"""Conversational chat agent router.

Mirrors the behaviour of ``taim/chat/agent.py`` but re-uses the chirag
artifact + settings stack:

* Shared ``make_client`` OpenAI factory.
* Re-uses the memoised ``ArtifactLoader`` for Phase 4/5/6.5/7 artifacts.
* Issues guarded SELECT-only queries via a dedicated SQLAlchemy engine.

The router is intentionally thin — the heavy lifting lives in
:mod:`agnes.api.chat_tools` so the tool implementations can be unit-tested
without the HTTP layer.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.engine import Engine

from agnes.api.chat_tools import (
    tool_analyze_bom,
    tool_execute_sql,
    tool_find_candidates,
    tool_get_evidence,
    tool_get_recommendation,
    tool_get_risks,
    tool_get_supplier_profile,
    tool_list_suppliers,
)
from agnes.api.services.artifact_loader import ArtifactLoader
from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.llm.openai_client import make_client
from agnes.models.chat import (
    CHAT_SCHEMA_VERSION,
    ChatRequest,
    ChatResponse,
    ChatStep,
)
from agnes.services.scope_guard import run_scope_guard

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

SYSTEM_PROMPT_PATH = Path("prompts/chat_agent.md")

MAX_ITERATIONS = 8


_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Run a guarded read-only SQL SELECT against the supply-chain "
                "SQLite database. Only a single SELECT (or WITH ... SELECT) "
                "statement is allowed. Result set is capped at 50 rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A single SELECT statement without a trailing semicolon.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_candidates",
            "description": (
                "Return Phase 4 substitute candidates for a canonical source "
                "key (e.g. 'vitamin-c-ascorbic-acid')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_key": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["source_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence",
            "description": (
                "Return the Phase 5 grounded-evidence bundle for a "
                "(source_key, candidate_key) pair."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_key": {"type": "string"},
                    "candidate_key": {"type": "string"},
                },
                "required": ["source_key", "candidate_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendation",
            "description": (
                "Return the Phase 7 consolidation opportunity + top rows for "
                "a canonical source_key."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_key": {"type": "string"},
                },
                "required": ["source_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risks",
            "description": (
                "Return Phase 6.5 supply-risk items, optionally filtered by "
                "severity ('high'|'medium'|'low') and/or type "
                "('single_source'|'supplier_concentration'|'critical_ingredient'|"
                "'supplier_quality'|'price_volatility')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "type_": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_bom",
            "description": (
                "Summarise a finished-good's BOM: components, suppliers, and "
                "single-source flags. Accepts an SKU or company-name fragment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string"},
                },
                "required": ["search_term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_profile",
            "description": (
                "Return a consolidated profile for one supplier — rating "
                "(quality / compliance / reliability / risk tier), "
                "procurement history (orders, total spend, on-time %, "
                "quality pass rate), top 5 products by spend, and distinct "
                "customer companies. Accepts either supplier_id or a name "
                "fragment (case-insensitive)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_suppliers",
            "description": (
                "Return a ranked supplier roster with Supplier_Rating + "
                "Procurement_History aggregates (spend, orders, on-time, "
                "quality pass rate). Use this for questions like 'top "
                "suppliers by spend', 'worst on-time suppliers', 'low-risk "
                "suppliers with quality above 80'. Limit capped at 50."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sort_by": {
                        "type": "string",
                        "enum": [
                            "spend",
                            "orders",
                            "on_time",
                            "quality",
                            "reliability",
                            "compliance",
                            "lead_time",
                            "name",
                        ],
                    },
                    "risk_tier": {
                        "type": "string",
                        "description": "Filter by Supplier_Rating.RiskTier (case-insensitive).",
                    },
                    "min_quality": {
                        "type": "number",
                        "description": "Only suppliers with QualityScore >= this.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
        },
    },
]


def _load_system_prompt() -> str:
    try:
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "You are Agnes, an AI supply-chain analyst. Always call tools "
            "before answering; never fabricate data."
        )


def _dispatch_tool(
    name: str,
    args: dict[str, Any],
    *,
    engine: Engine,
    loader: ArtifactLoader,
) -> tuple[dict[str, Any], str]:
    """Execute a tool call and return (result_dict, human_label)."""

    if name == "execute_sql":
        q = args.get("query", "")
        label = f"SQL: {q[:80]}{'…' if len(q) > 80 else ''}"
        return tool_execute_sql(engine, q), label
    if name == "find_candidates":
        return (
            tool_find_candidates(
                loader,
                source_key=args.get("source_key", ""),
                limit=int(args.get("limit", 10)),
            ),
            f"Candidates for {args.get('source_key', '')}",
        )
    if name == "get_evidence":
        return (
            tool_get_evidence(
                loader,
                source_key=args.get("source_key", ""),
                candidate_key=args.get("candidate_key", ""),
            ),
            f"Evidence: {args.get('source_key', '')} → {args.get('candidate_key', '')}",
        )
    if name == "get_recommendation":
        return (
            tool_get_recommendation(loader, source_key=args.get("source_key", "")),
            f"Recommendation for {args.get('source_key', '')}",
        )
    if name == "get_risks":
        return (
            tool_get_risks(
                loader,
                severity=args.get("severity"),
                type_=args.get("type_"),
                limit=int(args.get("limit", 20)),
            ),
            f"Risks ({args.get('severity') or 'all'} / {args.get('type_') or 'all'})",
        )
    if name == "analyze_bom":
        return (
            tool_analyze_bom(engine, search_term=args.get("search_term", "")),
            f"BOM: {args.get('search_term', '')}",
        )
    if name == "get_supplier_profile":
        sid = args.get("supplier_id")
        nm = args.get("name")
        return (
            tool_get_supplier_profile(
                engine,
                supplier_id=int(sid) if isinstance(sid, (int, float, str)) and str(sid).strip() else None,
                name=str(nm) if nm else None,
            ),
            f"Supplier profile: {nm or sid or '?'}",
        )
    if name == "list_suppliers":
        return (
            tool_list_suppliers(
                engine,
                sort_by=str(args.get("sort_by", "spend")),
                risk_tier=(str(args["risk_tier"]) if args.get("risk_tier") else None),
                min_quality=(
                    float(args["min_quality"])
                    if args.get("min_quality") is not None
                    else None
                ),
                limit=int(args.get("limit", 10)),
            ),
            f"Suppliers by {args.get('sort_by', 'spend')}",
        )
    return {"error": f"unknown_tool: {name}"}, f"unknown:{name}"


def _preview(payload: dict[str, Any], limit: int = 240) -> str:
    try:
        s = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        s = str(payload)
    return s if len(s) <= limit else s[: limit - 1] + "…"


@router.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    settings: Settings = request.app.state.settings
    loader: ArtifactLoader = request.app.state.artifact_loader

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "llm_unavailable",
                "message": (
                    "AGNES_OPENAI_API_KEY is not configured; the chat agent "
                    "requires an OpenAI key."
                ),
            },
        )

    client = make_client(settings.openai_api_key)
    engine = get_engine(settings)

    steps: list[ChatStep] = []

    # --- Scope guard: refuse off-topic requests before touching tools ---
    scope = run_scope_guard(client=client, message=body.message)
    steps.append(
        ChatStep(
            tool="scope_guard",
            args={"message_preview": body.message[:120]},
            label="Scope check",
            ok=True,
            result_preview=(
                "in_scope=true" if scope.in_scope else "in_scope=false"
            ),
            duration_ms=scope.latency_ms,
        )
    )
    if not scope.in_scope:
        logger.info("chat.refused reason=out_of_scope message_preview=%r", body.message[:120])
        return ChatResponse(
            reply=scope.refusal,
            steps=steps,
            llm_model=settings.openai_model,
            finish_reason="refused",
            schema_version=CHAT_SCHEMA_VERSION,
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _load_system_prompt()}
    ]
    for turn in body.history:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": body.message})

    finish_reason: str = "stop"
    reply = ""

    for iteration in range(MAX_ITERATIONS):
        try:
            completion = client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat.llm_call_failed", extra={"iteration": iteration})
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error": "llm_call_failed",
                    "message": str(exc),
                    "schema_version": CHAT_SCHEMA_VERSION,
                },
            ) from exc

        choice = completion.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            reply = msg.content or ""
            finish_reason = "stop"
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
            except Exception as exc:  # noqa: BLE001 - surface as step error
                logger.exception(
                    "chat.tool_failed", extra={"tool": name, "args": args}
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
    else:
        finish_reason = "max_iterations"
        reply = (
            reply
            or "I hit the maximum tool-use budget for this turn — please "
            "rephrase or narrow the question."
        )

    return ChatResponse(
        reply=reply,
        steps=steps,
        llm_model=settings.openai_model,
        finish_reason=finish_reason,  # type: ignore[arg-type]
        schema_version=CHAT_SCHEMA_VERSION,
    )


__all__ = ["router"]
