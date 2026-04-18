# AgnesTheSecond

**AI supply chain manager for CPG procurement.**
Cheaper. Safer. Defensible.

Agnes turns fragmented BOM, supplier, and procurement data into sourcing
recommendations a buyer can actually act on. Built for the **TUM.ai ×
Spherecast Makeathon 2026**.

---

## Table of contents

- [What Agnes does](#what-agnes-does)
- [The prioritization framework](#the-prioritization-framework)
- [The app](#the-app)
- [Dataset at a glance](#dataset-at-a-glance)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Repository layout](#repository-layout)
- [License](#license)

---

## What Agnes does

Most procurement tools stop at cost. Agnes reasons across BOM structure,
supplier coverage, procurement history, quality and compliance signals,
and substitution logic, then recommends sourcing actions with evidence,
caveats, and tradeoffs surfaced up-front.

**Inputs**

- Bills of materials + supplier / product links
- Two years of procurement history
- Supplier ratings and certifications
- Market-benchmark pricing

**Reasoning**

- Ingredient profiling and functional categorization
- Multi-level substitution detection (variant / functional)
- Cross-company consolidation analysis with cost modelling
- Five-type risk assessment (single-source, supplier concentration,
  critical ingredient, supplier quality, price volatility)
- Five-dimension prioritization framework with an anti-monopoly guard

**Outputs**

- Consolidation proposals with evidence trails and caveats
- Substitution standardization recommendations
- Risk mitigation actions (second-source qualification)
- Cost-optimization opportunities with benchmark-backed savings estimates
- LLM-drafted purchase-order PDFs that extract structured order data from
  the conversation and deterministically validate it against the catalogue

---

## The prioritization framework

Every consolidation recommendation is scored on five explicit dimensions
and combined into a single weighted score.

| Weight | Dimension                    |
| :----: | ---------------------------- |
|  0.35  | Consolidation leverage       |
|  0.25  | Evidence confidence          |
|  0.20  | Compliance fit               |
|  0.10  | **Supplier diversification** (anti-monopoly guard) |
|  0.10  | Switching feasibility        |

**Hard rule:** if consolidating to the best supplier would leave
≤ 2 suppliers network-wide for that ingredient, the grade is automatically
downgraded from `safe_to_consolidate` to `review_required`. It is a rule
in the code, not a heuristic.

On the hackathon dataset, **124 of 125 consolidation opportunities trigger
this veto** — a naive tool would recommend full consolidation on every
one of them; Agnes flags 124 for review and backs only the one that is
actually safe.

---

## The app

A single Flask app with one deterministic analysis engine and five
surfaces that share it.

| Surface    | Route           | Purpose |
| ---------- | --------------- | ------- |
| Chat       | `/`             | Natural-language agent (OpenAI gpt-4o-mini) that dispatches real SQL queries + BOM analysis + substitute lookups against the database. |
| Explorer   | `/explorer/`    | Five-tab interactive browser for ingredients, suppliers, supply-chain graph, procurement analytics, and raw tables. |
| Insights   | `/agnes/`       | Recommendations dashboard with grade badges, the tension-matrix for every consolidation opportunity, evidence trails, and caveats. |
| Cube       | `/cube/`        | Voice interface (ElevenLabs TTS/STT) over the same chat agent, with transcription pre-processing for intent and entity extraction. |
| Orders     | `/orders/…`     | LLM-drafted purchase orders. Every chat turn is persisted to SQLite; the extractor pulls structured order fields from the conversation, deterministically validates supplier / product / buyer against the catalogue, and renders a minimal PO as a PDF that shows inline in the chat's right panel. Triggered automatically when a user turn matches an order-intent pattern. |

The analysis engine at [taim/insights/agnes_engine.py](taim/insights/agnes_engine.py)
(~1,500 lines) is pure Python: loads the DB once, runs the full pipeline,
caches the result as a lazy-initialized singleton. Determinism is the
spine — same inputs, same outputs, every time. LLMs are scoped to
natural-language interfaces and never change a score, a grade, or a
supplier.

---

## Dataset at a glance

| Count | What |
| ----: | ---- |
| 61    | companies |
| 149   | finished goods |
| 876   | raw materials |
| 357   | unique ingredients |
| 40    | suppliers |
| 8,127 | procurement orders |
| $1.52B | historical procurement spend |
| 117   | substitution groups detected |
| 125   | consolidation opportunities identified |
| 89    | supply-chain risk items flagged |
| 54    | total recommendations (19 high-priority) |

Original tables (`Company`, `Product`, `BOM`, `BOM_Component`, `Supplier`,
`Supplier_Product`) come from the hackathon dataset. Mock procurement
tables (`Supplier_Rating`, `Price_Benchmark`, `Procurement_History`) are
generated once by [taim/generate_mock_data.py](taim/generate_mock_data.py)
with a fixed seed so the dataset is fully reproducible. The order
blueprint adds `Conversation`, `ConversationMessage`, `Order`, and
`OrderItem`; schema is created on first request — no migration needed.

---

## Quick start

Requires Python 3.11+ and an `OPENAI_API_KEY` for the LLM-backed
surfaces (Chat, Cube, Orders).

```bash
git clone https://github.com/PRONGS-CHIRAG/AgnesTheSecond.git
cd AgnesTheSecond/taim
python -m venv .venv && source .venv/bin/activate
pip install flask flask-cors sqlalchemy openai reportlab

python generate_mock_data.py          # one-time, seeds mock procurement data
OPENAI_API_KEY=sk-... python app.py
```

The server binds to `0.0.0.0:5050` (port 5000 is avoided to sidestep
macOS AirPlay Receiver).

---

## Environment variables

Copy [.env.example](.env.example) as reference. Only `OPENAI_API_KEY` is
required to run the full app; Agnes's analysis engine runs without any
external credentials.

| Variable            | Required | Purpose |
| ------------------- | -------- | ------- |
| `OPENAI_API_KEY`    | chat / cube / orders | OpenAI access for gpt-4o-mini. Can also be supplied per-request via the chat UI. |
| `AGNES_ORDER_MODEL` | optional | Override the model used by the order extractor (default `gpt-4o-mini`). |

Per-tool rate-limit and cache knobs exist for completeness and are
documented in the example file. They have sensible defaults.

---

## Repository layout

```
AgnesTheSecond/
├─ README.md                  ← you are here
├─ PITCH.md                   ← speaker script + demo notes + FAQ
├─ PITCH.pptx                 ← 3-slide pitch deck (regeneratable)
├─ LICENSE                    ← MIT
├─ .env.example
├─ scripts/
│  └─ build_pitch_pptx.py     ← regenerate PITCH.pptx from Python
├─ hackathon-tumai/
│  ├─ db.sqlite               ← the challenge dataset
│  └─ TUM.ai x Spherecast.docx
└─ taim/
   ├─ README.md               ← detailed Flask-app documentation
   ├─ app.py                  ← entrypoint, registers all blueprints
   ├─ generate_mock_data.py   ← one-time seeding of mock procurement tables
   ├─ chat/                   ← Blueprint at `/`
   ├─ explorer/               ← Blueprint at `/explorer/`
   ├─ insights/               ← Blueprint at `/agnes/` + the analysis engine
   ├─ cube/                   ← Blueprint at `/cube/` (voice)
   └─ orders/                 ← Blueprint at `/orders/`: storage,
                                extractor, pdf_generator, routes
```

For a deep technical tour of `taim/` (schema, analysis pipeline,
substitution logic, risk types, recommendation types, chat agent tools,
explorer APIs) read [taim/README.md](taim/README.md).

---

## Credits

Built by Team Agnes for the **TUM.ai × Spherecast Makeathon 2026**.

## License

[MIT](LICENSE) © 2026 Chirag Natesh Vijay.
