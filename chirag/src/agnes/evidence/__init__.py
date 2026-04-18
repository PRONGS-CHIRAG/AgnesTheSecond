"""Phase 5: external evidence enrichment over Phase 4 substitute candidates."""

from agnes.evidence.enricher import (
    EvidenceCache,
    enrich_pairs,
    load_prompt_template,
    render_prompt,
    select_pairs,
)

__all__ = [
    "EvidenceCache",
    "enrich_pairs",
    "load_prompt_template",
    "render_prompt",
    "select_pairs",
]
