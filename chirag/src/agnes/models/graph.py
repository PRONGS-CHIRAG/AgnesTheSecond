"""Typed KG node / edge / ingest-report models (Phase 3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agnes.graph.schema import EdgeKind, NodeKind


class KGNode(BaseModel):
    """A deterministic knowledge-graph node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: NodeKind
    props: dict[str, Any] = Field(default_factory=dict)


class KGEdge(BaseModel):
    """A directed edge between two ``KGNode`` ids."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    kind: EdgeKind
    props: dict[str, Any] = Field(default_factory=dict)


class GraphIngestReport(BaseModel):
    """Summary written by ``scripts/phase3_graph_ingest.py``."""

    model_config = ConfigDict(extra="forbid")

    graph_schema_version: str
    taxonomy_version: str
    dataset: str
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    duration_ms: int
    partial: bool
    cognee_version: str | None = None
    batches_written: int = 0


def node_id(kind: NodeKind, key: str | int) -> str:
    """Stable string id, e.g. ``Company:3`` or ``CanonicalMaterial:calcium-citrate``."""
    return f"{kind}:{key}"
