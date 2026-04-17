# Agnes The Second

Evidence-grounded **raw material substitution** and **sourcing consolidation** for CPG procurement: ingest BOM and supplier data from SQLite, reason about substitutes with explicit uncertainty, and recommend consolidation with evidence trails (see [plan.md](plan.md)).

This repository is a hackathon MVP scaffold. Phase 0 provides environment setup and connectivity checks only.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` if needed)
- Google AI Studio **Gemini API key** (for LLM smoke tests)

## Setup

```bash
uv sync --extra dev
cp .env.example .env
# Set AGNES_GEMINI_API_KEY in .env

mkdir -p data/raw
cp hackathon-tumai/db.sqlite data/raw/db.sqlite
```

## Verify (Phase 0 smoke tests)

From the repository root:

```bash
uv run python scripts/smoke_db.py
uv run python scripts/smoke_gemini.py
uv run python scripts/smoke_cognee.py
uv run pytest -q
```

Expected `smoke_db` row counts (challenge DB): Company 61, Product 1025, BOM 149, BOM_Component 1528, Supplier 40, Supplier_Product 1633.

`smoke_gemini` and `smoke_cognee` require a valid `AGNES_GEMINI_API_KEY` and network access (first Cognee run may download embedding models).

## Project docs

- [plan.md](plan.md) — execution blueprint
- [Claude.md](Claude.md) — engineering conventions
- [Do_not_do.md](Do_not_do.md) — anti-patterns to avoid

## Layout

- `src/agnes/` — Python package (data loader, retrieval, graph, future modules)
- `data/raw/` — SQLite challenge database (not committed; copy from `hackathon-tumai/`)
- `scripts/` — smoke scripts for DB, Gemini, Cognee
