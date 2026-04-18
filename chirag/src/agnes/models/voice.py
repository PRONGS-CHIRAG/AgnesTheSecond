"""Pydantic contracts for the /api/voice/* endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agnes.models.chat import ChatStep

VOICE_SCHEMA_VERSION = "voice-1.1.0"


class VoiceTimings(BaseModel):
    """Per-stage latency breakdown (milliseconds)."""

    stt_ms: int = 0
    translate_ms: int = 0
    answer_ms: int = 0
    humanize_ms: int = 0
    backtranslate_ms: int = 0
    total_ms: int = 0


class VoiceRespondResponse(BaseModel):
    """Answer the frontend gets *before* it asks for TTS audio."""

    transcript: str = Field(
        ...,
        description="User speech in the original spoken language (as recognised by Scribe v1).",
    )
    detected_language: str = Field(
        default="",
        description="ISO 639-1 code detected by Scribe (e.g. 'en', 'fr', 'de'). Empty if unknown.",
    )
    detected_language_name: str = Field(
        default="",
        description="Human-readable name of the detected language (e.g. 'English').",
    )
    language_probability: float = Field(
        default=0.0,
        description="Scribe confidence (0..1) for the detected language.",
    )
    english_transcript: str = Field(
        default="",
        description=(
            "English paraphrase produced by the translator agent. Equals "
            "`transcript` when the user already spoke English."
        ),
    )
    answer_raw: str = Field(
        ...,
        description=(
            "Raw reply from the answer agent (English, may contain markdown / tables)."
        ),
    )
    answer_spoken_en: str = Field(
        default="",
        description="Humanised English spoken reply (always produced).",
    )
    answer_spoken: str = Field(
        ...,
        description=(
            "Final speech-ready reply in the user's spoken language. Equal to "
            "`answer_spoken_en` for English users; otherwise back-translated."
        ),
    )
    answer_language: str = Field(
        default="en",
        description="ISO 639-1 code of `answer_spoken` (matches `detected_language` for non-English users).",
    )
    steps: list[ChatStep] = Field(default_factory=list)
    timings: VoiceTimings = Field(default_factory=VoiceTimings)
    llm_model: str
    voice_id: str
    schema_version: str = VOICE_SCHEMA_VERSION


class VoiceTtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice_id: str | None = Field(
        default=None,
        description="Optional ElevenLabs voice id override (default = Charlotte).",
    )


__all__ = [
    "VOICE_SCHEMA_VERSION",
    "VoiceRespondResponse",
    "VoiceTimings",
    "VoiceTtsRequest",
]
