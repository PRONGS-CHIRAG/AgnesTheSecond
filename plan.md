````md
# Agnes Hackathon Plan
## Evidence-Grounded Raw Material Substitution and Sourcing Consolidation System

**Project codename:** Agnes The Second  
**Challenge:** Spherecast / AI Supply Chain Manager  
**Primary goal:** Build an AI decision-support system that identifies functionally substitutable raw materials, verifies likely compliance and quality fit using internal and external evidence, and recommends sourcing consolidation opportunities with clear evidence trails and uncertainty handling.

---

# 1. Mission

We are building an internal AI procurement intelligence system for CPG sourcing.

The system must:
1. Ingest organizer-provided BOM and supplier data from a SQLite database.
2. Understand relationships across companies, finished goods, BOMs, raw materials, and suppliers.
3. Detect functionally interchangeable raw materials.
4. Infer likely quality and compliance constraints in the context of the finished product.
5. Enrich incomplete internal data with external evidence.
6. Recommend sourcing consolidation opportunities.
7. Explain reasoning, evidence, tradeoffs, and uncertainty.

This is **not** a generic chatbot.  
This is **not** just cost optimization.  
This is **not** shallow ingredient matching.

This is an **evidence-grounded procurement decision system**.

---

# 2. Core Product Thesis

Procurement teams miss savings because the same or similar ingredients are sourced in fragmented ways across products, plants, business units, or companies. However, consolidation is only valuable if substitutes are truly acceptable in the context of the finished product.

Agnes should answer:

- Which raw materials are likely substitutes?
- Are they acceptable in the context of the end product?
- Can sourcing be consolidated safely?
- What evidence supports the recommendation?
- What is still uncertain and needs review?

---

# 3. What Winning Looks Like

A strong result includes:

- A working pipeline from database -> substitute candidates -> evidence enrichment -> recommendation
- At least one strong end-to-end demo flow
- Clear evidence trails
- Explicit confidence and uncertainty handling
- Business-relevant sourcing recommendations
- Minimal but usable UI
- Strong architecture and explanation

A weak result would be:

- Generic chatbot interface
- Similarity-only matching
- No uncertainty handling
- Unsupported compliance claims
- Heavy UI with weak reasoning
- Overbuilt orchestration and underbuilt logic

---

# 4. Technical Stack

## Required core stack
- Python
- SQLite
- Pandas
- SQLAlchemy
- Pydantic
- FastAPI or lightweight Python service layer if needed
- Streamlit or Gradio or lightweight web app for demo UI

## Core intelligence infrastructure
- **Google Cloud**
  - model access
  - embeddings if needed
  - retrieval and document handling if needed
  - optional deployment backend
- **Cognee**
  - procurement memory
  - knowledge graph / GraphRAG style retrieval
  - multi-hop entity reasoning
  - persistent memory layer for suppliers, materials, evidence, certifications, and decisions

## Optional only at the end
- **ElevenLabs**
  - optional voice summary / narrated Agnes recommendation
  - only after core pipeline is fully working

---

# 5. Non-Goals

Do not spend time building the following unless explicitly prioritized later:

- perfect full-scale web scraping infrastructure
- a beautiful polished enterprise frontend
- a universal compliance engine covering all regulations
- a full ERP replacement
- a fully general optimizer for all supply-chain cases
- a chat agent with broad generic conversational scope
- complicated infrastructure that slows down hackathon progress

---

# 6. Domain Understanding

## Key entities in the database
- **Company**: end brand / company
- **Product**: can be either `finished-good` or `raw-material`
- **BOM**: bill of materials belonging to a finished-good product
- **BOM_Component**: raw materials contained in a BOM
- **Supplier**: vendor
- **Supplier_Product**: mapping that shows a supplier can supply a raw material

## Mental model
`Company -> Finished Product -> BOM -> BOM Components -> Raw Materials -> Supplier_Product -> Supplier`

## Important challenge constraints
- scope is only raw ingredients / raw materials
- finished goods have BOMs
- suppliers only map to raw materials
- substitution is not just name similarity
- compliance and quality acceptability depends on end-product context
- external evidence is incomplete and messy
- uncertainty must be surfaced explicitly

---

# 7. Product Scope for MVP

We will build a focused MVP that does a few things well.

## MVP must do
1. Load and analyze challenge database
2. Build a demand and sourcing view across raw materials
3. Normalize raw material names
4. Generate substitute candidates
5. Enrich selected candidates with external evidence
6. Score candidate substitutions
7. Produce sourcing consolidation recommendations
8. Explain tradeoffs and uncertainty

## MVP should not attempt
- solve every ingredient family perfectly
- cover every regulation globally
- create a fully autonomous sourcing system
- replace human QA / procurement review

---

# 8. Product Outputs

Agnes should produce structured outputs such as:

## A. Raw material profile
- canonical material name
- ingredient family
- functional role
- known suppliers
- related finished goods
- likely substitute cluster

## B. Substitute assessment
- original material
- candidate substitute
- functional fit assessment
- compliance fit assessment
- quality fit assessment
- supplier impact
- evidence summary
- confidence score
- uncertainty notes
- recommendation class

## C. Sourcing recommendation
- current fragmented sourcing picture
- proposed consolidation opportunity
- suppliers involved
- expected benefit
- risk areas
- evidence trail
- required manual reviews

---

# 9. Recommendation Classes

The system must avoid false certainty.

Use these classes:

- **Safe to consolidate**
- **Likely safe, review required**
- **Potential substitute, insufficient evidence**
- **Not recommended**

Each recommendation must include:
- confidence level
- supporting evidence
- missing evidence
- rationale
- tradeoff explanation

---

# 10. High-Level Architecture

## Layer 1: Data ingestion and relational understanding
Purpose:
- parse SQLite database
- inspect schema
- load into analysis-friendly structures
- compute base entity relationships

Outputs:
- relational views
- summary tables
- company -> finished product -> BOM -> raw material chains
- supplier coverage views

## Layer 2: Procurement memory and knowledge graph
Purpose:
- represent internal entities and relationships in a persistent knowledge layer
- support GraphRAG / multi-hop retrieval

Tool:
- **Cognee**

Entities to store:
- company
- finished product
- BOM
- raw material
- supplier
- supplier product
- ingredient family
- functional role
- certification
- evidence source
- substitute candidate
- recommendation

Relationships to store:
- company owns product
- product has BOM
- BOM contains raw material
- supplier offers raw material
- raw material belongs to family
- raw material may substitute raw material
- evidence supports claim
- product implies constraints
- supplier has certification
- recommendation supported by evidence

## Layer 3: Canonicalization and substitute discovery
Purpose:
- normalize raw material identities
- reduce naming fragmentation
- generate likely substitute candidates

Methods:
- lexical normalization
- embedding similarity
- taxonomy inference
- LLM-assisted canonicalization
- heuristic grouping by descriptors and roles

## Layer 4: External evidence enrichment
Purpose:
- gather missing evidence from public sources for top substitute candidates

Evidence sources may include:
- supplier product pages
- product descriptions
- certification pages
- public databases
- packaging or label references
- regulatory references
- product listings

## Layer 5: Context and compliance reasoning
Purpose:
- determine whether a substitute is likely acceptable in the context of a finished product

Reason over:
- functional equivalence
- likely formulation role
- likely compliance constraints
- likely quality / sensory fit
- evidence quality
- missing information

## Layer 6: Recommendation and optimization
Purpose:
- identify high-value consolidation opportunities and rank them

Consider:
- supplier consolidation potential
- likely leverage
- confidence of substitution
- evidence sufficiency
- operational feasibility
- concentration risk

## Layer 7: Demo UI
Purpose:
- show one clear end-to-end decision flow
- provide evidence trail and recommendation view

---

# 11. Knowledge Graph / Memory Design

## Why Cognee is central
The challenge requires more than flat retrieval. We need entity memory, relationships, evidence trails, and multi-hop reasoning.

Cognee should store:
- canonical raw materials
- supplier mappings
- substitute relations
- certifications
- evidence fragments
- prior decisions
- confidence metadata

## Example entity schema ideas

### RawMaterial
- id
- raw_name
- canonical_name
- ingredient_family
- functional_role
- descriptors
- normalized_text
- source_product_ids
- supplier_ids

### SupplierOffer
- supplier_id
- raw_material_id
- offer_name
- extracted_attributes
- evidence_refs

### EvidenceRecord
- id
- source_type
- source_url_or_ref
- extracted_text
- structured_claims
- confidence
- retrieval_timestamp

### SubstituteCandidate
- source_material_id
- candidate_material_id
- similarity_score
- role_match_score
- evidence_score
- final_confidence

---

# 12. Google Cloud Usage Plan

Google Cloud is part of the core plan.

Use Google Cloud for:
- model inference
- embeddings where useful
- retrieval support if needed
- optional API deployment
- optional hosting / service endpoints

Google Cloud should support:
- canonicalization prompts
- substitute reasoning prompts
- evidence extraction prompts
- recommendation explanation prompts

Do not overcomplicate this with too many managed services if that slows down build speed.

Use Google Cloud as:
- reliable AI backend
- enterprise-grade infrastructure story
- scalable deployment base if time allows

---

# 13. ElevenLabs Usage Plan

**ElevenLabs is optional and should be added only at the end.**

Possible optional feature:
- Agnes speaks a short recommendation summary

Examples:
- narrated sourcing briefing
- voice-based executive summary
- optional audio explanation in demo

This must never block core system delivery.

Priority order:
1. core logic
2. evidence trails
3. demo UI
4. optional ElevenLabs polish

---

# 14. Functional Modules

## Module 1: Database Loader
Responsibilities:
- load SQLite file
- inspect schema
- load tables into DataFrames / ORM models
- validate row counts and relationships
- expose helper query functions

Deliverables:
- schema summary
- entity counts
- reusable data access module

## Module 2: BOM Analyzer
Responsibilities:
- trace raw materials used by finished goods
- identify repeated raw materials across products and companies
- generate demand overlap views
- detect supplier fragmentation opportunities

Deliverables:
- repeated raw-material report
- cross-company ingredient overlap view
- supplier overlap matrix

## Module 3: Material Canonicalizer
Responsibilities:
- clean raw material names
- infer canonical names
- extract descriptors
- assign ingredient family
- assign functional role where possible

Deliverables:
- normalized material table
- canonical material clusters

## Module 4: Substitute Candidate Generator
Responsibilities:
- generate likely substitute candidates
- use lexical, embedding, and reasoning signals
- rank candidate substitutes

Deliverables:
- candidate substitute list per raw material
- substitute similarity and confidence metadata

## Module 5: External Evidence Retriever
Responsibilities:
- search public sources for supplier and ingredient evidence
- extract useful snippets
- record evidence provenance
- capture structured claims

Deliverables:
- evidence records
- certification mentions
- product descriptors
- public source references

## Module 6: Compliance and Context Reasoner
Responsibilities:
- assess substitute suitability in context
- reason over role, claims, quality fit, compliance fit
- identify gaps / uncertainty

Deliverables:
- structured verdicts
- recommendation class
- evidence-based rationale
- uncertainty flags

## Module 7: Recommendation Engine
Responsibilities:
- compute sourcing consolidation opportunities
- combine substitution quality and sourcing impact
- score and rank opportunities

Deliverables:
- ranked recommendation list
- before/after supplier picture
- risk-adjusted sourcing proposals

## Module 8: Demo UI
Responsibilities:
- allow exploration of a selected raw material or product
- show evidence, substitute candidates, and recommendations
- keep interface simple and business-oriented

Deliverables:
- working UI flow
- one strong scenario demo

## Module 9: Optional Voice Layer
Responsibilities:
- generate a short spoken Agnes summary
- summarize top recommendation only

Deliverables:
- optional audio demo

---

# 15. Suggested Repository Structure

```text
agnes-hackathon/
├── README.md
├── plan.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/
│   │   └── db.sqlite
│   ├── interim/
│   └── processed/
├── notebooks/
│   ├── 01_schema_exploration.ipynb
│   ├── 02_material_overlap.ipynb
│   └── 03_substitute_validation.ipynb
├── src/
│   ├── config/
│   │   └── settings.py
│   ├── data/
│   │   ├── db_loader.py
│   │   ├── schema_summary.py
│   │   └── queries.py
│   ├── models/
│   │   ├── domain_models.py
│   │   ├── pydantic_outputs.py
│   │   └── graph_models.py
│   ├── graph/
│   │   ├── cognee_client.py
│   │   ├── graph_ingest.py
│   │   └── graph_queries.py
│   ├── canonicalization/
│   │   ├── text_cleaning.py
│   │   ├── canonicalizer.py
│   │   └── role_classifier.py
│   ├── substitutes/
│   │   ├── candidate_generator.py
│   │   ├── similarity_scoring.py
│   │   └── clustering.py
│   ├── retrieval/
│   │   ├── google_cloud_client.py
│   │   ├── search_external_sources.py
│   │   └── evidence_extractor.py
│   ├── reasoning/
│   │   ├── compliance_reasoner.py
│   │   ├── context_reasoner.py
│   │   ├── recommendation_reasoner.py
│   │   └── uncertainty.py
│   ├── optimization/
│   │   ├── scoring.py
│   │   └── rank_recommendations.py
│   ├── ui/
│   │   └── app.py
│   ├── utils/
│   │   ├── logging.py
│   │   ├── io.py
│   │   └── helpers.py
│   └── main.py
├── outputs/
│   ├── reports/
│   ├── evidence/
│   ├── recommendations/
│   └── demo_assets/
└── tests/
    ├── test_db_loader.py
    ├── test_canonicalizer.py
    ├── test_candidate_generator.py
    ├── test_reasoner.py
    └── test_scoring.py
````

---

# 16. Core Data Contracts

Use strict structured outputs via Pydantic.

## Example output: SubstituteAssessment

```python
class SubstituteAssessment(BaseModel):
    source_material: str
    candidate_material: str
    ingredient_family: str | None
    functional_role_match: float
    compliance_fit_score: float
    quality_fit_score: float
    evidence_confidence: float
    recommendation_class: Literal[
        "safe_to_consolidate",
        "likely_safe_review_required",
        "potential_substitute_insufficient_evidence",
        "not_recommended",
    ]
    rationale: str
    missing_information: list[str]
    supporting_evidence: list[str]
```

## Example output: SourcingRecommendation

```python
class SourcingRecommendation(BaseModel):
    raw_material_cluster: str
    current_suppliers: list[str]
    recommended_suppliers: list[str]
    consolidation_benefit_score: float
    confidence_score: float
    risk_notes: list[str]
    tradeoff_summary: str
    review_required: bool
```

Claude Code should implement all LLM-facing outputs as typed models.

---

# 17. Scoring Strategy

Use a transparent scoring framework rather than a black-box decision.

## Suggested dimensions

* substitute similarity score
* functional role fit
* evidence confidence
* compliance fit
* quality fit
* supplier consolidation benefit
* operational risk
* concentration risk
* missing evidence penalty

## Suggested overall logic

Final recommendation should be based on:

* candidate quality
* evidence sufficiency
* business benefit
* risk penalties

Do not present raw numeric precision as truth.
Scores are decision support, not guarantees.

---

# 18. Uncertainty Handling

This is critical.

Agnes must explicitly surface:

* what is known
* what is inferred
* what evidence supports it
* what is missing
* what needs manual review

Examples:

* "Functional equivalence appears likely, but certification evidence is incomplete."
* "Supplier consolidation is attractive, but formulation sensitivity is uncertain."
* "Recommendation is suitable for procurement review, not direct execution."

Never claim regulatory certainty without solid evidence.
Never hide low-confidence cases.

---

# 19. Demo Flow

The demo should focus on one strong business story.

## Preferred demo sequence

1. Select a finished product or raw material cluster
2. Show current fragmented sourcing picture
3. Show normalized material cluster and substitute candidates
4. Show evidence retrieved for top candidates
5. Show Agnes recommendation
6. Show risk and uncertainty flags
7. Show before vs after sourcing consolidation view

## Demo message

Agnes helps procurement teams move from fragmented purchasing to evidence-backed consolidation, while maintaining trust through explainability and uncertainty awareness.

---

# 20. Execution Phases

## Phase 0: Setup

Tasks:

* initialize repository
* create environment and config
* connect SQLite database
* verify Google Cloud access
* verify Cognee setup
* create basic project skeleton

Deliverables:

* working repo
* environment variables template
* db access test
* model access test
* Cognee connectivity test

## Phase 1: Data understanding

Tasks:

* inspect schema
* load all core tables
* count entities
* map table relationships
* identify repeated raw materials
* identify supplier fragmentation patterns

Deliverables:

* schema summary script
* basic EDA notebook
* overlap report

## Phase 2: Canonicalization pipeline

Tasks:

* normalize raw material names
* remove naming noise
* infer canonical names
* infer ingredient family and role
* generate structured normalized table

Deliverables:

* normalized material registry
* canonicalization logic

## Phase 3: Build knowledge graph memory

Tasks:

* define graph entities and edges
* ingest normalized data into Cognee
* store supplier and product relationships
* expose retrieval functions

Deliverables:

* graph ingest pipeline
* graph query helpers
* persistent procurement memory

## Phase 4: Substitute candidate generation

Tasks:

* generate candidate substitutes for target materials
* combine lexical and semantic signals
* filter low-quality candidates
* rank candidates

Deliverables:

* candidate generation module
* substitute candidate records

## Phase 5: External evidence enrichment

Tasks:

* search public sources for top candidates
* extract relevant evidence
* record evidence provenance
* map evidence to materials and suppliers

Deliverables:

* evidence retrieval module
* evidence records with source metadata

## Phase 6: Context and compliance reasoning

Tasks:

* assess substitute acceptability in context
* produce structured verdicts
* classify recommendation level
* log uncertainty

Deliverables:

* assessment engine
* typed substitute verdicts

## Phase 7: Recommendation engine

Tasks:

* compute consolidation opportunity scores
* combine substitute confidence and sourcing benefit
* rank opportunities
* generate recommendation summaries

Deliverables:

* recommendation ranking
* business-oriented output tables

## Phase 8: Demo UI

Tasks:

* create simple user flow
* display materials, evidence, verdicts, and sourcing proposals
* keep UI functional and clean

Deliverables:

* demo app

## Phase 9: Optional voice feature

Tasks:

* integrate ElevenLabs
* generate voice narration for top recommendation
* keep it optional and non-blocking

Deliverables:

* optional narrated recommendation

---

# 21. Priority Ordering for Claude Code

Claude Code should execute in this order:

## Must do first

1. repository structure
2. config and environment
3. database loader
4. schema exploration
5. core relational queries
6. normalized material pipeline

## Must do next

7. Cognee integration
8. graph ingestion
9. candidate substitute generation
10. evidence retrieval skeleton
11. reasoning models and structured outputs

## Then

12. recommendation scoring
13. UI demo
14. demo scenario data

## Only at the very end

15. ElevenLabs voice layer

---

# 22. Engineering Principles

Claude Code must follow these principles:

## Principle 1: Structured outputs first

Every AI reasoning step should return typed, validated structured data.

## Principle 2: Keep modules separable

Canonicalization, retrieval, reasoning, and scoring must be independently testable.

## Principle 3: Deterministic where possible

Use heuristics and explicit logic for data cleaning and scoring where reasonable. Reserve LLMs for inference-heavy tasks.

## Principle 4: Preserve provenance

Every extracted or inferred claim should be traceable to a source or reasoning step.

## Principle 5: Make uncertainty explicit

No silent assumptions.

## Principle 6: Optimize for demo trustworthiness, not over-automation

This is a decision-support system.

## Principle 7: Build a startup-worthy architecture, but do not over-engineer hackathon execution

Speed matters.

---

# 23. Prompting Guidelines for Claude Code

When implementing LLM-powered steps, Claude Code should:

* use small, explicit prompts
* request structured JSON only
* separate extraction from reasoning
* separate reasoning from ranking
* never mix too many tasks in one prompt
* include uncertainty fields in every non-trivial output
* avoid long free-form outputs inside the pipeline

---

# 24. Testing Requirements

Minimum tests should cover:

* database loading
* entity relationship assumptions
* raw material normalization behavior
* substitute candidate generation logic
* structured output validation
* recommendation scoring logic

At minimum, create:

* smoke tests for pipeline modules
* one integration test for a small end-to-end path

---

# 25. Logging and Observability

Add logs for:

* db load success
* row counts
* canonicalization actions
* candidate generation results
* evidence retrieval attempts
* reasoning decisions
* scoring outputs
* error paths

Use clean structured logs where practical.

---

# 26. Security / Safety / Reliability Notes

* Do not fabricate compliance claims
* Do not claim certification unless backed by evidence
* Do not drop provenance
* Do not silently rewrite source data
* Do not overstate optimizer recommendations
* Always preserve uncertainty and review requirement when evidence is partial

---

# 27. Presentation Narrative Alignment

The codebase should support the following pitch story:

> Agnes is an evidence-grounded procurement intelligence system for CPG sourcing. It connects fragmented BOM and supplier data, identifies likely raw material substitutes, enriches the decision with external evidence, and recommends sourcing consolidation opportunities with transparent tradeoffs and uncertainty handling.

The architecture should support these claims:

* internal data + external evidence
* knowledge graph memory via Cognee
* scalable AI backend via Google Cloud
* explainable sourcing decisions
* human-in-the-loop trust model

---

# 28. Stretch Goals

Only if core MVP is complete:

* richer compliance rule layer
* better visual graph explanation view
* scenario comparison mode
* procurement opportunity dashboard
* supplier concentration simulation
* optional voice summary via ElevenLabs
* feedback loop for accepted/rejected sourcing decisions

---

# 29. What Not To Do

Claude Code should avoid:

* spending hours on frontend polish
* turning everything into a chat interface
* building complicated orchestration before basic logic works
* trying to scrape too many sources early
* relying only on embeddings for substitution logic
* making unsupported quality or compliance claims
* blocking core delivery on optional features

---

# 30. Immediate First Tasks for Claude Code

Start with these tasks in order:

1. Create repository structure from this plan
2. Add `requirements.txt` and `.env.example`
3. Implement database loader for SQLite
4. Implement schema summary script
5. Implement relational query helpers for:

   * company -> products
   * finished product -> BOM
   * BOM -> raw materials
   * raw material -> suppliers
6. Produce initial analysis of:

   * number of companies
   * number of finished goods
   * number of raw materials
   * number of suppliers
   * repeated raw materials across finished goods
7. Implement material normalization pipeline
8. Draft Pydantic output models
9. Add Cognee integration scaffold
10. Add Google Cloud client scaffold
11. Create a first end-to-end pipeline for one selected raw material cluster

---

# 31. Final Build Philosophy

Build Agnes as:

* a **decision-support system**
* grounded in **structured internal data**
* strengthened by **external evidence**
* organized through **knowledge graph memory**
* deployed with **enterprise-grade architecture**
* honest about **uncertainty**
* focused on **practical procurement value**

If tradeoffs are needed, prefer:

* clear logic over breadth
* trustworthiness over flashy automation
* one strong workflow over many shallow ones

---

# 32. Context for Claude Code

We are solving a hackathon challenge around an AI supply chain manager called Agnes.

The challenge is about fragmented sourcing in CPG companies. The same ingredient may be bought across multiple companies, plants, or product lines without full visibility into combined demand. This causes missed consolidation opportunities, weak buying leverage, and fragmented supplier relationships.

However, consolidation is only valuable if two raw materials are genuinely substitutable and still acceptable in the context of the finished product. This means the system must go beyond cost optimization and ingredient name matching.

The system should reason across:

* normalized BOM data
* supplier-product relationships
* multiple companies and finished goods
* likely ingredient function
* supplier evidence
* public product information
* certifications
* possible compliance constraints
* uncertainty and missing evidence

The database contains real companies and real products with adjusted and approximated BOMs and ingredients.

Important database interpretation:

* Company = end brand
* Product = either finished-good or raw-material
* Every finished-good has a BOM
* Each BOM has BOM components
* BOM components are raw materials
* Supplier_Product exists only for raw materials

The challenge values:

* practical usefulness
* business relevance
* reasoning quality
* evidence trails
* trustworthiness
* hallucination control
* handling of missing data
* soundness of substitution logic
* explainability
* scalable startup potential

UI polish is explicitly not the priority.

This project should be built in a way that supports both:

1. a strong hackathon demo
2. a potential startup spinout direction

---

# 33. Startup Framing

The startup version of Agnes can be framed as:

**AI Procurement Intelligence for Compliance-Aware Raw Material Substitution and Supplier Consolidation in CPG**

Core wedge:

* identify likely raw material substitutes
* assess suitability in end-product context
* consolidate fragmented sourcing
* maintain evidence-backed reasoning
* improve over time with procurement memory

Potential future moat:

* internal procurement knowledge graph
* accepted and rejected sourcing decisions
* supplier intelligence memory
* company-specific constraint learning
* evidence-backed formulation-aware sourcing decisions

The hackathon MVP should already hint at this direction.

---

# 34. Team Execution Guidance

While implementing, always prefer:

* one strong ingredient cluster over many weak ones
* one strong end-to-end workflow over many disconnected experiments
* explicit structured outputs over vague text responses
* traceability over cleverness
* reliability over novelty

Suggested practical execution sequence:

* understand the data
* find repeated raw materials
* normalize them
* build substitute candidate sets
* enrich only the most promising candidates
* reason about top cases
* generate recommendations
* build a clear demo flow

---

# 35. Suggested Demo Narrative

A possible demo narrative is:

1. Start with a finished product or a raw material used across multiple BOMs
2. Show how sourcing is fragmented today
3. Show how Agnes normalizes and groups similar raw materials
4. Show one or two candidate substitutes
5. Show external evidence retrieved for them
6. Show how Agnes evaluates fit, risks, and uncertainty
7. Show a sourcing consolidation recommendation
8. End with clear statement of:

   * what can be consolidated now
   * what needs manual review
   * what evidence is still missing

This creates trust and business relevance.

---

# 36. `what_not_to_do.md` Content Embedded Here

## Do not:

* build a generic procurement chatbot
* claim certainty where evidence is weak
* focus on frontend polish before core reasoning works
* scrape huge volumes of external data too early
* rely only on embeddings for equivalence
* collapse reasoning, extraction, and ranking into one giant prompt
* overbuild multi-agent orchestration before core modules work
* spend meaningful time on ElevenLabs before the recommendation engine works
* pretend optimization outputs are exact truth
* drop source provenance

## Always:

* preserve evidence source
* preserve uncertainty
* keep outputs structured
* keep logic modular
* keep the demo business-focused
* make recommendations reviewable by humans

---

# 37. `context.md` Content Embedded Here

## Project Summary

Agnes is an AI-powered internal procurement decision-support application for the CPG industry. It helps teams discover where fragmented raw material purchasing can be consolidated, while ensuring substitutes are likely compliant and acceptable in context.

## Business Problem

CPG companies often source the same or similar ingredients across multiple products and suppliers without consolidated visibility. This leads to:

* overpayment
* reduced negotiation leverage
* supplier fragmentation
* hidden demand overlap
* missed consolidation opportunities

But consolidation is hard because:

* materials may not truly be equivalent
* quality and compliance requirements vary by finished product
* supplier evidence is scattered
* data is incomplete and messy

## Product Promise

Agnes connects internal structured supply-chain data with external evidence and procurement memory to generate explainable sourcing recommendations.

## Product Principles

* evidence-backed
* uncertainty-aware
* human-reviewable
* context-sensitive
* business-relevant
* scalable into a startup product

## Core system promise

Agnes should help answer:

* what is likely substitutable?
* what is likely acceptable in context?
* what can be consolidated?
* what evidence supports this?
* what still needs review?

---

# 38. Claude Code Implementation Guardrails

Claude Code should:

* create clean, production-style Python modules
* add docstrings
* use type hints
* use Pydantic models for structured outputs
* avoid unnecessary abstraction until needed
* write small testable functions
* keep retrieval, reasoning, and scoring separated
* prefer deterministic preprocessing before LLM inference
* save intermediate artifacts where useful
* make logs readable
* create minimal but useful notebooks for inspection

Claude Code should not:

* put all logic in notebooks
* hide core logic inside prompts
* hardcode brittle assumptions without comments
* mix UI code with reasoning code
* introduce unnecessary frameworks unless they speed delivery

---

# 39. Final Instruction to Claude Code

Use this plan as the authoritative execution blueprint.

Start implementation immediately by:

1. creating the repository structure
2. setting up configuration and environment handling
3. implementing database ingestion and schema exploration
4. producing first data understanding outputs
5. building the normalization and canonicalization layer
6. scaffolding Cognee and Google Cloud integrations
7. implementing a first narrow end-to-end workflow for one raw material cluster
8. expanding into evidence enrichment, reasoning, recommendation scoring, and demo UI

Do not wait to design everything perfectly before coding.

Prefer:

* narrow but complete
* explainable but simple
* modular but practical
* startup-grade but hackathon-fast

Only add ElevenLabs at the very end as optional polish.

```
```
