"""Pipeline control endpoints.

Clients can POST a phase run with a typed body mirroring the CLI flags,
subscribe to live logs via Server-Sent Events, and cancel in-flight runs.
The scripts themselves are the source of truth for flag semantics; this module
only maps typed request fields into ``argv``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from agnes.api.services.run_manager import Phase, RunManager

router = APIRouter(prefix="/api/runs", tags=["runs"])


# ---------- request bodies ----------


class _BaseRunParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = False


class Phase4Params(_BaseRunParams):
    target: str | None = None
    all: bool = False
    top_k: int | None = Field(default=None, ge=1, le=100)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    cross_family: bool = False
    no_cache: bool = False


class Phase5Params(_BaseRunParams):
    top_sources: int | None = Field(default=None, ge=0, le=500)
    per_source: int | None = Field(default=None, ge=0, le=50)
    max_total: int | None = Field(default=None, ge=0, le=500)
    source: str | None = None
    model: str | None = None
    no_cache: bool = False


class Phase6Params(_BaseRunParams):
    max_llm_calls: int | None = Field(default=None, ge=0, le=500)
    model: str | None = None
    source: str | None = None
    company: int | None = None
    no_cache: bool = False


class Phase7Params(_BaseRunParams):
    top_n_polish: int | None = Field(default=None, ge=0, le=100)
    max_llm_calls: int | None = Field(default=None, ge=0, le=500)
    model: str | None = None
    source: str | None = None
    company: int | None = None
    min_grade: str | None = None
    no_cache: bool = False


# ---------- argv transformers ----------


def _flag(args: list[str], name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        if value:
            args.append(name)
        return
    args.extend([name, str(value)])


def _phase4_args(p: Phase4Params) -> list[str]:
    args: list[str] = []
    if p.target:
        _flag(args, "--target", p.target)
    if p.all:
        args.append("--all")
    _flag(args, "--top-k", p.top_k)
    _flag(args, "--min-score", p.min_score)
    if p.cross_family:
        args.append("--cross-family")
    if p.no_cache:
        args.append("--no-cache")
    if p.dry_run:
        args.append("--dry-run")
    return args


def _phase5_args(p: Phase5Params) -> list[str]:
    args: list[str] = []
    _flag(args, "--top-sources", p.top_sources)
    _flag(args, "--per-source", p.per_source)
    _flag(args, "--max-total", p.max_total)
    _flag(args, "--source", p.source)
    _flag(args, "--model", p.model)
    if p.no_cache:
        args.append("--no-cache")
    if p.dry_run:
        args.append("--dry-run")
    return args


def _phase6_args(p: Phase6Params) -> list[str]:
    args: list[str] = []
    _flag(args, "--max-llm-calls", p.max_llm_calls)
    _flag(args, "--model", p.model)
    _flag(args, "--source", p.source)
    _flag(args, "--company", p.company)
    if p.no_cache:
        args.append("--no-cache")
    if p.dry_run:
        args.append("--dry-run")
    return args


def _phase7_args(p: Phase7Params) -> list[str]:
    args: list[str] = []
    _flag(args, "--top-n-polish", p.top_n_polish)
    _flag(args, "--max-llm-calls", p.max_llm_calls)
    _flag(args, "--model", p.model)
    _flag(args, "--source", p.source)
    _flag(args, "--company", p.company)
    _flag(args, "--min-grade", p.min_grade)
    if p.no_cache:
        args.append("--no-cache")
    if p.dry_run:
        args.append("--dry-run")
    return args


# ---------- helpers ----------


def _manager(request: Request) -> RunManager:
    return request.app.state.run_manager


async def _start(
    request: Request, phase: Phase, args: list[str]
) -> dict[str, Any]:
    manager = _manager(request)
    try:
        record = await manager.start(phase, args)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "run_conflict", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_phase", "message": str(exc)},
        ) from exc
    return {
        "run_id": record.run_id,
        "phase": record.phase,
        "status": record.status,
        "args": record.args,
    }


def _sse_format(event: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode()


# ---------- endpoints ----------


@router.post("/phase4")
async def post_phase4(request: Request, body: Phase4Params | None = None) -> dict[str, Any]:
    return await _start(request, "phase4", _phase4_args(body or Phase4Params()))


@router.post("/phase5")
async def post_phase5(request: Request, body: Phase5Params | None = None) -> dict[str, Any]:
    return await _start(request, "phase5", _phase5_args(body or Phase5Params()))


@router.post("/phase6")
async def post_phase6(request: Request, body: Phase6Params | None = None) -> dict[str, Any]:
    return await _start(request, "phase6", _phase6_args(body or Phase6Params()))


@router.post("/phase7")
async def post_phase7(request: Request, body: Phase7Params | None = None) -> dict[str, Any]:
    return await _start(request, "phase7", _phase7_args(body or Phase7Params()))


@router.get("")
def list_runs(request: Request) -> dict[str, list[dict[str, Any]]]:
    return {"runs": _manager(request).list_runs()}


@router.get("/{run_id}")
def get_run(request: Request, run_id: str) -> dict[str, Any]:
    snap = _manager(request).snapshot(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id})
    return snap


@router.post("/{run_id}/cancel")
async def cancel_run(request: Request, run_id: str) -> dict[str, Any]:
    ok = await _manager(request).cancel(run_id)
    if not ok:
        raise HTTPException(status_code=409, detail={"error": "cancel_failed", "run_id": run_id})
    return {"run_id": run_id, "cancelled": True}


@router.get("/{run_id}/events")
async def stream_events(request: Request, run_id: str) -> StreamingResponse:
    manager = _manager(request)
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id})

    async def _gen() -> AsyncIterator[bytes]:
        yield _sse_format(
            "status",
            {
                "run_id": record.run_id,
                "phase": record.phase,
                "status": record.status,
                "pid": record.pid,
            },
        )
        try:
            async for line in manager.subscribe(run_id):
                if line is None:
                    break
                yield _sse_format(
                    "log",
                    {"ts": line.ts, "stream": line.stream, "text": line.text},
                )
                if await request.is_disconnected():
                    return
        except asyncio.CancelledError:
            return
        final = manager.get(run_id)
        if final is not None:
            yield _sse_format(
                "done",
                {
                    "run_id": final.run_id,
                    "status": final.status,
                    "exit_code": final.exit_code,
                    "ended_at": final.ended_at,
                    "error": final.error,
                },
            )

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


__all__ = ["router", "Phase4Params", "Phase5Params", "Phase6Params", "Phase7Params"]
