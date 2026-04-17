# Agnes The Second

Evidence-grounded **raw material substitution** and **sourcing consolidation** for CPG procurement: ingest BOM and supplier data from SQLite, reason about substitutes with explicit uncertainty, and recommend consolidation with evidence trails (see [plan.md](plan.md)).

This repository is a hackathon MVP scaffold. **Phase 0** covers environment setup and connectivity checks; **Phase 1** adds schema + overlap analysis (no LLM).

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

## Phase 1 (data understanding)

From the repository root (with `data/raw/db.sqlite` present):

```bash
uv run python scripts/phase1_schema.py
uv run python scripts/phase1_overlap.py
```

Writes JSON/CSV under `outputs/reports/` (gitignored). Optional: open `notebooks/01_data_understanding.ipynb` or execute it with:

```bash
uv run jupyter nbconvert --to notebook --execute notebooks/01_data_understanding.ipynb --output /tmp/01_out.ipynb
```

## Project docs

- [plan.md](plan.md) — execution blueprint
- [Claude.md](Claude.md) — engineering conventions
- [Do_not_do.md](Do_not_do.md) — anti-patterns to avoid

## Layout

- `src/agnes/` — Python package (data loader, retrieval, graph, future modules)
- `data/raw/` — SQLite challenge database (not committed; copy from `hackathon-tumai/`)
- `scripts/` — Phase 0 smoke scripts; Phase 1 `phase1_schema.py` / `phase1_overlap.py`
- `notebooks/` — exploratory notebooks
- `outputs/reports/` — generated Phase 1 artifacts (not committed)
