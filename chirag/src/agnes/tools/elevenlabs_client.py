"""Thin async ElevenLabs client for Scribe v1 STT + streaming TTS.

Kept intentionally small and dependency-free (httpx only) so it can be unit
tested without network access. Two public entry points:

- :func:`transcribe` - multipart upload → plain-text transcript.
- :func:`tts_stream`  - async byte iterator of audio/mpeg chunks.

Latency notes:

- TTS uses ``eleven_turbo_v2_5`` + ``optimize_streaming_latency=4`` — this
  cuts first-byte latency to ~300-400 ms for short replies.
- STT uses ``scribe_v1``. ElevenLabs returns the full transcript in one
  response (no streaming), so we just await the POST.

Errors are wrapped in :class:`ElevenLabsError` with a stable ``code`` prefix
so the voice router can translate them to structured HTTP errors.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

DEFAULT_TTS_MODEL = "eleven_turbo_v2_5"
DEFAULT_STT_MODEL = "scribe_v1"
DEFAULT_VOICE_ID = "XB0fDUnXU5powFXDhCwa"


class ElevenLabsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Transcript:
    """Result bundle from a Scribe v1 transcription."""

    text: str
    language_code: str  # ISO 639-1 (``en``, ``fr``, ``de``, ...) or ``""``
    language_probability: float  # 0..1 confidence, 0.0 when missing


def _resolve_key(api_key: str | None) -> str:
    key = (
        api_key
        or os.getenv("AGNES_ELEVENLABS_API_KEY")
        or os.getenv("ELEVENLABS_API_KEY")
    )
    if not key:
        raise ElevenLabsError(
            "elevenlabs_key_missing",
            "Set AGNES_ELEVENLABS_API_KEY in chirag/.env",
        )
    return key


def default_voice_id() -> str:
    return os.getenv("AGNES_ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)


async def transcribe(
    audio: bytes,
    *,
    api_key: str | None = None,
    filename: str = "speech.webm",
    content_type: str = "audio/webm",
    language_code: str | None = None,
) -> Transcript:
    """Upload one blob of audio and return the recognised transcript.

    When ``language_code`` is ``None`` (the default) Scribe auto-detects
    the spoken language and returns the ISO 639-1 code in
    ``Transcript.language_code``. Pass a value to lock recognition to a
    specific language.
    """

    if not audio:
        raise ElevenLabsError("stt_empty_audio", "audio payload is empty")

    headers = {"xi-api-key": _resolve_key(api_key)}
    files = {"file": (filename, audio, content_type)}
    data: dict[str, str] = {"model_id": DEFAULT_STT_MODEL}
    if language_code:
        data["language_code"] = language_code

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ELEVENLABS_API_URL}/speech-to-text",
            headers=headers,
            files=files,
            data=data,
        )

    if resp.status_code != 200:
        raise ElevenLabsError(
            "stt_failed",
            f"{resp.status_code} {resp.text[:200]}",
        )

    payload = resp.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise ElevenLabsError("stt_empty_transcript", "no speech detected")

    lang = str(payload.get("language_code") or "").strip().lower()
    try:
        prob = float(payload.get("language_probability") or 0.0)
    except (TypeError, ValueError):
        prob = 0.0
    return Transcript(text=text, language_code=lang, language_probability=prob)


async def tts_stream(
    text: str,
    *,
    api_key: str | None = None,
    voice_id: str | None = None,
    stability: float = 0.45,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    optimize_streaming_latency: int = 4,
) -> AsyncIterator[bytes]:
    """Stream audio/mpeg bytes for ``text`` using ElevenLabs TTS."""

    if not text.strip():
        raise ElevenLabsError("tts_empty_text", "text payload is empty")

    vid = voice_id or default_voice_id()
    headers = {
        "xi-api-key": _resolve_key(api_key),
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    body = {
        "text": text,
        "model_id": DEFAULT_TTS_MODEL,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
        "optimize_streaming_latency": optimize_streaming_latency,
    }

    client = httpx.AsyncClient(timeout=60.0)
    try:
        async with client.stream(
            "POST",
            f"{ELEVENLABS_API_URL}/text-to-speech/{vid}/stream",
            headers=headers,
            json=body,
        ) as resp:
            if resp.status_code != 200:
                body_text = (await resp.aread())[:200]
                raise ElevenLabsError(
                    "tts_failed",
                    f"{resp.status_code} {body_text!r}",
                )
            async for chunk in resp.aiter_bytes():
                if chunk:
                    yield chunk
    finally:
        await client.aclose()


__all__ = [
    "DEFAULT_VOICE_ID",
    "ElevenLabsError",
    "Transcript",
    "default_voice_id",
    "transcribe",
    "tts_stream",
]
