"""Scope-guard agent shared by ``/api/chat`` and ``/api/voice/respond``.

The guard runs before any answering agent and decides whether the user's
message belongs to Agnes 2's remit (supply chain, procurement, suppliers,
BOMs, supply risk, sourcing savings, and closely related topics). If the
message is off-topic, we short-circuit with a polite refusal and never
spend tool budget on it.

Design notes
============

* Single, stateless OpenAI call. ``gpt-4o-mini`` is fast enough that the
  added latency is < 300 ms in the common case.
* Fails **open**: any parsing / API error allows the downstream agent to
  run. The hackathon cost of a false negative (off-topic leak) is smaller
  than the cost of a false positive (refusing a valid procurement
  question).
* Zero tool access — the guard reasons only from the text.
* Deterministic JSON contract, validated in Python so a malformed LLM
  response cannot break the pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


SCOPE_PROMPT_PATH = Path("prompts/scope_guard_agent.md")
SCOPE_MODEL_DEFAULT = "gpt-4o-mini"
SCOPE_MAX_TOKENS = 120

DEFAULT_DECLINE = (
    "I'm built for supply chain and procurement questions — ask me about "
    "suppliers, BOMs, spend, sourcing risk, or cost savings. For example: "
    "who are our top suppliers by spend?"
)

_FALLBACK_SYSTEM_PROMPT = (
    "You are the scope guard for Agnes 2, a supply chain and procurement "
    "assistant. Decide whether the user's message is about supply chain, "
    "procurement, suppliers, BOMs, supply risk, cost savings, or a closely "
    "related topic (greetings and short clarifications are in scope). "
    "Return strict JSON: "
    '{"in_scope": true} for on-topic, or '
    '{"in_scope": false, "decline": "<one short polite sentence steering '
    'the user back to supply chain topics>"} for off-topic.'
)


@dataclass(frozen=True)
class ScopeDecision:
    """Verdict returned by the scope guard."""

    in_scope: bool
    decline: str = ""
    latency_ms: int = 0

    @property
    def refusal(self) -> str:
        """Polite decline text to show the user (guaranteed non-empty)."""

        if self.in_scope:
            return ""
        return self.decline.strip() or DEFAULT_DECLINE


def _load_scope_prompt() -> str:
    try:
        return SCOPE_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:  # pragma: no cover - defensive
        logger.warning("scope_guard.prompt_missing path=%s", SCOPE_PROMPT_PATH)
        return _FALLBACK_SYSTEM_PROMPT


def _coerce_decision(raw: str) -> ScopeDecision | None:
    """Parse the LLM response into a :class:`ScopeDecision`, or ``None``."""

    text = (raw or "").strip()
    if not text:
        return None
    # Strip common markdown fencing the model might add despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    # Isolate the JSON object if the model added any prose around it.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        payload: Any = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    in_scope = payload.get("in_scope")
    if not isinstance(in_scope, bool):
        return None
    if in_scope:
        return ScopeDecision(in_scope=True)
    decline = str(payload.get("decline") or "").strip()
    return ScopeDecision(in_scope=False, decline=decline or DEFAULT_DECLINE)


def run_scope_guard(
    *,
    client: Any,
    message: str,
    model: str = SCOPE_MODEL_DEFAULT,
) -> ScopeDecision:
    """Classify ``message`` as in-scope or off-topic for Agnes 2.

    Fails open: any exception or malformed JSON yields ``in_scope=True``.
    """

    import time

    if not message or not message.strip():
        # Empty input = nothing to filter; let the downstream agent handle
        # the "empty question" edge case naturally.
        return ScopeDecision(in_scope=True)

    t0 = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _load_scope_prompt()},
                {"role": "user", "content": message.strip()},
            ],
            temperature=0.0,
            max_tokens=SCOPE_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
    except Exception:  # noqa: BLE001 - fail open
        logger.exception("scope_guard.llm_failed")
        return ScopeDecision(in_scope=True, latency_ms=int((time.perf_counter() - t0) * 1000))

    raw = completion.choices[0].message.content or ""
    decision = _coerce_decision(raw)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if decision is None:
        logger.warning("scope_guard.parse_failed raw=%r", raw[:200])
        return ScopeDecision(in_scope=True, latency_ms=latency_ms)

    logger.info(
        "scope_guard.decision in_scope=%s latency_ms=%d",
        decision.in_scope,
        latency_ms,
    )
    return ScopeDecision(
        in_scope=decision.in_scope,
        decline=decision.decline,
        latency_ms=latency_ms,
    )


__all__ = [
    "DEFAULT_DECLINE",
    "ScopeDecision",
    "run_scope_guard",
]
