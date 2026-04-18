#!/usr/bin/env python3
"""Phase 6: ingest the Phase 3 graph payload into Cognee Cloud."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION
from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.graph.builder import build_graph_payload, count_by_kind
from agnes.graph.cognee_cloud_client import (
    CognneCloudClient,
    CognneCloudError,
    build_transport,
)
from agnes.models.canonical import CanonicalRegistry
from agnes.utils.logging import configure_logging, get_logger

OUT_DIR = Path("outputs/reports")
REPORT_PATH = OUT_DIR / "cognee_cloud_ingest.json"

log = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest Phase 3 graph into Cognee Cloud.")
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
        help="Path to Phase 2 canonical_registry.json",
    )
    p.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Override AGNES_COGWIT_DATASET.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ingest only the first N canonical materials (useful for smoke).",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Sentences per /add call (default: 500).",
    )
    p.add_argument(
        "--fresh",
        action="store_true",
        help="Append a UTC timestamp to the dataset name to start a fresh dataset.",
    )
    p.add_argument(
        "--skip-cognify",
        action="store_true",
        help="Upload only; do not trigger /cognify.",
    )
    p.add_argument(
        "--verify-query",
        type=str,
        default=None,
        help="Run a GRAPH_COMPLETION search after cognify and include in report.",
    )
    return p.parse_args()


def _aiohttp_version() -> str | None:
    try:
        return version("aiohttp")
    except PackageNotFoundError:
        return None


async def _run(args: argparse.Namespace, settings: Settings) -> dict[str, object]:
    if not args.registry.is_file():
        return {"ok": False, "error": "registry_missing", "path": str(args.registry)}

    registry = CanonicalRegistry.model_validate_json(
        args.registry.read_text(encoding="utf-8")
    )
    if registry.taxonomy_version != TAXONOMY_VERSION:
        return {
            "ok": False,
            "error": "taxonomy_version_mismatch",
            "expected": TAXONOMY_VERSION,
            "got": registry.taxonomy_version,
        }

    dataset = args.dataset or settings.cogwit_dataset
    if args.fresh:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dataset = f"{dataset}-{stamp}"

    engine = get_engine(settings)
    nodes, edges = build_graph_payload(registry, engine, limit=args.limit)
    node_counts, edge_counts = count_by_kind(nodes, edges)

    client = CognneCloudClient(settings, transport=build_transport(settings))

    t0 = time.perf_counter()
    add_responses = await client.add_graph(
        nodes,
        edges,
        dataset_name=dataset,
        batch_size=args.batch_size,
    )
    add_ms = int((time.perf_counter() - t0) * 1000)

    dataset_id = str(add_responses[0].dataset_id) if add_responses else None

    cognify_ms: int | None = None
    cognify_status: object = None
    if add_responses and not args.skip_cognify:
        t1 = time.perf_counter()
        ds_id = add_responses[0].dataset_id
        if ds_id is not None:
            cognify_resp = await client.cognify(dataset_ids=[ds_id])
        else:
            cognify_resp = await client.cognify(datasets=[dataset])
        cognify_ms = int((time.perf_counter() - t1) * 1000)
        cognify_status = _summarize_cognify(cognify_resp)

    verify: dict[str, object] | None = None
    if args.verify_query:
        t2 = time.perf_counter()
        try:
            result = await client.search(args.verify_query)
            verify = {
                "ok": True,
                "query": args.verify_query,
                "latency_ms": int((time.perf_counter() - t2) * 1000),
                "preview": _preview_search(result),
            }
        except CognneCloudError as exc:
            verify = {
                "ok": False,
                "query": args.verify_query,
                "status": exc.status,
                "error": str(exc.error),
            }

    return {
        "ok": True,
        "dataset": dataset,
        "dataset_id": dataset_id,
        "n_sentences": len(nodes) + len(edges),
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "batches": len(add_responses),
        "add_ms": add_ms,
        "cognify_ms": cognify_ms,
        "cognify_status": cognify_status,
        "verify": verify,
        "aiohttp_version": _aiohttp_version(),
        "taxonomy_version": TAXONOMY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _summarize_cognify(resp: object) -> object:
    """Extract per-dataset status strings from a ``/api/v1/cognify`` JSON body."""
    if isinstance(resp, dict):
        summary: dict[str, object] = {}
        for k, v in resp.items():
            if isinstance(v, dict) and "status" in v:
                summary[k] = v.get("status")
            elif isinstance(v, str):
                summary[k] = v
            else:
                summary[k] = type(v).__name__
        return summary or "empty"
    if isinstance(resp, list):
        return {"count": len(resp)}
    return str(resp)[:200]


def _preview_search(result: object) -> object:
    """Shrink a Cognee Cloud search result to a human-readable preview."""
    if isinstance(result, list):
        out: list[dict[str, object]] = []
        for item in result[:3]:
            entry: dict[str, object] = {}
            sr = getattr(item, "search_result", None)
            if sr is None and isinstance(item, dict):
                sr = item.get("search_result")
            if isinstance(sr, str):
                entry["search_result"] = sr[:500]
            elif isinstance(sr, list) and sr:
                head = sr[0]
                if isinstance(head, dict):
                    entry["search_result_head"] = {
                        k: (v if not isinstance(v, str) else v[:200])
                        for k, v in list(head.items())[:6]
                    }
                else:
                    entry["search_result_head"] = str(head)[:500]
            elif sr is not None:
                entry["search_result"] = str(sr)[:500]
            out.append(entry)
        return out
    if hasattr(result, "result"):
        return {"result": str(getattr(result, "result"))[:500]}
    return str(result)[:500]


def main() -> int:
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    try:
        report = asyncio.run(_run(args, settings))
    except CognneCloudError as exc:
        payload = {
            "ok": False,
            "op": exc.op,
            "status": exc.status,
            "error": str(exc.error),
        }
        print(json.dumps(payload), file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(json.dumps({"report": str(REPORT_PATH), **report}, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
