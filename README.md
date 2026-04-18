# AgnesTheSecond

Decision-support platform for CPG procurement teams. Analyses BOMs,
supplier coverage, procurement history, and market-benchmark pricing to
surface consolidation opportunities, substitution candidates, and
supply-chain risks with evidence trails attached.

## Features

- **Ingredient profiling** — functional categorization, allergen
  detection, cross-company usage, per-supplier pricing.
- **Substitution detection** — direct, variant, and functional matches
  with Jaccard similarity and semantic root clustering.
- **Consolidation analysis** — cross-company supplier coverage, cost
  modelling against the benchmark, prioritization on five weighted
  dimensions (leverage, evidence confidence, compliance fit, supplier
  diversification, switching feasibility).
- **Risk register** — single-source, supplier concentration, critical
  ingredient, supplier quality, price volatility.
- **Conversational agent** — OpenAI `gpt-4o-mini` with tool-calling over
  the SQLite database; voice interface via ElevenLabs.
- **Purchase-order drafting** — LLM extracts structured order fields
  from a conversation, resolves supplier / product / buyer against the
  catalogue, and renders a PDF.

## Prioritization framework

| Weight | Dimension                   |
| :----: | --------------------------- |
|  0.35  | Consolidation leverage      |
|  0.25  | Evidence confidence         |
|  0.20  | Compliance fit              |
|  0.10  | Supplier diversification    |
|  0.10  | Switching feasibility       |

If consolidating to the best supplier would leave ≤ 2 suppliers
network-wide for that ingredient, the grade is downgraded from
`safe_to_consolidate` to `review_required`.

## Surfaces

| Route         | Description |
| ------------- | ----------- |
| `/`           | Chat agent. |
| `/explorer/`  | Ingredient, supplier, graph, procurement, and table browser. |
| `/agnes/`     | Recommendations dashboard. |
| `/cube/`      | Voice interface. |
| `/orders/…`   | Purchase-order extraction and PDF generation. |

## Dataset

61 companies · 149 finished goods · 876 raw materials · 357 ingredients
· 40 suppliers · 8,127 procurement orders · $1.52 B historical spend.

Core tables come from the hackathon dataset. Mock procurement tables
(`Supplier_Rating`, `Price_Benchmark`, `Procurement_History`) are
deterministically seeded by `taim/generate_mock_data.py`. Conversation
and order tables are created on first request.

## Getting started

Requires Python 3.11+ and an `OPENAI_API_KEY`.

```bash
git clone https://github.com/PRONGS-CHIRAG/AgnesTheSecond.git
cd AgnesTheSecond/taim
python -m venv .venv && source .venv/bin/activate
pip install flask flask-cors sqlalchemy openai reportlab

python generate_mock_data.py
OPENAI_API_KEY=sk-... python app.py
```

## Configuration

| Variable            | Purpose |
| ------------------- | ------- |
| `OPENAI_API_KEY`    | Required for Chat, Cube, and order extraction. |
| `AGNES_ORDER_MODEL` | Overrides the extractor model (default `gpt-4o-mini`). |

## Project layout

```
taim/
├─ app.py              Flask entrypoint
├─ generate_mock_data.py
├─ chat/               Chat agent (blueprint at /)
├─ explorer/           Data explorer (blueprint at /explorer/)
├─ insights/           Analysis engine + recommendations UI (/agnes/)
├─ cube/               Voice interface (blueprint at /cube/)
└─ orders/             Order extraction, storage, PDF (blueprint at /orders/)
hackathon-tumai/
└─ db.sqlite           SQLite dataset
```

See [taim/README.md](taim/README.md) for the internal architecture.

## License

[MIT](LICENSE) © 2026 Chirag Natesh Vijay.
