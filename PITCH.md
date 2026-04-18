# AgnesTheSecond — Pitch

**TUM.ai × Spherecast Makeathon 2026**

Multi-format speaker notes: a 5-minute deck, a 60-second cut for
1-minute-talking formats, and FAQ answers for Q&A.

---

## Core positioning

> Agnes is an AI **supply chain manager** for CPG procurement teams. It turns
> fragmented BOM, supplier, and procurement data into sourcing decisions that
> are cheaper, safer, and easier to defend.

- Agnes does not just optimize for lowest cost.
- Agnes checks whether materials are substitutable **in context**.
- Agnes shows **evidence, caveats, and tradeoffs** before recommending action.
- Agnes explicitly avoids unsafe over-consolidation with an **anti-monopoly
  guard**.

## The one-sentence claim

> Agnes helps procurement teams consolidate spend **only when the substitute
> is functionally valid, commercially attractive, and still compliant.**

---

## Slide structure (5 minutes, 3 slides)

### Slide 1 — Problem (0:00 – 1:30)

> **CPG companies leave money on the table because demand is fragmented
> and substitution is hard to prove.**

Three pains:
1. **Fragmented demand** — the same ingredient is bought by many
   companies and products with no shared visibility. No volume leverage.
2. **Hidden single-source risk** — consolidation can look attractive,
   but if only 1–2 suppliers remain, a single disruption takes out the line.
3. **Compliance is the blocker** — cheaper alternatives only count if
   they are functionally valid AND meet quality / regulatory requirements.

"CPG companies leave money on the table because demand is fragmented and
substitution is hard to prove. The same ingredient is often bought by
multiple companies and products with no shared visibility — that blocks
volume leverage and creates hidden single-source risk. And consolidation
is only useful if the substitute still meets quality and compliance
requirements. Otherwise you've just traded a cost problem for a
compliance incident. Most tools stop at cost. Procurement teams need a
recommendation they can actually defend."

---

### Slide 2 — Solution (1:30 – 3:00)

> **Agnes turns fragmented procurement data into evidence-backed sourcing
> decisions.**

Three-column flow:

- **Inputs:** BOMs + supplier–product links · 2 years of procurement
  history · supplier ratings + certifications · market-benchmark pricing.
- **Reasoning:** substitution detection (variant / functional) ·
  compliance-fit checks · risk detection (5 risk types) · prioritization
  on 5 weighted dimensions.
- **Outputs:** consolidation proposals w/ evidence · substitution
  standardization · risk mitigation actions · cost-optimization.

**One engine, four surfaces:** Chat · Explorer · Insights · Cube.

**Run against:** 61 companies · 357 ingredients · 8,127 orders · $1.52B spend.

"Agnes profiles every ingredient across the network. It finds variant
and functional substitutes. It scores consolidation opportunities across
five weighted dimensions — leverage, evidence confidence, compliance fit,
diversification, switching feasibility — and produces recommendations
with evidence trails and caveats. Four surfaces: Chat, Explorer, Insights,
Cube. Same brain. Run against the real dataset: 61 companies, 357
ingredients, 40 suppliers, 8,127 procurement orders, $1.52 billion in
spend. On that dataset Agnes identified 125 consolidation opportunities,
117 substitution groups, and 89 risk items."

---

### Slide 3 — Why our approach is trustworthy (3:00 – 5:00)

> **Agnes is designed to be defensible, not just impressive.**

**Left panel — the Prioritization Framework:**

| Weight | Dimension |
|---|---|
| 0.35 | Consolidation leverage |
| 0.25 | Evidence confidence |
| 0.20 | Compliance fit |
| 0.10 | **Supplier diversification** ← anti-monopoly guard |
| 0.10 | Switching feasibility |

**Right panel — the hard rule:**

> **124 / 125** consolidation opportunities trigger the anti-monopoly veto.
>
> If consolidation would leave ≤ 2 suppliers network-wide, the grade is
> automatically downgraded. Not a heuristic — a hard rule in the code.

**Three proof points (bottom row):**

- **Beta Carotene** · `safe_to_consolidate` · 5 cos · 4 suppliers · score
  0.85 — consolidate to Prinova USA, keep 3 backups.
- **Microcrystalline Cellulose** · `review_required` · 13 cos · 2 suppliers
  · downgrade fired — partial consolidation + qualified backup.
- **Maltodextrin** · `risk_mitigation` · 1 supplier (Ingredion) · 8 cos ·
  8 products — qualify a second supplier.

"Every recommendation is tied to actual supplier, spend, and benchmark
data. The UI exposes evidence, confidence, and caveats. The system
includes an anti-monopoly guard: when full consolidation would leave the
network with two or fewer suppliers, the grade is automatically
downgraded. On our dataset that fires on 124 of 125 opportunities. Three
proof points. Beta Carotene — safe to consolidate, four suppliers, plenty
of backup. Microcrystalline Cellulose — downgraded; Agnes recommends
partial consolidation plus a qualified backup. Maltodextrin —
single-source from Ingredion; Agnes recommends qualifying a second
supplier. This is exactly what procurement teams need: not just answers,
but justification."

"We built against the actual dataset, not a toy. 54 total recommendations,
19 high-priority, all traceable to source data."

---

### Slide 8 — Team + close (4:50 – 5:00)

> **Agnes turns fragmented procurement data into sourcing decisions teams
> can defend.**
>
> *Trustworthy sourcing, not just cheaper sourcing.*

"Happy to walk through the code, the math, or any example."

---

## 60-second version (1-minute talking format)

"CPG companies overpay because the same ingredients are sourced in
fragmented ways across products, plants, and even companies. But
consolidation only works if the alternative is truly substitutable and
still compliant.

We built Agnes, an AI supply chain manager that reasons across BOMs,
supplier relationships, procurement history, quality signals, and market
benchmarks to recommend sourcing actions teams can actually trust.

On our dataset, Agnes analyzed 357 ingredients and over 8,000 orders,
identified 125 consolidation opportunities, 117 substitution groups, and
89 risk items — then turned them into evidence-backed recommendations.

What makes Agnes different is that it does not blindly chase the cheapest
supplier. It exposes confidence, caveats, and even blocks unsafe
over-consolidation with an anti-monopoly guard.

So instead of just saying 'buy this cheaper material,' Agnes tells
procurement teams what to consolidate, what to standardize, what to
dual-source, and why."

---

## 1-minute demo script

"Agnes has already analyzed the full network: 61 companies, 357
ingredients, 40 suppliers, and over 8,000 orders.

On the Recommendations tab, Agnes surfaces high-priority sourcing actions
with evidence and caveats. Beta Carotene can be safely consolidated —
five companies, four suppliers, plenty of backups.

Compare with Microcrystalline Cellulose. Agnes sees strong consolidation
leverage, but it downgrades the recommendation because full consolidation
would create concentration risk. The anti-monopoly guard is important
because procurement teams need resilience, not just lower prices.

Agnes also detects standardization opportunities, like Vitamin D3 variants
used across 22 companies, and highlights cost spreads such as Vitamin A
Palmitate — where a qualified supplier change could save roughly
$600,000.

So the output isn't just an answer. It's a sourcing proposal with
evidence, tradeoffs, and trust built in."

---

## Speaker cheat-sheet

**Numbers to memorize**
- 61 companies · 149 finished goods · 876 raw materials · 357 ingredients
- 40 suppliers · 8,127 procurement orders · $1.52B historical spend
- 117 substitution groups · 125 consolidation opportunities · 89 risk items
- 54 recommendations (19 high-priority)
- **124 / 125** consolidation opportunities trigger the monopoly veto

**Architecture (keep short)**
Python + Flask backend, SQLite + SQLAlchemy data layer, gpt-4o-mini for
tool-based natural-language analysis, custom scoring engine for
substitution/consolidation/risk, lightweight HTML/CSS/JS dashboards for
explainability.

> "We intentionally kept the stack simple and focused effort on decision
> quality, evidence handling, and explainability."

**External enrichment — what to claim**
- ✅ Architecture is ready for certifications, regulatory references,
  supplier pages, label evidence.
- ❌ Don't claim live web enrichment is already running.
- ❌ Don't claim end-to-end automated compliance.

**"Why not just consolidate fully?"**
"Because 124 out of 125 times the math says you shouldn't. Monopoly risk
compounds — one supplier failure takes out an ingredient line across every
company downstream. Agnes keeps a qualified backup: you retain ~90% of
the negotiating leverage and you don't lose the business when a factory
burns."

**"Where do you use LLMs, exactly?"**
"Three places. Chat dispatches SQL queries — data comes from the database,
not the model. Evidence extraction for substitutes cites sources.
Optional prose polish on recommendation summaries. In all three, the LLM
**cannot change a score, a grade, or a supplier.** Scoring is pure Python."

**One-liner (if cut off)**
> "Agnes doesn't find the cheapest supplier. It finds the sourcing
> decision you can actually defend to a CFO."

---

## What not to demo

- ❌ Cube (visually cool but off-message for judging)
- ❌ Raw table browsing
- ❌ Any live external enrichment you can't show working

## Closing lines (pick one)

1. "Agnes turns fragmented procurement data into sourcing decisions teams
   can defend."
2. "The value isn't just cheaper sourcing. It's trustworthy sourcing."
3. "In supply chain, the best recommendation is the one a buyer can
   actually act on."
