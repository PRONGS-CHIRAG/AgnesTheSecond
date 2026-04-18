# Agnes The Second

Evidence-grounded **raw material substitution** and **sourcing consolidation** for CPG procurement: ingest BOM and supplier data from SQLite, reason about substitutes with explicit uncertainty, and recommend consolidation with evidence trails (see [plan.md](plan.md)).

This repository is a hackathon MVP scaffold. **Phase 0** covers environment setup and connectivity checks; **Phase 1** adds schema + overlap analysis (no LLM).

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` if needed)
- **OpenAI API key** (powers Phase 4 embeddings + Phases 5/6/7 `gpt-4o-mini`)
- **Tavily Search API key** (required by the Phase 5 `search_web` tool)

## Setup

```bash
uv sync --extra dev
cp .env.example .env
# Set AGNES_OPENAI_API_KEY and AGNES_TAVILY_API_KEY in .env

mkdir -p data/raw
cp hackathon-tumai/db.sqlite data/raw/db.sqlite
```

> **Upgrading from the Gemini build?** Delete the Phase 4–7 caches once:
> `rm -f .cache/phase4_embeddings.json .cache/phase5_evidence.json .cache/phase6_assessments.json .cache/phase7_recommendations.json`.
> Schema versions bumped from `v1` to `v2`, so stale on-disk entries would
> otherwise miss indefinitely.

## Verify (Phase 0 smoke tests)

From the repository root:

```bash
uv run python scripts/smoke_db.py
uv run python scripts/smoke_openai.py
uv run python scripts/smoke_cognee.py
uv run pytest -q
```

Expected `smoke_db` row counts (challenge DB): Company 61, Product 1025, BOM 149, BOM_Component 1528, Supplier 40, Supplier_Product 1633.

`smoke_openai` and `smoke_cognee` require a valid `AGNES_OPENAI_API_KEY` and network access (first Cognee run may download embedding models).

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

## Run the demo (Phase 8 UI)

Phase 8 ships a FastAPI transport layer that exposes Phase 2–7 artifacts (read) and runs
Phase 4/5/6/7 as subprocesses (write) plus a Next.js App Router frontend
(Dashboard / Opportunities / Materials / Runs) that consumes them.

```bash
# Terminal 1 — backend (http://localhost:8000)
uv sync --extra dev
uv run uvicorn agnes.api.main:app --reload --port 8000

# Terminal 2 — frontend (http://localhost:3000)
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Then visit http://localhost:3000 . The Dashboard surfaces the top consolidation
opportunity; the Runs console re-runs any phase with live log streaming and
auto-refreshes the rest of the UI on success. Docker is optional:

```bash
docker compose up --build       # backend + frontend, shared outputs/ volume
```

## Project docs

- [plan.md](plan.md) — execution blueprint
- [Claude.md](Claude.md) — engineering conventions
- [Do_not_do.md](Do_not_do.md) — anti-patterns to avoid

## Layout

- `src/agnes/` — Python package (data loader, retrieval, graph, agents, API)
- `src/agnes/api/` — FastAPI transport layer (artifact endpoints, run manager, SSE)
- `frontend/` — Next.js 15 App Router + Tailwind demo UI
- `data/raw/` — SQLite challenge database (not committed; copy from `hackathon-tumai/`)
- `scripts/` — Phase 0 smoke scripts + Phase 1–7 CLIs
- `notebooks/` — exploratory notebooks
- `outputs/reports/` — generated Phase 1–7 artifacts (not committed)
