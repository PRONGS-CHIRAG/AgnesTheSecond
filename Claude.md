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
  - Empty placeholder packages: `models/`, `canonicalization/`, `substitutes/`, `reasoning/`, `optimization/`, `ui/`
- `scripts/smoke_db.py`, `smoke_gemini.py`, `smoke_cognee.py` — one-liner JSON output, exit 0/1
- `tests/test_smoke.py` — import + settings tests (no network required)
- `data/raw/db.sqlite` — copied from `hackathon-tumai/db.sqlite` (gitignored)
- `.env.example` — all `AGNES_` keys documented
- `README.md` — setup and verify steps

**Confirmed DB row counts:** Company 61 / Product 1025 / BOM 149 / BOM\_Component 1528 / Supplier 40 / Supplier\_Product 1633.

**Next phase:** Phase 1 — schema inspection, BOM relational queries, repeated raw-material analysis, overlap reports.