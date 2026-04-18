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

**Verified (run log, 2026-04-18):** End-to-end check of `scripts/phase5_evidence.py` with inputs `outputs/reports/substitute_candidates.json` and `outputs/reports/canonical_registry.json`. Offline: 27 tests passed (`test_evidence_models`, `test_enricher_selector`, `test_enricher`, `test_gemini_grounded`). Dry-run (`--top-sources 1 --per-source 3 --max-total 0 --dry-run`) selected three pairs for source `calcium-citrate` → `magnesium-citrate`, `calcium-carbonate`, `dicalcium-phosphate`. Live pass with `gemini-2.5-flash`: `n_pairs=3`, warm cache yielded `n_cache_hits=3`, `n_api_calls=0`, `n_failures=0`, `partial=false`; all 18 claims `grounding_strength=grounded` with Gemini grounding citations; `magnesium-citrate` item `any_contradictions=true` (mixed functional equivalence vs calcium citrate). Outputs: `outputs/reports/substitute_evidence.json`, `substitute_evidence.csv`; idempotent rerun confirmed `n_api_calls=0`. First grounded runs can be slow; reruns are network-free once `.cache/phase5_evidence.json` is warm.

**Next phase:** Phase 6 — context and compliance reasoning over `SubstituteEvidence` to produce typed `SubstituteAssessment` verdicts with `recommendation_class`, `missing_information`, and uncertainty surfacing.

### Phase 6: Cognee Cloud Integration

**Purpose:** Replace the local Cognee + LiteLLM + FastEmbed stack with a managed Cognee Cloud integration so the knowledge graph (Phase 3 payload) is persisted, queryable, and shareable out-of-box, without running a local vector store or LLM proxy.

**Design rules:**

- Cloud-only: no dual backend, no `.cognee_data/` fallback. A missing API key fails fast.
- Single dependency: the official `cogwit-sdk` (`>=0.1.7`). `cognee` and `fastembed` are removed from `pyproject.toml`.
- Deterministic fact serialization: Phase 3 `KGNode` / `KGEdge` objects are rendered into a stable list of English sentences (`Node X is a Kind. with attributes k=v.` / `src EDGE_KIND dst.`) so Cognee Cloud cognify receives the same structure every run. Sentences preserve the sort order already imposed by `build_graph_payload`.
- Thin async wrapper over the SDK; structured errors raise `CognneCloudError` instead of leaking SDK `*Error` variants. Callers don't branch on response shape.
- Env-var parity: the wrapper honors both `AGNES_COGWIT_API_KEY` (preferred) and the SDK-native `COGWIT_API_KEY`; `AGNES_COGWIT_BASE_URL` is re-exported as `COGWIT_API_BASE` so the SDK picks it up.

**What was built:**

- `src/agnes/graph/cognee_cloud_client.py` — `build_cogwit`, `serialize_graph`, `CognneCloudClient` (`add_text`, `add_graph` with batching, `cognify`, `search`, `ping`), `CognneCloudError`, and a sync `ping(settings)` helper for CLI use.
- `scripts/cognee_cloud_ingest.py` — CLI that loads `CanonicalRegistry`, rebuilds the Phase 3 payload, uploads it to Cognee Cloud via `add_graph`, runs `cognify`, and optionally verifies with a `GRAPH_COMPLETION` search. Writes `outputs/reports/cognee_cloud_ingest.json` (dataset id + counts + latencies + cogwit SDK version + search preview). Supports `--limit`, `--batch-size`, `--fresh` (timestamped dataset), `--skip-cognify`, `--verify-query`.
- `scripts/smoke_cognee.py` — now points at the cloud client; `{"ok": true, "dataset_id": ...}` round-trip through `api.cognee.ai`.
- `src/agnes/config/settings.py` — added `cogwit_api_key`, `cogwit_dataset` (default `agnes`), `cogwit_base_url`; removed `cognee_llm_provider` and `cognee_data_root`.
- `.env.example` — added `AGNES_COGWIT_API_KEY`, `AGNES_COGWIT_DATASET`, commented `AGNES_COGWIT_BASE_URL`; removed `AGNES_COGNEE_DATA_ROOT`.
- `pyproject.toml` — swapped `cognee>=0.3` for `cogwit-sdk>=0.1.7`, removed `fastembed`.
- `tests/test_cognee_cloud_client.py` — offline coverage via a stubbed `cogwit` instance (`AsyncMock`): deterministic `serialize_graph`, API-key resolution precedence, missing-key short-circuit, `add_text` dispatch, `add_graph` batching + dataset-id reuse, error-variant detection, and `ping` happy/error paths. `tests/test_smoke.py` updated to import the new module.

**Observability:** Structured logs per operation (`cogwit.add_text`, `cogwit.add_graph.batch`, `cogwit.cognify`, `cogwit.search`). No secrets in logs.

**Idempotence:** Reruns against the same `AGNES_COGWIT_DATASET` append-update the existing dataset. `--fresh` appends a UTC timestamp to the dataset name for a clean slate (the SDK currently has no delete primitive).

**Next phase:** Phase 7 — context and compliance reasoning over `SubstituteEvidence` (originally framed as Phase 6) plus wiring Cognee Cloud search into the evidence/recommender loop.

### Phase 6 (plan): Context and Compliance Reasoning — Complete

**Purpose:** Turn Phase 5 `SubstituteEvidence` into typed `SubstituteAssessment` verdicts, one per `(company_id, finished_product_id, source_key, candidate_key)` tuple. Each verdict carries a `recommendation_class` (`recommend | recommend_with_caveats | do_not_recommend | insufficient_evidence`), a deterministic `acceptability` score in `[0,1]`, explicit `contradictions`/`missing_information` claim keys, and a `rationale` + `caveats` for downstream UI. `ASSESSMENT_SCHEMA_VERSION = "v1"`.

> Note: The codebase already shipped a separate "Phase 6: Cognee Cloud Integration" section above. The plan file numbers this work as Phase 6 ("Context and compliance reasoning"); we keep both sections to preserve history, and this section is the one Phase 7 (recommendation engine) consumes.

**Design rules:**

- Rules-first, LLM-only-if-needed: a deterministic scorer over Phase 5 claims decides most tuples. Gemini's structured-output mode is only called for *borderline* tuples (`recommend_with_caveats`, high-weight contradictions, or missing regulatory/certification).
- Pure deterministic core: `aggregate_claims`, `score_acceptability`, `classify` have no I/O, no clock, no LLM — they are safe to test exhaustively and rerun under new weights without touching the cache.
- Per (company, product) expansion: the same (source, candidate) pair is assessed once per finished-good that actually consumes the source. Context expansion joins `company_product_tree` (BOM joins) against the canonical registry's `raw_product_id`s; sources with zero BOM rows produce zero tuples by design.
- Budgeted LLM fallback: `max_llm_calls` caps *new* structured calls per run. LLM failures fall back to the rules verdict and bump `n_failures`; cache entries are discriminated by `"rules"` vs the Gemini model id so toggling the LLM path is safe.
- Disk cache at `.cache/phase6_assessments.json` keyed by `(company_id, finished_product_id, source_key, candidate_key, model_or_rules, ASSESSMENT_SCHEMA_VERSION)`; changing weights/thresholds/model id cleanly invalidates old entries.
- No new dependencies; no `google_search` tool for Phase 6 (we reason over Phase 5 citations rather than doing fresh web lookups).

**What was built:**

- `src/agnes/models/assessment.py` — `ASSESSMENT_SCHEMA_VERSION`, `RecommendationClass`, `DecisionPath`, `AssessmentContext`, `SubstituteAssessment`, `SubstituteAssessmentLLM`, `AssessmentReport` (all `extra="forbid"`, frozen where it makes sense).
- `src/agnes/reasoning/context.py` — `expand_context(registry, engine, evidence_report, candidates_report=None, usage_df=None)` fans each Phase 5 pair out to `(company_id, finished_product_id)` tuples via `company_product_tree`; dedups duplicate BOM rows; sorts stably; `usage_df` hook keeps tests DB-free.
- `src/agnes/reasoning/rules.py` — `RulesConfig`, `ClaimAggregate`, `aggregate_claims`, `score_acceptability`, `classify`, `deterministic_rationale`. Per-claim contribution = `confidence × grounding_multiplier × polarity_factor`; keyed weights default to `{functional_equivalence:0.35, regulatory:0.25, certification:0.15, quality_sensory:0.10, price_availability:0.10, typical_suppliers:0.05}`; acceptability = weighted mean of `clip(support - contradict)` over observed keys.
- `src/agnes/reasoning/llm_fallback.py` — `StructuredBackend` Protocol, `GoogleStructuredBackend` (real `google-genai`, `response_mime_type="application/json"`, no tools), `StructuredLLM.assess` (parse JSON, Pydantic-validate into `SubstituteAssessmentLLM`, one retry, raises `AssessmentLLMError`), plus `claims_to_json` / `render_prompt` helpers.
- `src/agnes/reasoning/assessor.py` — `AssessmentCache` (schema- + model-scoped) and `assess_contexts(...)` orchestrator with budgets, per-tuple structured logs (`phase6_tuple_start`, `phase6_rules_decision`, `phase6_llm_call`, `phase6_llm_ok`, `phase6_llm_failed`, `phase6_cache_hit`, `phase6_budget_exhausted`), and a `partial` flag when budget trips an otherwise-borderline tuple.
- `prompts/assessment.md` — `string.Template` with `$company`, `$product`, `$source_key`, `$candidate_key`, `$source_name`, `$candidate_name`, `$claims_json`, `$rules_summary`; forbids fabrication and restricts outputs to the `SubstituteAssessmentLLM` schema.
- `scripts/phase6_assess.py` → `outputs/reports/substitute_assessments.json` + `substitute_assessments.csv` (one row per tuple). CLI flags: `--evidence/--candidates/--registry/--max-llm-calls/--model/--prompt/--cache-path/--no-cache/--dry-run/--source/--company`.
- `src/agnes/config/settings.py` — added `phase6_claim_weights` (JSON), `phase6_accept_threshold=0.75`, `phase6_reject_threshold=0.35`, `phase6_min_grounded_claims=2`, `phase6_max_llm_calls=25`, `phase6_llm_model="gemini-2.5-flash"`; `.env.example` mirrors as `AGNES_PHASE6_*`.
- `tests/test_assessment_models.py`, `tests/test_reasoning_rules.py`, `tests/test_reasoning_context.py`, `tests/test_llm_fallback.py`, `tests/test_reasoning_assessor.py` — schema round-trips + enum validation, monotonicity and threshold tests for the scorer, context expansion (fan-out, sort stability, dedup, empty-usage short-circuit), structured LLM parse/retry/fail, and end-to-end assessor (rules-only path, borderline→LLM merge, cache hit on rerun, budget exhaustion → `partial=True`, LLM failure → rules fallback + `n_failures`, dry-run suppresses calls, missing evidence → `insufficient_evidence`). 29 new tests, all green.

**Coverage model (report):**

- `n_tuples`: number of `(company, product, source, candidate)` assessments produced (after `expand_context`).
- `n_rules_decisions` + `n_llm_decisions`: disjoint counts of verdict paths actually emitted.
- `n_cache_hits`: tuples served directly from `.cache/phase6_assessments.json`; disjoint from `n_api_calls`.
- `n_api_calls`: *new* structured LLM calls; capped by `max_llm_calls`.
- `n_failures`: LLM failures that fell back to the rules verdict.
- `n_without_evidence`: tuples with no matching Phase 5 pair (scored as `insufficient_evidence`).
- `counts_by_class`: histogram by `RecommendationClass`.
- `partial`: `True` iff budget tripped an otherwise-borderline tuple.

**Idempotence:** `aggregate_claims` / `score_acceptability` / `classify` are pure functions of `(evidence, weights, thresholds)`. Cache keys embed `ASSESSMENT_SCHEMA_VERSION` and the model id, so reruns with the same Phase 5 inputs and settings return `n_api_calls=0` and `n_cache_hits=n_tuples` (asserted in `test_cache_hit_on_rerun`). Changing weights/thresholds forces the cache line to miss (rules verdicts are cached under the `"rules"` discriminator; borderline paths under the Gemini model id).

**Observability:** Structured logs per tuple under `phase6_*`, plus a single-line JSON run summary on stdout. No secrets or PII in logs; long error strings truncated to 200 chars.

**Next phase:** Phase 7 — recommendation engine that ranks assessments by `acceptability × substitute_score × sourcing-benefit` and emits procurement-ready tables; optionally writes top verdicts back into Cognee Cloud memory for cross-session reuse.

---

## Phase 7: Recommendation Engine — Complete

**Purpose:** turn Phase 6 `SubstituteAssessment`s into business-shaped `SourcingRecommendation`s: a deterministic sourcing-benefit scorer joins supplier data with each `(company, product, source, candidate)` tuple, combines it with Phase 6 acceptability and Phase 4 substitute score, produces a per-tuple ranked table, then rolls up to one `ConsolidationOpportunity` per `source_key`. An optional Gemini structured-output pass polishes the `tradeoff_summary` for the top-N rollup rows under a budget with disk caching. Scoring + rollup are pure; only the optional polish is non-deterministic.

**Design rules honored:**

- Deterministic scoring first (pure functions, no LLM): the report is demo-stable even with Gemini off.
- Phase 6 verdicts veto numerics: `do_not_recommend` / `insufficient_evidence` short-circuit the grade regardless of sourcing benefit.
- Every LLM call is budgeted and cached; cache keys embed `RECOMMENDATION_SCHEMA_VERSION` + model id so changing settings or model invalidates by intent.
- Sparse-data graceful: when the DB has no supplier rows for a side, `sourcing_benefit` returns a neutral `0.5` and `missing_signals=["no_supplier_data"]` is surfaced.
- CSVs surface the raw signals (supplier counts, overlaps, shared supplier ids) so reviewers can eyeball the score.

**What was built:**

- `src/agnes/models/recommendation.py` — `RECOMMENDATION_SCHEMA_VERSION`, frozen `SourcingSignals`, `SourcingRecommendation`, `ConsolidationOpportunity`, plus `RecommendationReport` (counts, budgets, weights, thresholds, `counts_by_grade`, `partial`, duration_ms, items + opportunities).
- `src/agnes/data/queries.py` — added `supplier_products_by_company(engine)` (Company → finished Product → BOM → raw → Supplier_Product join). Other queries untouched.
- `src/agnes/recommendation/signals.py` — `SupplierIndex` dataclass and `build_supplier_index(registry, suppliers_df, company_df)` / `compute_signals(index, …)` for per-`(company, source, candidate)` structural signals (counts, shared suppliers, company-level overlap, concentration_relief).
- `src/agnes/recommendation/scorer.py` — `SourcingWeights` (`diversification=0.40`, `company_overlap=0.35`, `concentration_relief=0.25`), `FinalScoreConfig` (`α_accept=0.55`, `α_substitute=0.25`, `α_sourcing=0.20`), `GradeThresholds` (`safe=0.70`, `reject=0.30`), `sourcing_benefit`, `final_score` (handles `None` substitute_score by redistributing its weight), and `map_grade` (Phase 6 veto + high-weight-contradiction downgrade + `review_required`).
- `src/agnes/recommendation/builder.py` — `build_rows` produces one `SourcingRecommendation` per assessment (passes Phase 6 citations + caveats through unchanged, emits a deterministic `tradeoff_summary`, risk notes), `rollup_opportunities` groups by `source_key`, picks the best candidate by `sum(final_score × acceptability)`, aggregates products/companies covered, unions supplier lists, and surfaces the worst per-row grade to stay demo-conservative.
- `src/agnes/recommendation/llm_polish.py` — `SummaryLLMResponse` Pydantic contract (`tradeoff_summary` + `risk_notes`), `StructuredBackend` Protocol, `GoogleStructuredBackend` (`response_mime_type="application/json"`, no tools), `SummaryLLM.polish` (parse JSON, Pydantic-validate, one retry, raises `RecommendationLLMError`). The LLM never changes grades, suppliers, or scores — polish-only.
- `prompts/recommendation_polish.md` — `string.Template` with `$source_name`, `$candidate_name`, `$grade`, `$acceptability`, `$sourcing_benefit`, `$current_suppliers`, `$recommended_suppliers`, `$caveats`, `$contradictions`; forbids fabrication and ties the summary to supplied context.
- `src/agnes/recommendation/engine.py` — `RecommendationCache` (schema- + model-scoped JSON on disk) and `generate_report(...)` orchestrator: ranks opportunities by `aggregate_final_score` desc, polishes the top-N under `max_llm_calls`, merges result into both the opportunity and its per-tuple rows, records `partial=True` when budget trips. Structured logs: `phase7_row_scored`, `phase7_opportunity_built`, `phase7_llm_call`, `phase7_llm_ok`, `phase7_llm_failed`, `phase7_cache_hit`, `phase7_budget_exhausted`.
- `scripts/phase7_recommend.py` → `outputs/reports/sourcing_recommendations.json` (full `RecommendationReport`) + `sourcing_recommendations.csv` (per-tuple) + `consolidation_opportunities.csv` (per-source rollup). CLI flags: `--assessments/--candidates/--registry/--top-n-polish/--max-llm-calls/--model/--prompt/--cache-path/--no-cache/--dry-run/--source/--company/--min-grade`.
- `src/agnes/config/settings.py` — added `phase7_sourcing_weights` (JSON), `phase7_final_weights` (JSON), `phase7_safe_threshold=0.70`, `phase7_reject_threshold=0.30`, `phase7_top_n_polish=5`, `phase7_max_llm_calls=10`, `phase7_llm_model="gemini-2.5-flash"`; `.env.example` mirrors as `AGNES_PHASE7_*`.
- `tests/test_recommendation_models.py`, `tests/test_recommendation_signals.py`, `tests/test_recommendation_scorer.py`, `tests/test_recommendation_builder.py`, `tests/test_recommendation_engine.py`, `tests/test_llm_polish.py` — schema round-trips + enum/bounds validation, index construction, concentration-relief triggers, overlap ratio, monotonicity of every scorer input, Phase 6 veto + high-weight-contradiction downgrade, builder citation/caveat passthrough, rollup best-candidate selection + stability under row shuffling, engine end-to-end (dry-run skips LLM, top-N limits polish scope, cache hit on rerun, budget exhaustion → `partial=True`, LLM failure falls back to deterministic summary), plus polish-LLM parse/retry/schema-mismatch. 36 new tests, all green; full suite (116) clean.

**Coverage model (report):**

- `n_tuples`: per-row `SourcingRecommendation` count (after optional `--source/--company/--min-grade` filters).
- `n_opportunities`: distinct `source_key` rollups.
- `n_cache_hits`: opportunities whose polish came from `.cache/phase7_recommendations.json`; disjoint from `n_api_calls`.
- `n_api_calls`: *new* polish calls; capped by `max_llm_calls`.
- `n_failures`: polish failures that fell back to the deterministic summary.
- `counts_by_grade`: histogram over `RecommendationGrade`.
- `partial`: `True` iff the budget tripped a top-N opportunity that would otherwise have been polished.

**Idempotence:** `build_supplier_index`, `compute_signals`, `sourcing_benefit`, `final_score`, `map_grade`, `build_rows`, and `rollup_opportunities` are pure functions of their inputs. Only the optional LLM polish is non-deterministic; its results are cached under `(source_key, candidate_key, model, RECOMMENDATION_SCHEMA_VERSION)`, so reruns with the same assessments + model return `n_api_calls=0` and `n_cache_hits=n_opportunities_in_top_n` (asserted in `test_cache_hit_on_rerun`). Dry-run exercises the full deterministic pipeline with zero Gemini calls — the default mode for CI and demo prep.

**Observability:** Per-row / per-opportunity structured logs under `phase7_*`, plus a single-line JSON run summary on stdout. Error strings truncated to 200 chars; no secrets or PII in logs.

**Next phase:** Phase 8 — Demo UI (Streamlit/Gradio) over `sourcing_recommendations.json` + `consolidation_opportunities.csv`: one click drills from opportunity → per-tuple rows → Phase 6 rationale → Phase 5 citations. Optional post-Phase 8: wire the deferred Cognee Cloud memory write once the UI has an explicit "save decision" affordance.

---

## Phase 8: Demo UI — Complete

**Purpose:** expose Phase 2–7 artifacts through a narrow FastAPI transport layer and a Next.js 15 App Router frontend so a non-technical reviewer can land on http://localhost:3000, understand the current consolidation story in under 30 seconds, drill from an opportunity into its grounded evidence + compliance assessment, and — when the data feels stale — re-run any phase from the UI with live log streaming. The frontend never writes artifacts directly; the CLI scripts remain the single source of truth.

**Design rules honored:**

- Transport only: `src/agnes/api/` is a thin read/run layer. It imports existing Pydantic models and CLI scripts unchanged; there is no new pipeline logic.
- Artifacts are the source of truth: reads go through a shared `ArtifactLoader` keyed by `(path, mtime_ns)`; every successful run invalidates the loader so the UI auto-refreshes.
- One concurrent run per phase: enforced in the run manager, returned as `409 run_conflict` so the UI can disable the button instead of racing itself.
- Subprocess hygiene: runs spawn via `asyncio.create_subprocess_exec(sys.executable, "scripts/phaseN_*.py", …)` so stdout/stderr stream live, cancel delivers `SIGTERM → SIGKILL`, and all state lives in memory (bounded ring of the last 20 runs); nothing is persisted.
- Quota-aware: the frontend tails stderr for `429` / `resource_exhausted` / `quota` and surfaces a verbatim explainer inline — the Phase 5 free-tier failure mode is documented in the UI, not hidden.
- Every async surface renders explicit loading / error / empty / `partial=true` states. Missing reports return `404` with `{error:"artifact_missing"}` so the UI can prompt the user to run the phase that produces them.

**What was built (backend, `src/agnes/api/`):**

- `main.py` — `create_app()`, CORS for `http://localhost:3000`, lifespan that wires `ArtifactLoader` + `RunManager` into `app.state`, and `/api/health`.
- `services/artifact_loader.py` — thread-safe mtime-keyed cache over the five report Pydantic models (`CanonicalRegistry`, `SubstituteCandidateReport`, `EvidenceReport`, `AssessmentReport`, `RecommendationReport`); `ArtifactStatus`, `ArtifactMissingError`, and an `invalidate(name)` hook used by the run manager.
- `services/run_manager.py` — `RunManager` singleton with `start / cancel / subscribe / snapshot / list_runs / shutdown`. Per-run `LogLine` deque (2000 lines), fan-out via bounded `asyncio.Queue`s, automatic loader invalidation on exit code 0, and a one-run-per-phase guard with `409` semantics.
- `artifacts.py` — read-only GET endpoints (`/api/summary`, `/api/registry` paged with `q/family/role`, `/api/registry/{canonical_key}`, `/api/candidates`, `/api/evidence[/{source_key}/{candidate_key}]`, `/api/assessments[/{row_key}]`, `/api/recommendations[/{row_key}]`, `/api/opportunities[/{source_key}]`). `/api/summary` surfaces presence + `generated_at` + partial flags + counts per phase; `/api/opportunities/{source_key}` joins the per-tuple rows, matching Phase 5 evidence, Phase 6 assessments, and Phase 4 candidates in one payload.
- `runs.py` — typed request bodies (`Phase4Params`…`Phase7Params` with 1:1 CLI flag mapping), `POST /api/runs/phase{4,5,6,7}`, `GET /api/runs[/{run_id}]`, `POST /api/runs/{run_id}/cancel`, and SSE at `/api/runs/{run_id}/events` emitting `status` / `log` / `done` events with JSON payloads.
- `pyproject.toml` — added `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `sse-starlette>=2.1` as first-class deps.
- `tests/test_api_artifacts.py` + `tests/test_api_runs.py` — 13 tests covering health, summary, registry pagination and filters, candidate/evidence/opportunity round-trips, missing-pair 404 shape, and a stub-subprocess run lifecycle (start → stream → success, list history, unknown run 404, cancel unknown 409, concurrent run 409). All 13 green; pre-existing `test_cognee_cloud_client` failures are unrelated.

**What was built (frontend, `frontend/`):**

- Next.js 15 App Router (`src/app/`), TypeScript strict, Tailwind 3 dark theme (`tailwind.config.ts`, `globals.css`), TanStack Query v5, Zod, `sonner` toasts, `lucide-react` icons. Hand-scaffolded (no `create-next-app` shell) to avoid stock boilerplate.
- `src/lib/schema.ts` — Zod mirrors of every Pydantic contract the UI consumes (`Summary`, `RegistryPage`, `SubstituteCandidateReport`, `EvidenceReport`, `AssessmentReport`, `RecommendationReport`, `OpportunityDetail`, `RunMeta`, `RunSnapshot`); `.passthrough()` on the nested records so new backend fields don't break builds.
- `src/lib/api.ts` — typed fetch client (parses through Zod, raises `ApiError` with status + detail) plus a `sseUrl(runId)` helper.
- `src/lib/sse.ts` — thin `EventSource` wrapper dispatching `status` / `log` / `done` events with typed handlers and a disposal function.
- Components: `navbar`, `stat-card`, `grade-badge` + `assessment-badge` + `polarity-badge`, `score-bar` + `score-radial`, `spinner`, `empty` + `error-state`, `log-terminal` (auto-scroll, quota highlighting, preserves manual scroll position), `run-panel` (typed fields → CLI flags → SSE → React Query invalidation + toast on success).
- Pages: `/` Dashboard (hero opportunity card with radial, per-phase stat cards + age chips, global "partial run" warning); `/opportunities` list (grade filter chips, client-side sort, one row per `ConsolidationOpportunity`); `/opportunities/[source_key]` with Recommendations / Evidence / Assessment tabs (per-tuple table, per-claim polarity badge + grounded-vs-parametric pill + citation fold-outs, per-candidate assessment grouping with caveats/contradictions chips); `/materials` paged registry (server-side filter by family/role, free-text search, 50/page); `/runs` with four `RunPanel`s, each mapping its body 1:1 to the underlying CLI (`top_sources/per_source/max_total`, `max_llm_calls`, `top_n_polish`, `source`, `company`, `min_grade`, `model`, `no_cache`, `dry_run`), a live terminal, and cache invalidation on success.
- `next.config.ts` pins `outputFileTracingRoot` to `frontend/` to silence the "multiple lockfiles" warning. Production build clean: `/` (3.6 kB), `/opportunities` (1.9 kB), `/opportunities/[source_key]` (2.9 kB), `/materials` (4.7 kB), `/runs` (7.1 kB).

**Infra / docs:**

- `docker-compose.yml` + `docker/backend.Dockerfile` + `docker/frontend.Dockerfile` for a single `docker compose up --build` demo (backend mounts the repo to keep `outputs/` as the source of truth).
- `.env.example` — added `AGNES_API_CORS_ORIGINS`, `AGNES_REPORTS_DIR`, `AGNES_REPO_ROOT`, `NEXT_PUBLIC_API_URL`; scrubbed the live `AGNES_COGWIT_API_KEY` sample value.
- `frontend/.env.example` — single `NEXT_PUBLIC_API_URL` line.
- `README.md` — "Run the demo" section covering the two-terminal local setup and the Docker Compose alternative.

**Coverage model (UI story hooks):**

- Dashboard stat cards show `present=false` as a warn-chip when a phase has never been run and route the viewer to `/runs` via the empty state on the hero card.
- The partial-run warning banner is driven by OR-ing `candidates/evidence/assessments/recommendations.partial` on `/api/summary`; no client-side heuristics.
- Runs console detects `429` / `resource_exhausted` / `quota` anywhere in streamed logs and surfaces a persistent warning banner pointing the user at `--dry-run` / an alternate model.

**Idempotence:** The API is read-only except for the explicit `POST /api/runs/phaseN` endpoints, which delegate to the existing idempotent CLIs. The run manager is a pure singleton: killing the FastAPI process loses run history but not artifacts. The frontend is a pure consumer of `/api/*`; all state is derived.

**Observability:** `/api/runs/{id}/events` streams the exact stdout of each phase (structlog ConsoleRenderer output), which the `LogTerminal` renders with per-level color. Backend structured logs reuse `configure_logging`; no new log schema.

**Verified (local smoke):**

- `uv run pytest tests/test_api_artifacts.py tests/test_api_runs.py -q` → 13 passed.
- `uv run pytest -q` → 137 passed, 2 pre-existing Cognee client failures unchanged.
- `npm --prefix ./frontend run typecheck` → clean; `npm --prefix ./frontend run build` → 7 static routes + 1 dynamic, no warnings.
- Live backend `uvicorn agnes.api.main:app` @ `127.0.0.1:8765`: `/api/health` → `{status:"ok"}`, `/api/summary` → all five artifacts `present=true`, `/api/opportunities` → 1 opp (`calcium-citrate → dicalcium-phosphate`, `safe_to_consolidate`), `/api/opportunities/calcium-citrate` → 12 rows + 3 evidence + 12 assessments + 3 candidates, `/api/registry?limit=3` → `total=876`, `families=16`, `roles=13`. End-to-end run: `POST /api/runs/phase4 {"target":"calcium-citrate","dry_run":true}` returned `run_id`, finished in ~2 s with `status=succeeded`, `exit_code=0`, and `args=["--target","calcium-citrate","--dry-run"]` captured in `/api/runs` history.

**Non-goals (unchanged from the plan):** no auth, no multi-user, no server-side persistence of runs, no writes to `outputs/reports/` from the frontend, no voice (ElevenLabs remains Phase 9).

**Next phase:** Phase 9 — voice / ElevenLabs narrator sitting on top of the Phase 8 artifact bundle, plus an optional Cognee Cloud "save decision" write triggered from the opportunity detail view.

---

## Phase 8.1: Dashboard full-bundle redesign — Complete

**Purpose:** collapse the dashboard's per-section HTTP chatter into a single batched request, then render every Phase 2–7 artifact as purpose-built UI (never raw JSON). The landing page becomes a "command center" that holds the complete pipeline story — full canonical registry, per-tuple recommendations, every evidence claim with citations, every assessment — not a five-tile summary with a single hero card. Drill-through pages (`/opportunities`, `/opportunities/[source_key]`) reuse the same payload via React Query cache seeding, so navigation from the dashboard issues zero additional network calls.

**Design rules honored:**

- One request, full dataset: `/api/dashboard` returns the whole bundle in one payload. Gzip middleware shrinks the 1.15 MB real-world response to ~237 KB over the wire (~79 % reduction), well within demo budget.
- Server-side aggregates: the backend computes family/role counts and a confidence histogram so the UI never recomputes over 876 canonical rows on each render.
- Graceful degradation: every phase block is nullable. Missing artifacts surface in a `missing: [name…]` list so the UI renders `Empty` sections with a "Run this phase" CTA instead of a page-wide error.
- No JSON dumps anywhere: every field lands on a dedicated component (score bar, radial, donut, horizontal bars, polarity badge, citation chip, claim card, recommendation row, collapse section). The guarantee is structural — the rewrite contains zero `<pre>{JSON.stringify(...)}</pre>` constructs.
- Cache coherence: the same React Query keys used by the drill-through pages (`["opportunities"]`, `["opportunity", source_key]`, `["recommendations"]`, etc.) are seeded from the bundle on success, and those pages run with `staleTime: 60_000, refetchOnWindowFocus: false` so the seeded data is actually reused.

**What was built (backend):**

- `src/agnes/api/artifacts.py` — new Pydantic models: `ConfidenceBucket`, `RegistryBundle` (total + families + roles + `family_counts` + `role_counts` + `confidence_histogram` + full `items`), and `DashboardBundle` (summary + registry + candidates + evidence + assessments + recommendations + pre-joined `opportunity_details` + missing).
- Factored shared helpers so `/api/summary`, `/api/opportunities/{source_key}`, and `/api/dashboard` all route through the same code:
  - `_build_summary(loader)` returns `(SummaryOut, generated_at map, missing list)`.
  - `_build_opportunity_detail(loader, opportunity, recommendations)` joins per-tuple rows + matching evidence + assessments + candidates for a single source.
  - `_build_registry_bundle(loader)` walks the canonical registry once to compute `family_counts`, `role_counts`, and five-bucket confidence histogram (`0.00–0.20`, `0.20–0.40`, `0.40–0.60`, `0.60–0.80`, `0.80–1.00`), each sorted by descending count so the UI can trust order without re-sorting.
- `GET /api/dashboard` calls those helpers and iterates `recommendations.opportunities` to pre-join every opportunity detail. Loader misses on individual phases are swallowed to keep the response usable when the pipeline is partially populated.
- `src/agnes/api/main.py` — added `GZipMiddleware(minimum_size=1024)` before `CORSMiddleware` so FastAPI honors `Accept-Encoding: gzip` on the single large endpoint.
- `tests/test_api_artifacts.py` — new `test_dashboard_bundle_shape` asserts the top-level keys, `registry.family_counts + role_counts + confidence_histogram` each sum to `registry.total`, and every `opportunity_details[i].opportunity.source_key` maps back into `recommendations.opportunities` (and each row's `source_key` matches its opportunity). Skips gracefully when the artifacts aren't on disk.

**What was built (frontend):**

- `frontend/src/lib/schema.ts` — Zod mirrors for `ConfidenceBucket`, `RegistryBundle`, and `DashboardBundle`, composed from the existing `Summary / SubstituteCandidateReport / EvidenceReport / AssessmentReport / RecommendationReport / OpportunityDetail` schemas. `.passthrough()` on records so new backend fields don't regress parsing.
- `frontend/src/lib/api.ts` — `api.dashboard()` typed fetch helper.
- `frontend/src/lib/useDashboard.ts` — single `useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, staleTime: 60_000, refetchOnWindowFocus: false })`. Inside a `useEffect` on success it calls `queryClient.setQueryData` to seed `["summary"]`, `["opportunities"]`, `["recommendations"]`, `["assessments"]`, `["evidence"]`, `["candidates"]`, `["registry-bundle"]`, and `["opportunity", source_key]` for every pre-joined detail.
- Query-key alignment: `frontend/src/app/opportunities/page.tsx` and `frontend/src/app/opportunities/[source_key]/page.tsx` already used the `["opportunities"]` and `["opportunity", source_key]` keys; both had `staleTime: 60_000` + `refetchOnWindowFocus: false` added so the seeded cache is reused instead of immediately refetched on observer mount.
- New reusable components under `frontend/src/components/`:
  - `opportunity-hero.tsx` — reusable hero (grade badge, radial, supplier chips, tradeoff summary, drill-through CTAs) extracted from the old inline implementation.
  - `donut.tsx` — dependency-free SVG donut chart. Tones are statically mapped (`stroke-good / stroke-accent / stroke-warn / stroke-bad / stroke-fg-muted` + matching `bg-*` for legend dots) so Tailwind's JIT picks up every class.
  - `horizontal-bars.tsx` — reused three times for family/role distributions and the confidence histogram.
  - `citation-chip.tsx` — favicon (via Google S2 favicon endpoint) + title + domain + external-link icon; extracted structurally from `CitationRef`.
  - `claim-card.tsx` — renders one `EvidenceClaim` with polarity badge, grounded-vs-parametric pill, confidence bar (toned by polarity), top-3 citations, and a "+N more" expander for the rest.
  - `recommendation-row.tsx` — four-column card for a single `SourcingRecommendation` (header + grade + path + tuple, scores stack, current → recommended supplier chips, tradeoff clamp + caveat/risk chips).
  - `collapse-section.tsx` — headless collapsible (chevron + title + subtitle + right-slot).
- Dashboard rewrite (`frontend/src/app/page.tsx`) — ten sections, all driven by `useDashboard()`:
  1. **Header strip** — command-center title, "oldest artifact" relative chip, all-phases-present / N-missing chip, per-partial-phase warning banner linking to `/runs`.
  2. **KPI row (5 cards)** — each card wrapped in an anchor to a matching `#materials`, `#candidates`, `#evidence`, `#assessments`, `#opportunities` section below.
  3. **Top opportunity hero** — the highest-`aggregate_final_score` `ConsolidationOpportunity`.
  4. **Opportunities table** — full list, sorted by `aggregate_final_score` desc, with per-row `ScoreRadial`, `ScoreBar`, and current-vs-recommended supplier count chips.
  5. **Per-tuple recommendations** — grouped by `source_key` in a `CollapseSection` (top opportunity opened by default), each child row rendered by `RecommendationRow`.
  6. **Evidence highlights** — per `SubstituteEvidence` item: header with counts + contradiction chip + model name; a 2-column grid of `ClaimCard`s.
  7. **Assessments** — side-by-side `Donut` of `counts_by_class` + full tuples table (assessment badge, company/product, source → candidate, acceptability bar, decision-path pill, rationale clamp + caveat/contradiction chips).
  8. **Canonical materials** — three `HorizontalBars` panels (families top-12, roles top-12, confidence histogram) + a 12-card preview grid with normalized name, SKU, family/role chips, and a confidence score bar, plus a "Browse all" link to `/materials`.
  9. **Substitute candidates** — table of every candidate with per-row score bar and a per-feature (family/role/lex/embed/supplier) breakdown in a monospace column.
  10. **Pipeline health footer** — one card per phase with presence/age, `partial` chip, and 4–6 key stats (durations in seconds, API-vs-cache counts, coverage).
- Loading → full-page skeleton (`DashboardSkeleton`) matching the target layout; error → `ErrorState`; per-section empties route the viewer to `/runs` with a phase-specific CTA.

**Coverage model (UI story hooks):**

- "N phases not yet run" chip drives directly off `bundle.missing`; replaced by a green `all phases present` chip when the list is empty.
- Partial-run banner lists exactly the phase names where `cands.partial || ev.partial || asmt.partial || rec.partial` is true (no OR-collapse into a single opaque flag).
- Every KPI card's age chip comes from `statusFor(name).generated_at`; the header's "oldest" chip is the minimum `generated_at` across present artifacts, so the user sees the worst-case staleness first.
- `opportunity_details[i]` is pre-fetched with rows + evidence + assessments + candidates, so clicking into `/opportunities/[source_key]` from the dashboard never re-hits the network.

**Idempotence:** `/api/dashboard` is a pure view over the on-disk artifacts; re-calling it is a no-op beyond loader cache revalidation (keyed by `(path, mtime_ns)`). The frontend hook is idempotent: re-mounting the dashboard page inside `staleTime: 60_000` returns the in-memory React Query cache with zero HTTP.

**Observability:** The endpoint itself logs nothing new; it reuses the Phase 8 structured logger for lifespan + request phases. Gzip middleware is quiet. Missing artifacts are surfaced via the `missing` field, not by 404ing the whole bundle.

**Verified (local smoke):**

- `uv run ruff check src/agnes/api tests/test_api_artifacts.py` → clean.
- `uv run pytest tests/test_api_artifacts.py tests/test_api_runs.py -q` → 14 passed (13 existing + new `test_dashboard_bundle_shape`).
- `npm --prefix ./frontend run typecheck` → clean; `npm --prefix ./frontend run build` → 7 routes, `/` is 10.4 kB / 148 kB first-load JS, no warnings.
- Live backend `uvicorn agnes.api.main:app @ 127.0.0.1:8765`: `/api/dashboard` returned **1,157,364 bytes** uncompressed / **237,142 bytes** gzipped; `keys = [assessments, candidates, evidence, missing, opportunity_details, recommendations, registry, summary]`; `missing = []`; `registry.total = 876`, `family_counts.sum() == role_counts.sum() == confidence_histogram.sum() == 876`; `len(opportunities) == len(opportunity_details) == 1`; `evidence.items = 3`, `assessments.items = 12`, `recommendations.items = 12`.
- Network profile: dashboard load issues exactly one `/api/dashboard` request; clicking into `/opportunities/calcium-citrate` afterward issues zero network calls (seeded cache hits).

**Non-goals (unchanged):** no pagination for the dashboard (dataset is small enough to ship whole; `/api/registry` paged endpoint stays for the Materials page), no pipeline-logic changes, no voice — Phase 9 remains the next milestone.

---

## Phase X: OpenAI migration (gpt-4o-mini + Tavily `search_web`)

**Purpose:** Replace Gemini with OpenAI across every LLM touchpoint so Agnes
depends on a single commercial provider with predictable rate-limit semantics
(`openai.RateLimitError` + `Retry-After` headers) and a cheaper default model.
Phase 5's grounded extraction is reimplemented as a function-calling loop over
a `search_web` tool backed by Tavily Search.

**Model map (new defaults):**

- Phase 4 embeddings: `text-embedding-3-small` (`openai.OpenAI.embeddings.create`).
- Phase 5 grounded extraction: `gpt-4o-mini` with a single `search_web(query,
  max_results)` function tool. The orchestration loop in
  `src/agnes/retrieval/openai_grounded.py` dispatches tool calls through the
  `WebSearchProvider` Protocol (default `TavilySearchProvider`).
- Phase 6 structured fallback: `gpt-4o-mini` with `response_format={"type":
  "json_object"}` (no tools).
- Phase 7 polish: same shape as Phase 6, `temperature=0.2`.
- Smoke ping: `scripts/smoke_openai.py` → `agnes.retrieval.openai_client.ping`
  (1-token `chat.completions.create`).

**Shared helpers:** `src/agnes/llm/openai_client.py` exposes `make_client`,
`is_rate_limited`, and `retry_after_seconds` so every phase uses identical
backoff semantics. The existing client-side RPM throttles inside
`src/agnes/substitutes/embeddings.py` and the Phase 5 / Tavily adapters are
preserved — only the exception parsing changed.

**Field rename:** `gemini_model` is now `llm_model` on every Pydantic model
(`SubstituteEvidence`, `SubstituteAssessment`, `SourcingRecommendation`,
`ConsolidationOpportunity`, and their report wrappers), every producer
(enricher/assessor/builder/engine), every CSV writer, and the Zod schemas +
chips in the frontend. Cache-key discriminators now embed the OpenAI model id.

**Schema bumps:** `EVIDENCE_SCHEMA_VERSION`, `ASSESSMENT_SCHEMA_VERSION`, and
`RECOMMENDATION_SCHEMA_VERSION` moved from `v1` → `v2` so existing
`.cache/phase{5,6,7}_*.json` entries miss cleanly on the first migrated run.
The Phase 4 embedding cache is keyed by `(model, canonical_key)` and is
auto-invalidated by the model-id change (`gemini-embedding-001` →
`text-embedding-3-small`).

**New env contract:**

- `AGNES_OPENAI_API_KEY` (required for Phases 4–7).
- `AGNES_OPENAI_MODEL` (default `gpt-4o-mini`, used by the smoke script).
- `AGNES_TAVILY_API_KEY` (required for Phase 5 grounded runs).
- Optional throttle knobs: `AGNES_EMBED_RPM`, `AGNES_GROUNDED_RPM`,
  `AGNES_GROUNDED_MAX_TOOL_CALLS`, `AGNES_TAVILY_RPM`,
  `AGNES_TAVILY_MAX_RETRIES`.

**Removed / renamed files:**

- `src/agnes/retrieval/gemini_grounded.py` → `openai_grounded.py`.
- `src/agnes/retrieval/google_cloud_client.py` → `openai_client.py`.
- `scripts/smoke_gemini.py` → `scripts/smoke_openai.py`.
- `tests/test_gemini_grounded.py` → `test_openai_grounded.py`.
- New: `src/agnes/tools/web_search.py` (Tavily adapter + Protocol),
  `src/agnes/llm/openai_client.py` (shared helpers).

**First-run hygiene:** on upgrade, delete the Phase 4–7 caches once
(`rm -f .cache/phase{4,5,6,7}_*.json`) or rely on the schema bump. See
`README.md` "Setup" section.

### Handoff summary (2026-04-18)

- **Done:** Full stack migration from Gemini (`google-genai`) to **OpenAI** (`gpt-4o-mini` for chat, `text-embedding-3-small` for Phase 4). Phase 5 uses a **function-calling loop** with a `search_web` tool backed by **Tavily** (`AGNES_TAVILY_API_KEY`). Shared rate-limit helpers live in `src/agnes/llm/openai_client.py`. Field **`gemini_model` → `llm_model`** across Pydantic, API, CSV, Zod, and UI; evidence/assessment/recommendation **schema versions** are **`v2`**. Smoke test: `uv run python scripts/smoke_openai.py`.
- **Removed:** `gemini_grounded.py`, `google_cloud_client.py`, `smoke_gemini.py`, `test_gemini_grounded.py`. **Added:** `openai_grounded.py`, `retrieval/openai_client.py`, `tools/web_search.py`, `smoke_openai.py`, `test_openai_grounded.py`.
- **Verify locally:** `uv run ruff check src tests scripts`, `uv run pytest -q` (if `AGNES_COGWIT_API_KEY` is set in `.env`, two Cognee key-resolution tests may fail until that var is unset for the test run), `npm --prefix frontend run typecheck && npm --prefix frontend run build`.
- **Ops:** Set `AGNES_OPENAI_API_KEY` and `AGNES_TAVILY_API_KEY` in `.env`; re-run Phases 4→7 to refresh `outputs/reports/` artifacts. Pipeline caches under `.cache/` remain gitignored.
