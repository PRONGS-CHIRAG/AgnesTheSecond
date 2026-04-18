"""Memoized Pydantic-validated loader for Phase 1-7 report artifacts.

The loader is the single read path for ``outputs/reports/*``. It is keyed by
``(path, mtime_ns)`` so that any pipeline re-run transparently invalidates the
in-memory copy.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from agnes.models.assessment import AssessmentReport
from agnes.models.canonical import CanonicalRegistry
from agnes.models.evidence import EvidenceReport
from agnes.models.recommendation import RecommendationReport
from agnes.models.substitutes import SubstituteCandidateReport

TReport = TypeVar("TReport", bound=BaseModel)


class ArtifactMissingError(FileNotFoundError):
    """Raised when an expected report file is not yet on disk."""


@dataclass(frozen=True)
class ArtifactStatus:
    name: str
    path: Path
    present: bool
    size_bytes: int | None
    mtime_ns: int | None


class _Cache(Generic[TReport]):
    __slots__ = ("mtime_ns", "payload")

    def __init__(self, mtime_ns: int, payload: TReport) -> None:
        self.mtime_ns = mtime_ns
        self.payload = payload


# (filename, model) for every report the UI can surface.
_REPORT_FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "registry": ("canonical_registry.json", CanonicalRegistry),
    "candidates": ("substitute_candidates.json", SubstituteCandidateReport),
    "evidence": ("substitute_evidence.json", EvidenceReport),
    "assessments": ("substitute_assessments.json", AssessmentReport),
    "recommendations": ("sourcing_recommendations.json", RecommendationReport),
}


class ArtifactLoader:
    """Thread-safe loader that validates reports through their Pydantic models."""

    def __init__(self, reports_dir: Path) -> None:
        self._reports_dir = reports_dir
        self._cache: dict[str, _Cache] = {}
        self._lock = threading.Lock()

    @property
    def reports_dir(self) -> Path:
        return self._reports_dir

    def path_for(self, name: str) -> Path:
        filename, _ = _REPORT_FILES[name]
        return self._reports_dir / filename

    def status(self, name: str) -> ArtifactStatus:
        path = self.path_for(name)
        if not path.is_file():
            return ArtifactStatus(
                name=name,
                path=path,
                present=False,
                size_bytes=None,
                mtime_ns=None,
            )
        stat = path.stat()
        return ArtifactStatus(
            name=name,
            path=path,
            present=True,
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )

    def all_statuses(self) -> dict[str, ArtifactStatus]:
        return {name: self.status(name) for name in _REPORT_FILES}

    def get_registry(self) -> CanonicalRegistry:
        return self._load("registry", CanonicalRegistry)

    def get_candidates(self) -> SubstituteCandidateReport:
        return self._load("candidates", SubstituteCandidateReport)

    def get_evidence(self) -> EvidenceReport:
        return self._load("evidence", EvidenceReport)

    def get_assessments(self) -> AssessmentReport:
        return self._load("assessments", AssessmentReport)

    def get_recommendations(self) -> RecommendationReport:
        return self._load("recommendations", RecommendationReport)

    def invalidate(self, name: str | None = None) -> None:
        with self._lock:
            if name is None:
                self._cache.clear()
            else:
                self._cache.pop(name, None)

    def _load(self, name: str, model: type[TReport]) -> TReport:
        path = self.path_for(name)
        if not path.is_file():
            raise ArtifactMissingError(f"{name} report not found at {path}")
        mtime_ns = path.stat().st_mtime_ns

        with self._lock:
            cached = self._cache.get(name)
            if cached is not None and cached.mtime_ns == mtime_ns:
                return cached.payload  # type: ignore[return-value]

        raw = path.read_text(encoding="utf-8")
        try:
            payload = model.model_validate_json(raw)
        except Exception:
            # fall back to JSON decode so we can raise a more helpful error later
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ArtifactMissingError(
                    f"{name} report at {path} is not valid JSON: {exc}"
                ) from exc
            raise

        with self._lock:
            self._cache[name] = _Cache(mtime_ns=mtime_ns, payload=payload)
        return payload
