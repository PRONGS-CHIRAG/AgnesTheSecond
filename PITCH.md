# AgnesTheSecond — 5-Minute Pitch

**TUM.ai × Spherecast Makeathon 2026**

Speaker script with slide markers. ~680 words ≈ 5 minutes at 135 wpm.
Bracketed notes are stage directions — skip when speaking.

---

## Slide 1 — Title (0:00 – 0:20)

> **AgnesTheSecond**
> *Supply chain intelligence that shows its work.*

"Hi — we're the team behind **Agnes The Second**. We built a supply-chain
intelligence platform for CPG companies that does two things most tools
refuse to do: it balances cost against risk honestly, and **every number
we show you is a pure function of your data — not an LLM guessing.**"

---

## Slide 2 — The Problem (0:20 – 1:00)

> **Procurement tools pick the wrong trade-off. AI tools make up numbers.**
>
> 1. "Consolidate with fewer suppliers — save money."
> 2. "Diversify across suppliers — reduce risk."
> 3. *"Here's a GPT-generated recommendation!"* — source: vibes
>
> **None of these survive a CFO conversation.**

"Procurement teams live inside a real tension. Consolidation gives you
leverage. Diversification protects you when a supplier has a factory fire
or a recall. Legacy tools tell you to pick one. The new wave of AI tools
just hallucinate confident-sounding numbers with no audit trail. Neither
approach survives a CFO conversation."

---

## Slide 3 — What Agnes Is (1:00 – 1:35)

> **Four products, one deterministic brain.**
>
> - **Chat** — natural-language agent, dispatches real SQL
> - **Explorer** — 5-tab data browser across 61 companies, 357 ingredients
> - **Insights** — 1,263-line deterministic analysis engine
> - **Cube** — voice interface
>
> Real dataset: **$1.52B of procurement spend · 8,127 orders · 40 suppliers.**

"Four products sharing one brain. Chat, Explorer, Insights, Voice. All
backed by the same 1,263-line Python engine running on real procurement
data — 61 companies, 357 ingredients, 40 suppliers, 8,127 orders, $1.52
billion in spend."

---

## Slide 4 — Deterministic by Design (1:35 – 2:10)

> **Every score is pure math. Same inputs → same outputs. Bit-for-bit.**
>
> - Consolidation detection: **pure rules.**
> - Risk assessment (5 risk types): **pure rules.**
> - The 5-dimension scoring framework: **pure weighted math.**
> - LLMs are used **only where they can't hallucinate damage** — dispatching
>   SQL queries, not inventing numbers.
> - **168 tests passing**, schema-versioned outputs, idempotent reruns.

"Here's what separates us from the AI-wrapper tools. **Every score Agnes
shows you is a deterministic function of your data.** Consolidation
detection, risk scoring, the weighted framework — all pure Python. Same
inputs give you the same outputs, byte-for-byte, on every run. 168 tests
enforce this."

"We use LLMs exactly where they help and nowhere they can hurt. The chat
agent dispatches real SQL queries against your database — it doesn't
invent answers, it routes questions to deterministic lookups. When we
optionally polish a recommendation summary, the LLM can only rewrite the
prose. **It cannot change a grade, a score, or a supplier.** That's a
hard boundary in the code."

---

## Slide 5 — The Prioritization Framework (2:10 – 3:15)

> **Every recommendation scored on 5 explicit dimensions:**
>
> | Weight | Dimension |
> |--------|-----------|
> | 0.35 | Consolidation leverage |
> | 0.25 | Evidence confidence |
> | 0.20 | Compliance fit |
> | 0.10 | **Supplier diversification** ← anti-monopoly guard |
> | 0.10 | Switching feasibility |
>
> **If consolidation would leave ≤2 suppliers network-wide, the grade is
> automatically downgraded.**

"The scoring framework. Every recommendation is a weighted sum of five
dimensions. Leverage, evidence, compliance, diversification, feasibility.
You can see the weights. You can check the math."

"Here's the load-bearing rule: **when consolidating would leave fewer
than three suppliers for that ingredient across the entire network, the
framework automatically downgrades the recommendation.** Not a heuristic,
not a prompt — a hard rule in the code."

"On our dataset, **124 of 125 consolidation opportunities trigger this
veto.** A naive tool would tell you to consolidate all 125 and save
millions. Agnes tells you which 1 is actually safe, and on the other 124
it says *consolidate most of the volume but keep a qualified backup.* That
is a defensible CFO-grade recommendation."

---

## Slide 6 — Live Demo (3:15 – 4:30)

> **[Open http://localhost:5050/agnes/]**

"Let me show you." **[Recommendations tab]**

"Grade badges, final scores. Every number you see — click any card —" **[expand Microcrystalline Cellulose]** "— comes with the full tension
matrix. Leverage 0.70, compliance 1.0, diversification *0.25.* Red.
Because the network has only 2 suppliers. Grade: review_required. The
banner explicitly says — *maximum leverage, minimum concentration risk.*"

**[Scroll to Beta Carotene]**

"Contrast: Beta Carotene. Four suppliers. Diversification green. Safe to
consolidate. Same engine, different reality, different answer — reached
by the same deterministic math."

**[Open Chat — http://localhost:5050/]**

"Chat surface. Same engine. Ask *'What are our top single-source risks?'*
— the agent runs SQL against the real database, shows its reasoning
steps, and cites the rows. No hallucinated numbers. **Every claim is
traceable to a query.**"

---

## Slide 7 — Why This Matters (4:30 – 4:50)

> **We don't ship dashboards. We ship defensible positions.**
>
> *"Agnes doesn't optimize for fewer suppliers.
> It finds maximum leverage with minimum concentration risk —
> and shows you the exact math behind every call."*

"Spherecast's customers don't need another tool that says 'you could
consolidate.' They need one that tells them **where to stop**, backed by
math they can defend to a CFO. That's what Agnes is."

---

## Slide 8 — Ask (4:50 – 5:00)

> **Ready to pilot today.**
>
> *Maximum leverage. Minimum concentration risk. Deterministic by design.*

"Happy to walk through the code, the data, or the math."

---

## Speaker cheat-sheet

**Numbers to memorize**
- 61 companies · 357 ingredients · 40 suppliers · 149 finished goods
- $1.52 billion procurement spend · 8,127 historical orders
- **125 consolidation opportunities · 124 trigger the concentration-risk veto**
- Weights: 35 / 25 / 20 / 10 / 10
- **168 tests passing · 1,263-line deterministic engine**

**One-liner (if they cut you off)**
> "Every score is pure math, every recommendation shows its work, and we
> refuse to recommend consolidating down to a monopoly."

**If asked "where do you use LLMs, exactly?"**
> "Three places. (1) The chat agent dispatches SQL queries — the data
> comes from your database, not the model. (2) Evidence extraction for
> external substitute research, with citations — we validate and cite
> every claim. (3) Optional prose polish on recommendation summaries,
> budget-capped and cached. **In all three, the LLM can never change a
> score, a grade, or a supplier.** Those are deterministic outputs."

**If asked "what stops the LLM from hallucinating?"**
> "Architecture, not prompting. The scoring engine has no LLM in the
> loop. LLM outputs that flow into the UI are Pydantic-validated against
> strict schemas with extra='forbid' — malformed outputs fail closed.
> LLM polish is scoped to summary text only; grades and scores come from
> pure functions. Every cache entry is keyed by schema version, so model
> drift can't silently corrupt historical decisions."

**If asked why we don't just consolidate fully**
> "Because 124 out of 125 times the math says you shouldn't. Monopoly
> risk compounds. One supplier failure takes out an ingredient line
> across every company downstream. Agnes keeps a qualified backup — you
> retain ~90% of the negotiating leverage, and you don't lose the
> business when a factory burns."

**If asked about the tech stack**
> "Python + Flask backend, SQLite with real + mock procurement data, OpenAI
> gpt-4o-mini for the chat SQL-dispatcher and optional prose polish only.
> Vanilla HTML/JS frontend. Pure-Python deterministic analysis engine,
> 168 tests, schema-versioned outputs, reproducible reruns."
