"""Async subprocess manager for Phase 4-7 CLI runs.

The run manager is intentionally minimal: it spawns `scripts/phaseN_*.py` as a
subprocess, tails stdout line-by-line, fans out each line to one or more
Server-Sent-Event subscribers, and retains a bounded history of recent runs in
memory. Runs are not persisted; the pipeline artifacts themselves are the
source of truth.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agnes.api.services.artifact_loader import ArtifactLoader

Phase = Literal["phase4", "phase5", "phase6", "phase7"]
RunStatus = Literal["starting", "running", "succeeded", "failed", "cancelled"]

_PHASE_SCRIPTS: dict[Phase, str] = {
    "phase4": "scripts/phase4_candidates.py",
    "phase5": "scripts/phase5_evidence.py",
    "phase6": "scripts/phase6_assess.py",
    "phase7": "scripts/phase7_recommend.py",
}

# Which artifact each phase refreshes — used to invalidate the loader cache on success.
_PHASE_ARTIFACT: dict[Phase, str] = {
    "phase4": "candidates",
    "phase5": "evidence",
    "phase6": "assessments",
    "phase7": "recommendations",
}

_LOG_RING_SIZE = 2000
_RUN_HISTORY_SIZE = 20


@dataclass
class LogLine:
    ts: float
    stream: Literal["stdout", "stderr"]
    text: str


@dataclass
class RunRecord:
    run_id: str
    phase: Phase
    args: list[str]
    status: RunStatus
    started_at: float
    ended_at: float | None = None
    exit_code: int | None = None
    error: str | None = None
    pid: int | None = None
    logs: deque[LogLine] = field(default_factory=lambda: deque(maxlen=_LOG_RING_SIZE))
    subscribers: list[asyncio.Queue[LogLine | None]] = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "args": self.args,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "pid": self.pid,
            "log_count": len(self.logs),
        }


class RunManager:
    """In-memory registry of pipeline runs with async subprocess support."""

    def __init__(self, *, repo_root: Path, artifact_loader: ArtifactLoader) -> None:
        self._repo_root = repo_root
        self._loader = artifact_loader
        self._runs: dict[str, RunRecord] = {}
        self._order: deque[str] = deque(maxlen=_RUN_HISTORY_SIZE)
        self._active_by_phase: dict[Phase, str] = {}
        self._lock = asyncio.Lock()

    # ---------- public API ----------

    def list_runs(self) -> list[dict]:
        return [self._runs[rid].to_dict() for rid in reversed(self._order) if rid in self._runs]

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def snapshot(self, run_id: str) -> dict | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        out = record.to_dict()
        out["logs"] = [
            {"ts": line.ts, "stream": line.stream, "text": line.text} for line in record.logs
        ]
        return out

    async def start(self, phase: Phase, args: list[str]) -> RunRecord:
        if phase not in _PHASE_SCRIPTS:
            raise ValueError(f"unknown phase: {phase}")

        async with self._lock:
            active_id = self._active_by_phase.get(phase)
            if active_id and self._runs[active_id].status in {"starting", "running"}:
                raise RuntimeError(f"{phase} is already running (run_id={active_id})")

            run_id = uuid.uuid4().hex[:12]
            record = RunRecord(
                run_id=run_id,
                phase=phase,
                args=list(args),
                status="starting",
                started_at=time.time(),
            )
            self._runs[run_id] = record
            self._order.append(run_id)
            # Drop oldest entries not kept by the bounded deque
            for stale in list(self._runs):
                if stale not in self._order:
                    self._runs.pop(stale, None)
            self._active_by_phase[phase] = run_id

        script = _PHASE_SCRIPTS[phase]
        cmd = [sys.executable, script, *args]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self._repo_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            record.status = "failed"
            record.ended_at = time.time()
            record.error = f"failed_to_spawn: {exc}"
            self._close_subscribers(record)
            return record

        record.process = proc
        record.pid = proc.pid
        record.status = "running"

        # Kick off background readers for stdout/stderr.
        asyncio.create_task(self._tail(record, proc.stdout, "stdout"))
        asyncio.create_task(self._tail(record, proc.stderr, "stderr"))
        asyncio.create_task(self._wait(record, proc, phase))
        return record

    async def cancel(self, run_id: str) -> bool:
        record = self._runs.get(run_id)
        if record is None or record.process is None:
            return False
        if record.status not in {"starting", "running"}:
            return False
        try:
            record.process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            return False
        # Give it a moment to exit, then SIGKILL if stuck.
        try:
            await asyncio.wait_for(record.process.wait(), timeout=5.0)
        except TimeoutError:
            try:
                record.process.kill()
            except ProcessLookupError:
                pass
        if record.status not in {"succeeded", "failed"}:
            record.status = "cancelled"
        return True

    async def subscribe(self, run_id: str) -> AsyncIterator[LogLine | None]:
        record = self._runs.get(run_id)
        if record is None:
            raise KeyError(run_id)

        queue: asyncio.Queue[LogLine | None] = asyncio.Queue(maxsize=1024)
        # Replay buffered history so late subscribers see the whole stream.
        for line in list(record.logs):
            await queue.put(line)
        # Only add as subscriber if the run is still live.
        if record.status in {"starting", "running"}:
            record.subscribers.append(queue)
        else:
            await queue.put(None)

        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            try:
                record.subscribers.remove(queue)
            except ValueError:
                pass

    async def shutdown(self) -> None:
        for record in list(self._runs.values()):
            if record.process is not None and record.status in {"starting", "running"}:
                try:
                    record.process.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    continue
                try:
                    await asyncio.wait_for(record.process.wait(), timeout=2.0)
                except TimeoutError:
                    try:
                        record.process.kill()
                    except ProcessLookupError:
                        pass
            self._close_subscribers(record)

    # ---------- internals ----------

    async def _tail(
        self,
        record: RunRecord,
        stream: asyncio.StreamReader | None,
        kind: Literal["stdout", "stderr"],
    ) -> None:
        if stream is None:
            return
        while True:
            try:
                raw = await stream.readline()
            except Exception as exc:
                self._emit(record, kind, f"<reader error: {exc}>")
                return
            if not raw:
                return
            text = raw.decode("utf-8", errors="replace").rstrip("\n")
            if text:
                self._emit(record, kind, text)

    def _emit(self, record: RunRecord, kind: Literal["stdout", "stderr"], text: str) -> None:
        line = LogLine(ts=time.time(), stream=kind, text=text)
        record.logs.append(line)
        for queue in list(record.subscribers):
            try:
                queue.put_nowait(line)
            except asyncio.QueueFull:
                # Drop oldest by reading one out and re-inserting to keep queue live.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(line)
                except asyncio.QueueFull:
                    continue

    async def _wait(
        self, record: RunRecord, proc: asyncio.subprocess.Process, phase: Phase
    ) -> None:
        try:
            exit_code = await proc.wait()
        except asyncio.CancelledError:
            exit_code = -1
        record.exit_code = exit_code
        record.ended_at = time.time()
        if record.status == "cancelled":
            pass
        elif exit_code == 0:
            record.status = "succeeded"
            # refresh the artifact this phase produces so subsequent reads are current
            try:
                self._loader.invalidate(_PHASE_ARTIFACT[phase])
            except KeyError:
                pass
        else:
            record.status = "failed"
            if record.error is None:
                record.error = f"exit_code={exit_code}"
        # clear the active slot
        async with self._lock:
            if self._active_by_phase.get(phase) == record.run_id:
                self._active_by_phase.pop(phase, None)
        self._close_subscribers(record)

    def _close_subscribers(self, record: RunRecord) -> None:
        for queue in list(record.subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        record.subscribers.clear()


__all__ = ["LogLine", "Phase", "RunManager", "RunRecord", "RunStatus"]
