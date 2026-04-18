"""Voice-chat router for Agnes 2.

Orchestrates a multi-agent voice pipeline:

1. **Transcriber** (ElevenLabs Scribe v1) — converts the user's audio to
   text and emits the detected language code.
2. **Translator agent** (OpenAI, gpt-4o-mini) — *only runs for non-English
   input*. Produces an idiomatic English paraphrase so the answer agent
   always operates on English.
3. **Answer agent** (OpenAI + Agnes tools) — grounded reply using the
   same supplier / BOM / risk / substitution tools as /api/chat, bounded
   to 2 tool iterations for voice latency.
4. **Humanizer agent** (OpenAI, fast model) — rewrites the reply in
   speech-friendly English form.
5. **Back-translator agent** (OpenAI, gpt-4o-mini) — *only runs for
   non-English input*. Renders the humanised English reply back into the
   user's spoken language so TTS sounds native.
6. **TTS** (ElevenLabs streaming) — exposed as a separate endpoint so the
   client can start playback while the transcript is already rendered.

The client-side VAD is the "seventh agent" — it decides when the user has
stopped speaking and triggers the upload.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import Engine

# NOTE: we deliberately reuse the chat agent's private tool list + dispatcher
# to keep the two agents in lockstep. If the chat agent grows a new tool,
# the voice agent picks it up for free.
from agnes.api.chat import _TOOLS, _dispatch_tool, _preview
from agnes.api.services.artifact_loader import ArtifactLoader
from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.llm.openai_client import make_client
from agnes.models.chat import ChatStep
from agnes.services.scope_guard import run_scope_guard
from agnes.models.voice import (
    VOICE_SCHEMA_VERSION,
    VoiceRespondResponse,
    VoiceTimings,
    VoiceTtsRequest,
)
from agnes.tools.elevenlabs_client import (
    DEFAULT_VOICE_ID,
    ElevenLabsError,
    transcribe,
    tts_stream,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

ANSWER_PROMPT_PATH = Path("prompts/voice_answer_agent.md")
HUMANIZER_PROMPT_PATH = Path("prompts/voice_humanizer_agent.md")
TRANSLATOR_PROMPT_PATH = Path("prompts/voice_translator_agent.md")
BACKTRANSLATOR_PROMPT_PATH = Path("prompts/voice_backtranslator_agent.md")

ANSWER_MAX_ITERATIONS = 2  # strict bound to keep voice latency < 3s
ANSWER_MAX_TOKENS = 220
HUMANIZER_MODEL = "gpt-4o-mini"
HUMANIZER_MAX_TOKENS = 160
TRANSLATOR_MODEL = "gpt-4o-mini"
TRANSLATOR_MAX_TOKENS = 200
BACKTRANSLATOR_MODEL = "gpt-4o-mini"
BACKTRANSLATOR_MAX_TOKENS = 220


# ISO 639-1 → English name for the languages ElevenLabs Turbo v2.5 supports.
# Used to build the translator/back-translator system prompts and the UI pill.
_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "es": "Spanish",
    "fi": "Finnish",
    "fil": "Filipino",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sv": "Swedish",
    "ta": "Tamil",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh": "Chinese",
}


def _language_name(code: str) -> str:
    code = (code or "").lower()
    if not code:
        return ""
    return _LANG_NAMES.get(code, code.upper())


def _is_english(code: str) -> bool:
    return (code or "").lower().startswith("en")


def _resolved_key(settings: Settings) -> str | None:
    """Prefer pydantic-settings field (reads chirag/.env); fall back to env."""

    import os

    return (
        settings.elevenlabs_api_key
        or os.getenv("AGNES_ELEVENLABS_API_KEY")
        or os.getenv("ELEVENLABS_API_KEY")
    )


def _resolved_voice_id(settings: Settings) -> str:
    return settings.elevenlabs_voice_id or DEFAULT_VOICE_ID


def _load_prompt(path: Path, fallback: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback


def _answer_system_prompt() -> str:
    return _load_prompt(
        ANSWER_PROMPT_PATH,
        (
            "You are Agnes 2, a voice assistant. Call tools to ground any "
            "factual claim. Keep replies to 30-60 spoken words, no markdown."
        ),
    )


def _humanizer_system_prompt() -> str:
    return _load_prompt(
        HUMANIZER_PROMPT_PATH,
        (
            "Rewrite the analyst reply below into 25-55 spoken words of "
            "plain English. Strip markdown and tables. Keep the key fact."
        ),
    )


def _translator_system_prompt() -> str:
    return _load_prompt(
        TRANSLATOR_PROMPT_PATH,
        (
            "Translate the user utterance below into natural English. "
            "Keep proper nouns untouched. Output only the translation."
        ),
    )


def _backtranslator_system_prompt() -> str:
    return _load_prompt(
        BACKTRANSLATOR_PROMPT_PATH,
        (
            "Translate the English reply below into the target language "
            "provided in context. Keep proper nouns untouched. Output only "
            "the translation."
        ),
    )


def _run_translator(
    *,
    client: Any,
    model: str,
    source_text: str,
    source_language_code: str,
) -> str:
    """Translate a non-English utterance into natural English."""

    lang_name = _language_name(source_language_code) or source_language_code
    system = _translator_system_prompt()
    user = (
        f"Source language: {source_language_code} ({lang_name})\n"
        f"User utterance:\n{source_text}"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=TRANSLATOR_MAX_TOKENS,
    )
    english = (completion.choices[0].message.content or "").strip()
    # Strip accidental wrapping quotes.
    if (english.startswith('"') and english.endswith('"')) or (
        english.startswith("'") and english.endswith("'")
    ):
        english = english[1:-1].strip()
    return english


def _run_backtranslator(
    *,
    client: Any,
    model: str,
    english_text: str,
    target_language_code: str,
) -> str:
    """Render an English reply in the user's original language."""

    lang_name = _language_name(target_language_code) or target_language_code
    system = _backtranslator_system_prompt()
    user = (
        f"Target language: {lang_name} ({target_language_code})\n"
        f"English reply:\n{english_text}"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=BACKTRANSLATOR_MAX_TOKENS,
    )
    translated = (completion.choices[0].message.content or "").strip()
    if (translated.startswith('"') and translated.endswith('"')) or (
        translated.startswith("'") and translated.endswith("'")
    ):
        translated = translated[1:-1].strip()
    return translated


def _run_answer_agent(
    *,
    client: Any,
    model: str,
    engine: Engine,
    loader: ArtifactLoader,
    transcript: str,
) -> tuple[str, list[ChatStep]]:
    """Run the tool-calling answer agent (bounded iterations)."""

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _answer_system_prompt()},
        {"role": "user", "content": transcript},
    ]
    steps: list[ChatStep] = []
    reply = ""

    for iteration in range(ANSWER_MAX_ITERATIONS + 1):
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto" if iteration < ANSWER_MAX_ITERATIONS else "none",
            temperature=0.3,
            max_tokens=ANSWER_MAX_TOKENS,
        )
        choice = completion.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            reply = (msg.content or "").strip()
            break

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                args = {}

            t0 = time.perf_counter()
            try:
                payload, label = _dispatch_tool(
                    name, args, engine=engine, loader=loader
                )
                err = payload.get("error") if isinstance(payload, dict) else None
                ok = err is None
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "voice.tool_failed", extra={"tool": name, "args": args}
                )
                payload = {"error": f"tool_crashed: {exc}"}
                label = f"{name} (crashed)"
                err = str(exc)
                ok = False
            duration_ms = int((time.perf_counter() - t0) * 1000)

            steps.append(
                ChatStep(
                    tool=name,
                    args=args,
                    label=label,
                    ok=ok,
                    error=err if not ok else None,
                    result_preview=_preview(payload),
                    duration_ms=duration_ms,
                )
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                }
            )

    if not reply:
        reply = (
            "Sorry — I couldn't pull that together in time. Want to try a "
            "narrower question?"
        )
    return reply, steps


def _run_humanizer(*, client: Any, model: str, raw_answer: str) -> str:
    """Rewrite the raw answer into a TTS-friendly spoken version."""

    if not raw_answer.strip():
        return "I don't have an answer for that right now."

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _humanizer_system_prompt()},
            {"role": "user", "content": raw_answer},
        ],
        temperature=0.4,
        max_tokens=HUMANIZER_MAX_TOKENS,
    )
    spoken = (completion.choices[0].message.content or "").strip()
    # Defensive: strip stray markdown that may sneak through.
    for token in ("```", "**", "__", "`"):
        spoken = spoken.replace(token, "")
    return spoken or raw_answer


@router.post("/api/voice/respond", response_model=VoiceRespondResponse)
async def voice_respond(
    request: Request,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> VoiceRespondResponse:
    """Accept one audio blob; auto-detect language; translate if needed.

    Flow:
        STT → [translator if non-English] → answer → humanize →
        [back-translator if non-English] → response.
    """

    settings: Settings = request.app.state.settings
    loader: ArtifactLoader = request.app.state.artifact_loader

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "llm_unavailable",
                "message": "AGNES_OPENAI_API_KEY is not configured.",
            },
        )

    eleven_key = _resolved_key(settings)
    if not eleven_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "elevenlabs_key_missing",
                "message": "Set AGNES_ELEVENLABS_API_KEY in chirag/.env",
            },
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "empty_audio"},
        )

    t_total = time.perf_counter()

    # --- 1. Transcribe (auto-detect language by default) ---
    t0 = time.perf_counter()
    try:
        stt = await transcribe(
            audio_bytes,
            api_key=eleven_key,
            filename=audio.filename or "speech.webm",
            content_type=audio.content_type or "audio/webm",
            language_code=language,  # None → Scribe auto-detect
        )
    except ElevenLabsError as exc:
        logger.warning("voice.stt_failed", extra={"code": exc.code})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    stt_ms = int((time.perf_counter() - t0) * 1000)

    client = make_client(settings.openai_api_key)
    engine = get_engine(settings)

    detected_lang = stt.language_code or ""
    is_english = _is_english(detected_lang) or not detected_lang

    # --- 2. Translator agent (only for non-English input) ---
    translate_ms = 0
    if is_english:
        english_transcript = stt.text
    else:
        t0 = time.perf_counter()
        try:
            english_transcript = await asyncio.to_thread(
                _run_translator,
                client=client,
                model=TRANSLATOR_MODEL,
                source_text=stt.text,
                source_language_code=detected_lang,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("voice.translate_failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "translate_failed", "message": str(exc)},
            ) from exc
        translate_ms = int((time.perf_counter() - t0) * 1000)
        if english_transcript.strip().upper() == "UNCLEAR" or not english_transcript:
            # Graceful fallback: pass the raw transcript; answer agent will
            # ask for clarification.
            english_transcript = stt.text

    # --- 3a. Scope guard (runs on the English version of the utterance) ---
    scope = await asyncio.to_thread(
        run_scope_guard, client=client, message=english_transcript
    )
    steps: list[ChatStep] = [
        ChatStep(
            tool="scope_guard",
            args={"message_preview": english_transcript[:120]},
            label="Scope check",
            ok=True,
            result_preview=(
                "in_scope=true" if scope.in_scope else "in_scope=false"
            ),
            duration_ms=scope.latency_ms,
        )
    ]

    answer_ms = 0
    humanize_ms = 0
    refused = not scope.in_scope
    if refused:
        logger.info(
            "voice.refused reason=out_of_scope transcript_preview=%r",
            english_transcript[:120],
        )
        answer_raw = scope.refusal
        answer_spoken_en = scope.refusal
    else:
        # --- 3b. Answer agent (always operates on English) ---
        t0 = time.perf_counter()
        try:
            answer_raw, agent_steps = await asyncio.to_thread(
                _run_answer_agent,
                client=client,
                model=settings.openai_model,
                engine=engine,
                loader=loader,
                transcript=english_transcript,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("voice.answer_failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "answer_failed", "message": str(exc)},
            ) from exc
        answer_ms = int((time.perf_counter() - t0) * 1000)
        steps.extend(agent_steps)

        # --- 4. Humanizer agent (English, spoken-friendly) ---
        t0 = time.perf_counter()
        try:
            answer_spoken_en = await asyncio.to_thread(
                _run_humanizer,
                client=client,
                model=HUMANIZER_MODEL,
                raw_answer=answer_raw,
            )
        except Exception:  # noqa: BLE001 - non-fatal, fall back to raw
            logger.exception("voice.humanize_failed")
            answer_spoken_en = answer_raw
        humanize_ms = int((time.perf_counter() - t0) * 1000)

    # --- 5. Back-translator agent (only for non-English input) ---
    backtranslate_ms = 0
    if is_english:
        answer_spoken = answer_spoken_en
        answer_language = "en"
    else:
        t0 = time.perf_counter()
        try:
            answer_spoken = await asyncio.to_thread(
                _run_backtranslator,
                client=client,
                model=BACKTRANSLATOR_MODEL,
                english_text=answer_spoken_en,
                target_language_code=detected_lang,
            )
        except Exception:  # noqa: BLE001 - non-fatal, fall back to English
            logger.exception("voice.backtranslate_failed")
            answer_spoken = answer_spoken_en
            answer_language = "en"
        else:
            answer_language = detected_lang
        backtranslate_ms = int((time.perf_counter() - t0) * 1000)

    total_ms = int((time.perf_counter() - t_total) * 1000)
    logger.info(
        "voice.respond",
        extra={
            "detected_language": detected_lang,
            "refused": refused,
            "scope_ms": scope.latency_ms,
            "stt_ms": stt_ms,
            "translate_ms": translate_ms,
            "answer_ms": answer_ms,
            "humanize_ms": humanize_ms,
            "backtranslate_ms": backtranslate_ms,
            "total_ms": total_ms,
            "transcript_len": len(stt.text),
            "spoken_len": len(answer_spoken),
            "n_steps": len(steps),
        },
    )

    return VoiceRespondResponse(
        transcript=stt.text,
        detected_language=detected_lang,
        detected_language_name=_language_name(detected_lang),
        language_probability=stt.language_probability,
        english_transcript=english_transcript,
        answer_raw=answer_raw,
        answer_spoken_en=answer_spoken_en,
        answer_spoken=answer_spoken,
        answer_language=answer_language,
        steps=steps,
        timings=VoiceTimings(
            stt_ms=stt_ms,
            translate_ms=translate_ms,
            answer_ms=answer_ms,
            humanize_ms=humanize_ms,
            backtranslate_ms=backtranslate_ms,
            total_ms=total_ms,
        ),
        llm_model=settings.openai_model,
        voice_id=_resolved_voice_id(settings),
        schema_version=VOICE_SCHEMA_VERSION,
    )


@router.post("/api/voice/tts")
async def voice_tts(body: VoiceTtsRequest, request: Request) -> StreamingResponse:
    """Stream audio/mpeg for ``text`` from ElevenLabs."""

    settings: Settings = request.app.state.settings

    # Eager key probe — tts_stream is an async generator, so errors raised
    # in its body don't propagate until the first chunk is pulled. Checking
    # here guarantees a proper 502 before StreamingResponse takes over.
    eleven_key = _resolved_key(settings)
    if not eleven_key:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "elevenlabs_key_missing",
                "message": "Set AGNES_ELEVENLABS_API_KEY in chirag/.env",
            },
        )

    stream = tts_stream(
        body.text,
        api_key=eleven_key,
        voice_id=body.voice_id or _resolved_voice_id(settings),
    )

    async def _iter() -> Any:
        try:
            async for chunk in stream:
                yield chunk
        except ElevenLabsError as exc:
            logger.warning("voice.tts_stream_failed", extra={"code": exc.code})
            return

    return StreamingResponse(
        _iter(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/voice/config")
def voice_config(request: Request) -> dict[str, Any]:
    """Minimal config probe the frontend can hit to know whether voice is ready."""

    settings: Settings = request.app.state.settings
    return {
        "ready": bool(_resolved_key(settings)),
        "voice_id": _resolved_voice_id(settings),
        "schema_version": VOICE_SCHEMA_VERSION,
    }


__all__ = ["router"]
