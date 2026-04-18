
---

#  `DO_NOT_DO.md` (copy-paste ready)

```md
# DO_NOT_DO.md

## Purpose

This file defines what Claude Code / Cursor / the developer must **NOT** do while building this multi-agent, tool-enabled, MCP-integrated hackathon MVP.

The goal is to prevent:
- token waste
- context drift
- architectural mess
- fake complexity
- fragile demos
- unsafe agent behavior
- hackathon death spirals

---

## 1) Do NOT over-engineer

Do NOT:
- create unnecessary abstractions before the first working flow
- split into microservices for a hackathon MVP
- create 8+ layers for simple logic
- build a “framework” before shipping a feature
- optimize for scale before proving the demo path

Avoid:
- speculative architecture
- enterprise theater
- pattern obsession

Rule:
- If a simpler design ships faster and stays maintainable, choose it.

---

## 2) Do NOT use multi-agent just for hype

Do NOT:
- create multiple agents with overlapping responsibilities
- rename identical LLM calls as “specialized agents”
- add planner / router / critic / evaluator / memory / reflection / judge / reviewer all at once without need
- build agent chains that are impossible to debug

Bad signs:
- unclear ownership per agent
- hidden prompt spaghetti
- no measurable benefit from agent separation

Rule:
- Every agent must have a **clear, defensible role**.

---

## 3) Do NOT let agents call tools in an uncontrolled way

Do NOT:
- let agents call raw APIs directly
- let agents call MCP endpoints without wrappers
- pass unvalidated tool outputs straight into final user responses
- assume tool outputs are correct
- silently ignore tool failures

Rule:
- All tools must be wrapped, validated, and observable.

---

## 4) Do NOT build giant prompts instead of code

Do NOT:
- bury business logic inside huge prompts
- use prompt text as the primary source of system behavior
- rely on fragile regex parsing of free-form LLM output if schemas are possible
- keep reusing giant context blobs in every call

Prefer:
- schemas
- typed models
- deterministic post-processing
- reusable prompt templates
- code-driven orchestration

---

## 5) Do NOT waste context / tokens

Do NOT:
- scan the whole repo for every task
- repeatedly re-read the same large files
- keep unrelated tasks in the same long session
- open entire folders when only 1–3 files are relevant
- do broad refactors while trying to finish a feature
- stuff huge docs into prompts unless absolutely necessary

Rule:
- Always identify the **minimum relevant file set** first.

If a graph / repo map / graph report exists:
- use that first
- do NOT read everything blindly

---

## 6) Do NOT let route handlers become orchestration engines

Do NOT:
- put multi-agent logic directly inside FastAPI routes
- put tool calling logic inside frontend components
- mix transport, orchestration, and business logic in one file
- build “god files”

Rule:
- Keep routes thin.
- Keep orchestration in services / agents.
- Keep tools in adapters.

---

## 7) Do NOT ignore failure modes

Do NOT:
- only test happy paths
- assume MCP is always available
- assume external APIs are fast
- assume tool output format never changes
- assume LLM structured output is always valid
- silently fallback to hallucination when tools fail

Rule:
- If a tool fails, degrade gracefully and surface uncertainty.

---

## 8) Do NOT chase breadth over demo quality

Do NOT:
- add 10 features that are each 40% complete
- build dashboards nobody will click in the demo
- build secondary flows before the main “wow” flow works
- spend hours on admin panels before the core value is proven

Rule:
- Protect the **primary demo path** above all else.

---

## 9) Do NOT do large speculative refactors mid-hackathon

Do NOT:
- rewrite the whole architecture because a “cleaner pattern” appears
- migrate libraries without necessity
- rename half the codebase for aesthetics
- switch frameworks late unless blocked
- refactor working code right before demo

Rule:
- If it works and is structurally acceptable, move forward.

---

## 10) Do NOT hide system state

Do NOT:
- make agent decisions invisible
- hide which tools were used
- hide whether data is real vs inferred
- hide retries / fallbacks / degraded mode
- hide assumptions in silent logic

Rule:
- Keep important decisions inspectable in logs or UI when useful.

---

## 11) Do NOT trust external data blindly

Do NOT:
- trust MCP results without validation
- trust retrieval results without checking relevance
- trust user-uploaded documents as clean or complete
- trust model-generated JSON without schema validation

Rule:
- Treat all external outputs as untrusted until normalized.

---

## 12) Do NOT break type safety casually

Do NOT:
- spam `any` in TypeScript
- skip type hints on important Python functions
- pass loose dictionaries everywhere
- use weakly typed contracts between tools and agents

Rule:
- Typed boundaries reduce bugs and reduce LLM confusion.

---

## 13) Do NOT hardcode secrets or environment assumptions

Do NOT:
- commit API keys
- hardcode localhost ports without documenting them
- assume external services are running
- assume one developer machine setup
- store secrets in source files

Rule:
- Use `.env`, `.env.example`, and explicit setup docs.

---

## 14) Do NOT optimize the wrong thing

Do NOT:
- prematurely optimize latency before the workflow is stable
- obsess over token savings while the architecture is still broken
- over-polish UI while the core logic is unreliable
- spend time on edge-case perfection before the main path works

Rule:
- First: correct and stable
- Then: demoable
- Then: faster / cleaner / prettier

---

## 15) Do NOT build “magic” that you cannot explain to judges

Do NOT:
- build a system you cannot describe in 30 seconds
- rely on hidden complexity without visible value
- add layers that do not strengthen your story
- make the architecture so complex it hurts credibility

Rule:
- Every major component should be explainable as:
  - why it exists
  - what problem it solves
  - why it improves trust, speed, or quality

---

## 16) Do NOT ignore observability

Do NOT:
- run agent flows with zero logs
- omit error messages
- hide tool failures
- skip latency tracing for slow steps
- debug purely by intuition

At minimum log:
- request start/end
- agent selected
- tools called
- tool success/failure
- validation pass/fail
- fallback triggered
- final status

---

## 17) Do NOT keep giant stale sessions alive forever

Do NOT:
- continue the same thread after multiple unrelated pivots
- let context accumulate dozens of stale branches
- rely on memory of old branches when the objective changed

Rule:
- One coherent objective per session.
- Summarize and reset when the task changes materially.

---

## 18) Do NOT skip documentation because “it’s just a hackathon”

Do NOT:
- leave setup undocumented
- omit env var explanations
- leave the architecture impossible to understand
- assume you’ll “remember later”

At minimum keep:
- README
- CLAUDE.md
- DO_NOT_DO.md
- .env.example
- short session handoff notes

---

## 19) Do NOT let the MVP become brittle because of shiny extras

Do NOT:
- add voice, vision, memory, autonomous background jobs, complex auth, multi-tenancy, or advanced analytics unless they clearly support the core story
- add a feature only because it sounds impressive

Rule:
- Every feature must strengthen:
  - core user value
  - demo narrative
  - technical credibility
  - judging impact

---

## 20) Final Anti-Pattern Check

Before adding any new component, ask:

1. Does this improve the primary demo path?
2. Can I explain why this exists in one sentence?
3. Is it more reliable than the simpler alternative?
4. Does it increase maintenance cost?
5. Will it create new failure modes before demo?
6. Can I test it quickly?
7. Is this solving a real problem or just adding complexity?

If unsure:
- do not add it yet.

---

## Final Rule

Do NOT sacrifice:
- clarity
- reliability
- demo stability
- maintainability

for:
- hype
- novelty theater
- fake complexity
- unnecessary agent count
- speculative architecture

Build the **strongest believable vertical slice**.
That wins hackathons more often than “AI chaos with 12 agents.”