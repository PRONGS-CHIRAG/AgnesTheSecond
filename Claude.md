# CLAUDE.md

## Project Purpose

This project is a **production-ready hackathon MVP** for a **multi-agent AI system** built with:
- **Claude Code** for implementation assistance
- **Cursor** for fast development
- **MCP / tool integrations**
- **Multi-agent orchestration**
- Strong emphasis on:
  - modularity
  - tool reliability
  - observability
  - fast iteration
  - demo-readiness
  - maintainability beyond the hackathon

The goal is **NOT** a toy prototype.
The goal is a **credible production-style MVP** that is:
- demoable
- testable
- extensible
- reasonably safe
- architecturally clean

---

## Core Development Philosophy

Always optimize for:

1. **Smallest production-worthy slice first**
2. **Vertical slices over broad unfinished systems**
3. **Tool reliability over fancy agent complexity**
4. **Deterministic flows where possible**
5. **Clear orchestration boundaries**
6. **Minimal context waste**
7. **Readable code over clever code**
8. **Fast shipping without creating architectural debt that blocks demo or post-hackathon continuation**

When in doubt:
- choose the **simpler design**
- prefer **1 strong agent workflow** over **many weak agents**
- prefer **tool contracts + schemas** over free-form prompting
- prefer **observable state transitions** over hidden magic

---

## Expected Stack (Default Assumption)

Unless the user explicitly says otherwise, assume:

### Backend / Intelligence Layer
- Python 3.11+
- FastAPI
- Pydantic v2
- Async-first design where useful
- SQLAlchemy 2.0 (if DB needed)
- Alembic (if persistent DB migrations needed)
- Pytest for tests
- Structured logging
- Environment-based configuration
- Tool wrappers / MCP clients as isolated modules

### Frontend / Product Layer
- Next.js (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui (if needed)
- Clean, production-style UI
- Minimal but polished UX
- Strong loading / error / empty states

### Infra / Runtime
- Docker or docker-compose if useful
- `.env.example`
- clear setup commands
- health check endpoints
- reproducible local run

---

## Architecture Rules

### High-Level Principle
Separate:
- **Product layer** (UI / API routes / interaction surfaces)
- **Intelligence layer** (agents / tools / orchestration / reasoning)
- **Infrastructure layer** (config / storage / logging / adapters)

### Required Separation
Keep these concerns separate:

- `agents/` → agent logic, role prompts, orchestration entrypoints
- `tools/` → all tool wrappers and MCP integrations
- `schemas/` → Pydantic / TS types / request-response contracts
- `services/` → deterministic business logic
- `api/` or `app/api/` → transport layer only
- `storage/` or `db/` → persistence
- `prompts/` → reusable prompt templates (if prompt-heavy)
- `tests/` → tests mirroring core logic

### Never mix:
- agent reasoning logic directly inside route handlers
- tool calling logic directly inside UI components
- business logic inside prompt strings
- parsing logic scattered across files
- hidden side effects in “utility” functions

---

## Multi-Agent System Standards

### Default Multi-Agent Philosophy
Use multi-agent only when there is a **clear role separation**.

Good reasons:
- planner vs executor
- retrieval vs synthesis
- tool selection vs domain reasoning
- verifier / critic / guardrail agent
- domain-specialized agents

Bad reasons:
- “because multi-agent sounds cool”
- duplicating the same LLM call under different names
- agent chains that are not observable or measurable

### Default Agent Pattern
Prefer this shape:

1. **Router / Planner Agent**
   - understands user goal
   - selects workflow
   - chooses tools or sub-agents
   - produces structured plan

2. **Specialist / Executor Agent(s)**
   - perform bounded tasks
   - use explicit tools
   - return structured outputs

3. **Verifier / Critic / Safety Check (optional but recommended)**
   - validates schema
   - checks completeness
   - checks confidence / contradictions / missing evidence

4. **Final Response Composer**
   - deterministic formatting where possible
   - clear user-facing answer
   - cites tool results if available

### Strong Preference
If possible:
- use **1 orchestrator + 1–3 specialists max** for hackathon scope
- avoid >4 agents unless there is a strong reason

---

## Tool & MCP Standards

### All tools must:
- have **clear input schemas**
- have **clear output schemas**
- fail gracefully
- return structured results
- expose meaningful errors
- be testable independently
- be wrapped in reusable adapter modules

### Tool calling rules
- Never let agents call raw external APIs directly from arbitrary code
- Always route through:
  - `tools/`
  - `mcp/`
  - adapter wrappers
- Normalize all tool outputs before passing to downstream agents

### MCP rules
- Treat MCP servers as **external dependencies**
- Add timeout handling
- Add retries only where safe
- Log failures with useful context
- Validate responses before trust
- Never assume MCP output is correct or complete

### If a tool is flaky:
- degrade gracefully
- fallback to partial response
- explicitly surface uncertainty
- do not silently hallucinate missing data

---

## Context Management Rules (Very Important)

Claude Code and Cursor must preserve context efficiency.

### Always do this first
Before reading many files:
1. Identify likely relevant files
2. Read only the minimum set
3. Ask for / infer the exact vertical slice
4. Avoid repo-wide scanning unless truly necessary

### Use graph / repo map first if available
If a knowledge graph, graph report, or architecture map exists:
- read that first
- use it to identify relevant files
- do not read the entire repo unnecessarily

### Session discipline
Each session should focus on **one coherent objective**:
- one feature slice
- one bug
- one refactor
- one integration
- one demo flow

### End-of-session ritual
At the end of a session, update a short handoff note containing:
- current objective
- what was completed
- files changed
- open issues
- next exact step

### When context gets noisy
- summarize before continuing
- compact state mentally
- prefer “continue from this summary” over dragging long stale context

### Never:
- repeatedly re-open the same large files unless needed
- scan the entire repo for a narrow task
- keep multiple unrelated tasks in the same long thread
- perform broad speculative refactors mid-feature

---

## Coding Standards (Backend)

### Python Standards
- Python 3.11+
- Type hints required for public functions
- Prefer small, composable functions
- Prefer explicit return types
- Use Pydantic models for request/response and internal contracts where useful
- Use async only when it provides real benefit
- Avoid over-abstracting too early

### API Standards
- FastAPI routes should be thin
- Route handlers should:
  - validate input
  - call service / orchestrator layer
  - return structured responses
- Never embed large business logic in route handlers

### Error Handling
- No bare `except`
- Catch specific exceptions
- Return actionable error messages
- Log enough to debug, but never leak secrets
- Distinguish:
  - user errors
  - tool errors
  - infra errors
  - LLM orchestration errors

### Logging
Use structured logs for:
- request start/end
- tool calls
- MCP calls
- agent transitions
- retries / fallbacks
- failures
- latency hotspots

### Validation
- Validate all external tool outputs
- Validate agent structured outputs
- Reject malformed data early
- Fail closed rather than silently accepting broken data

---

## Coding Standards (Frontend)

### TypeScript / Next.js
- Strict TypeScript mindset
- Avoid `any` unless absolutely unavoidable
- Prefer typed API clients
- Prefer server actions / route handlers / clean API boundaries depending on project need
- UI components should be presentational where possible

### UI Rules
- Every async action must have:
  - loading state
  - error state
  - empty state
  - success state
- Demo flow must be obvious within 1–2 clicks
- Avoid cluttered dashboards unless essential

### UX for Hackathon
Optimize for:
- “wow in 30 seconds”
- obvious value proposition
- clean primary workflow
- visible trust signals
- visible evidence / reasoning when relevant

---

## File & Folder Conventions

Suggested default structure:

```text
project/
├─ app/ or frontend/
├─ backend/
│  ├─ api/
│  ├─ agents/
│  ├─ tools/
│  ├─ mcp/
│  ├─ services/
│  ├─ schemas/
│  ├─ db/
│  ├─ core/
│  └─ tests/
├─ docs/
├─ prompts/
├─ scripts/
├─ session-notes/
├─ .env.example
├─ docker-compose.yml (if used)
├─ README.md
└─ CLAUDE.md

---

## Current Build State

### Phase 0: Complete

**Package manager:** `uv` with `pyproject.toml` (Python 3.11+). Run `uv sync --extra dev` to install.

**What was built:**

- `src/agnes/` Python package (editable install via `uv`):
  - `config/settings.py` — Pydantic v2 `BaseSettings`, `AGNES_` env prefix, reads `.env`
  - `data/db_loader.py` — `get_engine()` + `ping()` (returns row counts for 6 core tables)
  - `retrieval/google_cloud_client.py` — Gemini API ping via `google-genai` SDK
  - `graph/cognee_client.py` — Cognee `add + cognify` smoke with local store (LiteLLM Gemini, FastEmbed `BAAI/bge-small-en-v1.5`)
  - `utils/logging.py` — structlog setup
  - `models/` — entity + report + canonical + graph Pydantic models (Phases 1–3); still-empty: `substitutes/`, `reasoning/`, `optimization/`, `ui/`
- `scripts/smoke_db.py`, `smoke_gemini.py`, `smoke_cognee.py` — one-liner JSON output, exit 0/1
- `tests/test_smoke.py` — import + settings tests (no network required)
- `data/raw/db.sqlite` — copied from `hackathon-tumai/db.sqlite` (gitignored)
- `.env.example` — all `AGNES_` keys documented
- `README.md` — setup and verify steps

**Confirmed DB row counts:** Company 61 / Product 1025 / BOM 149 / BOM\_Component 1528 / Supplier 40 / Supplier\_Product 1633.

### Phase 1: Complete

**Purpose:** Understand the challenge DB — schema introspection, typed relational queries, entity counts, repeated raw materials (threshold on `n_companies`), supplier fragmentation (distinct suppliers per raw).

**What was built:**

- `src/agnes/data/queries.py` — `load_*`, `raw_material_usage`, `raw_material_suppliers`, `company_product_tree`, `entity_counts`
- `src/agnes/data/schema_summary.py` — `build_schema_summary()` via SQLAlchemy `inspect()`
- `src/agnes/services/overlap.py` — `compute_repeated_materials`, `compute_supplier_fragmentation`, `build_phase1_report`, `classify_concentration`
- `src/agnes/models/entities.py`, `reports.py` — row + report Pydantic models
- `scripts/phase1_schema.py` → `outputs/reports/schema_summary.json`
- `scripts/phase1_overlap.py` → `entity_counts.json`, `repeated_raw_materials.csv`, `supplier_fragmentation.csv`, `phase1_report.json` (generated files gitignored)
- `notebooks/01_data_understanding.ipynb` — same metrics as scripts
- `tests/test_queries.py`, `tests/test_overlap.py`

**Data note:** In this SQLite, each raw `Product.Id` appears in BOMs for finished goods from **one company only** (`n_companies` == 1 everywhere); cross-company overlap is a Phase 2 canonicalization concern. Supplier fan-out is meaningful: many raws have 2 suppliers (`fragmented`).

### Phase 2: Complete

**Purpose:** Deterministic SKU parse + `canonical_key` for every raw-material `Product` row; one batched Gemini structured call per uncached canonical key to assign `ingredient_family` and `functional_role` from a fixed taxonomy; versioned cache at `.cache/phase2_family_role.json` (keyed by `TAXONOMY_VERSION`, currently `v1`).

**What was built:**

- `src/agnes/canonicalization/taxonomy.py` — `FAMILIES`, `ROLES`, `TAXONOMY_VERSION`
- `src/agnes/canonicalization/text_cleaning.py` — `parse_sku`, `normalize_name`, `canonical_key`
- `src/agnes/canonicalization/canonicalizer.py` — `build_canonical_materials(engine)` over raw materials only
- `src/agnes/canonicalization/role_classifier.py` — `assign_family_role`, `count_cache_hits`, `.cache/phase2_family_role.json` read/write
- `src/agnes/models/canonical.py` — `CanonicalMaterial`, `FamilyRoleAssignment`, `FamilyRoleBatchResponse`, `CanonicalRegistry`
- `src/agnes/retrieval/gemini_structured.py` — `generate_structured` (JSON + Pydantic schema, one retry on validation failure, `StructuredOutputError`)
- `prompts/family_role.md` — taxonomy-constrained prompt template (no long prompts in Python)
- `scripts/phase2_canonicalize.py` → `outputs/reports/canonical_registry.json`, `canonical_registry.csv` (gitignored like other reports)
- `tests/test_text_cleaning.py`, `tests/test_canonicalizer.py` (876 raw rows), `tests/test_role_classifier.py` (cache-only, monkeypatched Gemini)

**Coverage model (registry):** `coverage` counts `assigned` (no `llm_error` in `missing_info`), `unassigned` (parse ok but batch/LLM fallback), `parse_failed` (`parse_ok=False`).

### Phase 3: Complete

**Purpose:** Deterministic knowledge graph from `CanonicalRegistry` + SQLite: typed `KGNode` / `KGEdge`, ingest into Cognee dataset `agnes_kg_v1` (`GRAPH_SCHEMA_VERSION`), and a pure-Python `MaterialGraphIndex` for Phase 4 queries (no Cognee read path required).

**What was built:**

- `src/agnes/graph/schema.py` — `NodeKind`, `EdgeKind`, `GRAPH_SCHEMA_VERSION`, `DATASET_NAME`
- `src/agnes/models/graph.py` — `KGNode`, `KGEdge`, `GraphIngestReport`, query ref types
- `src/agnes/graph/builder.py` — `build_graph_payload`, `count_by_kind`
- `src/agnes/graph/cognee_ingest.py` — `ingest_graph` (batched JSONL via `cognee.add` + `cognify`; optional `--reset` empties existing dataset by name)
- `src/agnes/graph/queries.py` — `MaterialGraphIndex`, `suppliers_for_material`, `materials_in_family`, `companies_using_family`, `neighbors_of_material`
- `src/agnes/graph/cognee_client.py` — public `configure_cognee()` (shared with ingest)
- `scripts/phase3_graph_ingest.py` → `outputs/reports/graph_ingest_report.json` (gitignored); `scripts/phase3_graph_query.py` — canned queries over the in-memory index
- `tests/test_graph_builder.py`, `tests/test_graph_queries.py`

**Idempotence:** Stable node ids (`Company:<id>`, `CanonicalMaterial:<canonical_key>`, etc.); re-running `build_graph_payload` with the same inputs yields identical sorted node/edge lists. Cognee store lives under `.cognee_data/` (gitignored).

**Next phase:** Phase 4 — substitute candidate generation using `MaterialGraphIndex` + embeddings.
### Phase 4: Complete

**Purpose:** For any raw material (or `CanonicalMaterial`), produce a deterministic, multi-signal ranked list of substitute candidates over the Phase 2 `CanonicalRegistry` and the Phase 3 `MaterialGraphIndex`. Signals are combined through an explainable weighted composite score (`SUBSTITUTES_SCHEMA_VERSION = "v1"`); no free-form LLM reasoning is used in the ranking loop.

**Design rules:**

- Deterministic first, LLM later: graph + lexical filters prune; embeddings only rerank; LLM context reasoning is deferred to Phase 6.
- Family-scoped by default: candidates drawn from within the target's `IngredientFamily` (with `FunctionalRole` tracked as a feature); cross-family searches require `--cross-family` or `AGNES_PHASE4_CROSS_FAMILY_DEFAULT=true`.
- Stable cache: embeddings cached on disk at `.cache/phase4_embeddings.json`, keyed by `(model, canonical_key)`; reruns are idempotent and network-free once warm.
- No Cognee read path — operates entirely on `CanonicalRegistry` + in-memory `MaterialGraphIndex` + SQLite.

**What was built:**

- `src/agnes/models/substitutes.py` — `CandidateFeatures`, `SubstituteCandidate`, `TargetDiagnostics`, `SubstituteCandidateReport` (Pydantic, frozen, `extra="forbid"`)
- `src/agnes/substitutes/features.py` — pure signal functions: `lexical_sim` (Jaccard on canonical-key tokens), `family_match`, `role_match`, `supplier_overlap`, `co_company_overlap`, `compute_features` (also records `missing_signals`)
- `src/agnes/substitutes/embeddings.py` — `GeminiEmbeddingClient` with `google-genai` backend, on-disk JSON cache, batched `get_batch`, and an `EmbeddingBackend` Protocol for tests
- `src/agnes/substitutes/scoring.py` — `DEFAULT_WEIGHTS` (`family=0.30`, `role=0.15`, `embed=0.35`, `lexical=0.10`, `supplier_overlap=0.10`), `score_candidate` with `MISSING_SIGNAL_PENALTY=0.05` and `[0,1]` clamp
- `src/agnes/substitutes/candidate_generator.py` — `generate_candidates(target_key, registry, graph_index, embeddings, *, top_k, min_score, cross_family, weights)` returning `(list[SubstituteCandidate], TargetDiagnostics)` with structured logs
- `scripts/phase4_candidates.py` → `outputs/reports/substitute_candidates.json` + `substitute_candidates.csv` (gitignored); CLI flags `--target/--all/--top-k/--min-score/--cross-family/--dry-run/--no-cache`
- `src/agnes/config/settings.py` — new keys `phase4_top_k`, `phase4_min_score`, `phase4_weights` (JSON), `phase4_embedding_model`, `phase4_cross_family_default`; `.env.example` updated with `AGNES_PHASE4_*`
- `tests/test_features.py`, `tests/test_scoring.py`, `tests/test_candidate_generator.py` — unit + end-to-end coverage (stubbed embedding backend, no network)

**Coverage model (report):**

- `with_candidates`: at least one in-family candidate scored above `min_score`.
- `without_candidates`: `reason ∈ {no_family, singleton_family, all_below_threshold}`.
- Per-target diagnostics: `n_pool`, `n_after_filter`, `n_returned`, `best_score`.

**Idempotence:** Feature functions are pure on `(CanonicalRegistry, MaterialGraphIndex)`; embedding cache is content-keyed by `(model, canonical_key)`; given the same inputs, weights, and model id the ranked list is byte-stable (asserted in tests).

**Observability:** Structured logs per target (`phase4_target_start`, `phase4_pool_filtered`, `phase4_target_ok`, `phase4_target_empty` with reason) plus a final run summary printed to stdout.

**Next phase:** Phase 5 — external evidence enrichment for top-N `SubstituteCandidate`s (public sources, provenance-tracked claims).

### Phase 5: Complete

**Purpose:** Enrich the top Phase 4 `SubstituteCandidate`s with citation-backed external evidence using Gemini with the `google_search` grounding tool. Each (source, candidate) pair yields a typed `SubstituteEvidence` with up to six structured `EvidenceClaim`s (`functional_equivalence`, `certification`, `regulatory`, `typical_suppliers`, `quality_sensory`, `price_availability`), each carrying `polarity`, `confidence`, `citations[]`, and `grounding_strength` (`grounded` vs `parametric`). `EVIDENCE_SCHEMA_VERSION = "v1"`.

**Design rules:**

- Deterministic plumbing + grounded extraction: selector, cache, aggregation are pure; only the grounded LLM call is non-deterministic.
- Reuses existing stack: `google-genai` + `types.Tool(google_search=...)`. No new dependencies. The Gemini API does not allow `google_search` and `response_schema` together, so the adapter asks the model to return raw JSON in the prompt and parses + Pydantic-validates with one retry.
- Provenance first: every claim carries `citations: list[CitationRef]`; claims without citations are kept but flagged `grounding_strength="parametric"`. The prompt forbids inventing URLs.
- Explicit budgets: `--top-sources`, `--per-source`, `--max-total` default-low; when `max_total` is tripped the run records `partial=True` without mutating the cache for unseen pairs.
- Disk cache at `.cache/phase5_evidence.json` keyed by `(source_key, candidate_key, gemini_model, EVIDENCE_SCHEMA_VERSION)`; reruns are idempotent and network-free once warm.
- No Cognee write path in Phase 5 (evidence is persisted into memory in Phase 6/7 once LLM verdicts exist).

**What was built:**

- `src/agnes/models/evidence.py` — `CitationRef`, `EvidenceClaim`, `SubstituteEvidence`, `SubstituteEvidenceLLM`, `EvidenceReport`, `EVIDENCE_SCHEMA_VERSION` (all `extra="forbid"`, frozen where safe)
- `src/agnes/retrieval/gemini_grounded.py` — `GroundedBackend` Protocol, `GoogleGroundedBackend` (real SDK), `GroundedLLM` (parses JSON from free-text grounded response, one retry, raises `GroundedExtractionError`), `parse_citations` (handles both Pydantic-like and dict grounding metadata, dedupes by URL, stamps `retrieved_at`)
- `src/agnes/evidence/enricher.py` — `select_pairs` (best-score-first source order, per-source truncation, optional single-source filter), `EvidenceCache` (JSON on disk, schema-versioned keys), `load_prompt_template` / `render_prompt` (`string.Template` with `$var` placeholders), `enrich_pairs` (budget, cache, failure counting, structured logs)
- `prompts/evidence_extraction.md` — taxonomy-constrained, rich-claim prompt template that instructs the model to cite primary sources and never fabricate URLs
- `scripts/phase5_evidence.py` → `outputs/reports/substitute_evidence.json` + `substitute_evidence.csv` (one row per claim for spreadsheet review); CLI flags `--top-sources/--per-source/--max-total/--source/--model/--prompt/--cache-path/--no-cache/--dry-run`
- `src/agnes/config/settings.py` — new keys `phase5_top_sources` (5), `phase5_per_source` (3), `phase5_max_total` (25), `phase5_grounded_model` (`gemini-2.5-flash`); `.env.example` updated with `AGNES_PHASE5_*`
- `tests/test_evidence_models.py`, `tests/test_enricher_selector.py`, `tests/test_enricher.py`, `tests/test_gemini_grounded.py` — schema round-trips, selector ordering, offline end-to-end enrichment with stub backend (asserts cache hit on rerun, `partial=True` at budget, `any_contradictions` derivation, failure counting), and grounded adapter JSON/citation parsing + retry behavior

**Coverage model (report):**

- `n_pairs`: pairs selected by `select_pairs`.
- `n_cache_hits` / `n_api_calls`: disjoint; `n_failures` counts pairs where grounded extraction failed after retries (report still emitted without an item for that pair).
- `partial`: `True` iff `max_total` tripped before all uncached pairs were processed.
- Per item: `n_citations` (sum across claims), `any_contradictions` (any claim with `polarity="contradicts"`).

**Idempotence:** Pure `select_pairs`; `EvidenceCache` keyed by `(source, candidate, model, schema_version)`. Given the same Phase 4 report, template, and model id, the second run returns `n_api_calls=0` and `n_cache_hits=n_pairs` (asserted in tests).

**Observability:** Structured logs per pair (`phase5_pair_start`, `phase5_cache_hit`, `phase5_grounded_call`, `phase5_pair_ok`, `phase5_pair_failed`, `phase5_budget_exhausted`) plus a single-line run summary on stdout. No PII or secrets in logs.

**Next phase:** Phase 6 — context and compliance reasoning over `SubstituteEvidence` to produce typed `SubstituteAssessment` verdicts with `recommendation_class`, `missing_information`, and uncertainty surfacing.
