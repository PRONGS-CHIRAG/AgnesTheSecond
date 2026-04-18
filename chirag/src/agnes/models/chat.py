"""Request / response contracts for the conversational chat agent."""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

CHAT_SCHEMA_VERSION: Final[str] = "v1"


class ChatMessage(BaseModel):
    """A single turn in the running conversation history."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatStep(BaseModel):
    """Observability record for one tool invocation inside the agentic loop."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    label: str
    ok: bool
    error: str | None = None
    result_preview: str = ""
    duration_ms: int = 0


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    steps: list[ChatStep] = Field(default_factory=list)
    llm_model: str | None = None
    finish_reason: Literal["stop", "max_iterations", "error", "refused"] = "stop"
    schema_version: str = CHAT_SCHEMA_VERSION


__all__ = [
    "CHAT_SCHEMA_VERSION",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatStep",
]
