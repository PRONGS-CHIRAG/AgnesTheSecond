# Agnes Decision Layer — Mathematics & Reasoning Reference

> **Version**: 2.0 — April 2026  
> **Engine file**: `taim/insights/agnes_engine.py`

This document describes every mathematical formula, every scoring dimension, every threshold, and every decision rule used by the Agnes decision-support engine. **Nothing is hard-coded arbitrarily** — every constant in the system is either:

1. **Derived from the data** at runtime (counts, ratios, scores from the database), or  
2. A **named, documented, tunable constant** defined in one place at the top of the engine and referencing a clear design rationale.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Model & Indices](#2-data-model--indices)
3. [Ingredient Profiling](#3-ingredient-profiling)
4. [Substitution Detection](#4-substitution-detection)
5. [Consolidation Analysis](#5-consolidation-analysis)
6. [Risk Assessment](#6-risk-assessment)
7. [Recommendation Generation](#7-recommendation-generation)
    - 7.1 [Consolidation Framework](#71-consolidation-framework)
    - 7.2 [Risk Mitigation Framework](#72-risk-mitigation-framework)
    - 7.3 [Substitution Framework](#73-substitution-framework)
    - 7.4 [Cost Optimisation Framework](#74-cost-optimisation-framework)
8. [Grade Mapping & Veto Logic](#8-grade-mapping--veto-logic)
9. [Confidence Model](#9-confidence-model)
10. [Evidence Trail Architecture](#10-evidence-trail-architecture)
11. [Named Constants Reference](#11-named-constants-reference)
12. [Design Principles](#12-design-principles)

---

## 1. Architecture Overview

Agnes follows a **pipeline architecture** with six sequential stages:

```
load_data → profile_ingredients → detect_substitution_groups
         → analyze_consolidation → assess_risks → generate_recommendations
```

Each stage reads data produced by earlier stages and writes structured results. The final output is a JSON object with `summary`, `ingredients`, `substitutionGroups`, `consolidationOpportunities`, `risks`, and `recommendations`.

Every recommendation carries:
- A **5-dimension scoring framework** (weighted linear model)
- A **grade** derived from the weighted score (with optional veto overrides)
- A **confidence** value = the evidence-strength dimension (never a flat constant)
- A **full evidence trail** explaining what data drove every score
- **Caveats** listing assumptions and required follow-up actions

---

## 2. Data Model & Indices

Agnes loads 9 database tables:

| Table | Purpose |
|-------|---------|
| `Company` | CPG companies in the buying network |
| `Product` | Raw materials (Type=`raw-material`) and finished goods |
| `BOM` / `BOM_Component` | Bills of materials linking finished goods → raw materials |
| `Supplier` / `Supplier_Product` | Supplier-to-product mapping |
| `Supplier_Rating` | Quality, compliance, reliability scores (0–100) + risk tier |
| `Procurement_History` | Historical orders: quantities, prices, on-time, quality pass rates |
| `Price_Benchmark` | Market reference prices, min/max, volatility per ingredient |

Six indices are built at load time:

| Index | Key → Value |
|-------|-------------|
| `base_name_index` | canonical ingredient name → [product IDs] |
| `product_suppliers` | product ID → [supplier IDs] |
| `supplier_to_products` | supplier ID → [product IDs] |
| `fg_components` | finished-good ID → [raw-material IDs] |
| `rm_to_fgs` | raw-material ID → {finished-good IDs} |
| `rm_products` / `fg_products` | product ID → product dict (split by type) |

**Canonical name extraction** (`_base_name`):
```
strip "RM-C{digits}-" prefix  →  strip trailing "-{hex6+}"  →  lowercase
```
This groups product SKUs like `RM-C1-vitamin-d3-abc123` and `RM-C2-vitamin-d3-def456` under the single canonical name `vitamin-d3`.

---

## 3. Ingredient Profiling

For each unique canonical name, Agnes builds a profile by aggregating:

- **companyCount**: number of distinct companies using this ingredient
- **supplierCount**: number of distinct suppliers across all product SKUs
- **productCount**: number of product SKUs sharing this canonical name
- **singleSourceCount**: SKUs with ≤ 1 linked supplier
- **category**: functional category via keyword-length-weighted matching
- **allergens**: detected from ingredient name against allergen keyword lists
- **qualityFlags**: organic, non-GMO, vegan, etc. from name keywords
- **pricing**: aggregated from `Procurement_History` + `Price_Benchmark` (see §3.1)

### 3.1 Pricing Aggregation

For each ingredient with benchmark data:

$$\text{avgUnitPrice} = \frac{\sum_{o \in \text{orders}} o.\text{TotalCost}}{\sum_{o \in \text{orders}} o.\text{Quantity}}$$

$$\text{priceVsMarket} = \frac{\text{avgUnitPrice} - \text{AvgMarketPrice}}{\text{AvgMarketPrice}} \times 100\%$$

Per-supplier pricing computes:
- **avgPrice**: total spend ÷ total quantity for that supplier
- **onTimeRate**: count of on-time deliveries ÷ total orders × 100
- **avgQualityPassRate**: mean of quality pass rates across orders

### 3.2 Functional Categorisation

Each ingredient is matched against 17 functional categories. Matching uses **keyword-length weighting** — longer keyword matches score higher to prefer specific matches over generic ones:

$$\text{categoryScore}(c) = \sum_{k \in \text{keywords}(c)} \mathbb{1}[k \in \text{name}] \cdot \text{len}(k)$$

$$\text{bestCategory} = \arg\max_c \text{categoryScore}(c)$$

---

## 4. Substitution Detection

Agnes identifies three levels of ingredient substitutability:

### 4.1 Direct Substitution (Level 1)
Same canonical name across companies — already grouped by `base_name_index`. Trivial.

### 4.2 Variant Detection (Level 2)

**Goal**: Find ingredients that are the same functional ingredient in different forms (e.g., `soy-lecithin` ↔ `sunflower-lecithin`).

**Algorithm**:
1. Tokenise each ingredient name: split on hyphens/spaces → set of word tokens
2. Remove modifier tokens (defined in `MODIFIER_TOKENS` constant — words like "organic", "natural", "pure" that don't change functional identity)
3. Build reverse index: significant tokens (length ≥ 4) → list of ingredient names
4. Cluster greedily: for each unclustered ingredient, pull in all others where:

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|} \geq 0.4 \quad \text{AND} \quad |A \cap B| \geq 1 \quad \text{AND} \quad \text{sameCategory}(A, B)$$

where $J$ is the **Jaccard similarity** between token sets.

**Confidence computation** (data-driven, not flat):

$$\text{avgSim} = \frac{1}{\binom{n}{2}} \sum_{i < j} J(\text{tokens}_i, \text{tokens}_j)$$

$$\text{supOverlap} = \frac{|\text{sharedSuppliers}|}{|\text{allSuppliers}|}$$

$$\text{allergenPenalty} = \begin{cases} 0.15 & \text{if any allergen difference exists} \\ 0.0 & \text{otherwise} \end{cases}$$

$$\text{confidence}_{\text{variant}} = \text{clamp}\left(0.6 \cdot \text{avgSim} + 0.25 + 0.15 \cdot \text{supOverlap} - \text{allergenPenalty}\right)$$

**Rationale**: Higher name similarity → more likely same ingredient. Shared suppliers further confirm (a supplier selling both variants implies they're interchangeable). Allergen differences reduce trust because swapping could create labelling risk.

### 4.3 Functional Grouping (Level 3)

**Goal**: Group different ingredients within the same functional category that serve the same formulation role (e.g., different sweeteners).

**Algorithm**:
1. Group all ingredients by functional category  
2. Within each category, sub-cluster by **longest significant root token** (after removing modifiers)
3. Merge singletons into the most similar existing sub-cluster if $J \geq 0.25$

**Confidence computation**:

$$\text{supOverlap}_f = \frac{|\text{sharedSuppliers}|}{|\text{allSuppliers}|}$$

$$\text{allergenPenalty}_f = 0.12 \times |\text{distinctAllergens}|$$

$$\text{confidence}_{\text{functional}} = \text{clamp}\left(0.30 + 0.05 \cdot \min(|\text{members}|, 4) + 0.15 \cdot \text{supOverlap}_f - \text{allergenPenalty}_f\right)$$

**Rationale**: Functional substitution is inherently less certain than variant substitution (different molecules vs. different forms of the same molecule). More members in the group → more market evidence of interchangeability. More allergen types → higher regulatory risk.

---

## 5. Consolidation Analysis

**Entry condition**: ingredient used by ≥ 2 companies AND currently served by ≥ 2 suppliers.

For each qualifying ingredient:

1. **Build company→supplier map** from product-supplier links
2. **Identify best supplier**: supplier serving the most companies already

$$\text{bestSupplier} = \arg\max_{s} \sum_{c \in \text{companies}} \mathbb{1}[s \in \text{suppliers}(c)]$$

3. **Compute cost analysis** from procurement data (§5.1)
4. **Compute 5-dimension prioritisation framework** (§7.1)
5. **Build evidence trail** (§10)

### 5.1 Cost Analysis

$$\text{estimatedConsolidatedSpend} = \text{bestSupplierAvgPrice} \times \sum_s \frac{s.\text{totalSpend}}{s.\text{avgPrice}}$$

$$\text{savings} = \text{currentTotalSpend} - \text{estimatedConsolidatedSpend}$$

$$\text{savingsPct} = \frac{\text{savings}}{\text{currentTotalSpend}} \times 100\%$$

All values derived from actual procurement history — no assumed volumes.

---

## 6. Risk Assessment

Five risk types, each with **data-driven detection logic**:

### 6.1 Single-Source Risk
**Trigger**: `supplierCount == 1` AND `companyCount ≥ 2`  
**Severity**: always `high` (structural risk — one failure point for multiple companies)  
**Rationale**: If the sole supplier fails, every company using that ingredient is affected simultaneously.

### 6.2 Supplier Concentration Risk
**Trigger**: a single supplier is the sole source for ≥ 3 ingredients  
**Severity**:

$$\text{severity} = \begin{cases} \text{high} & \text{if soleIngredientCount} \geq 10 \\ \text{medium} & \text{otherwise} \end{cases}$$

**Rationale**: Thresholds are relative to portfolio — 3 ingredients = minimum meaningful concentration, 10 = dominant dependency.

### 6.3 Critical Ingredient Risk
**Trigger**: `companyCount ≥ 5` AND `supplierCount ≤ 2` AND `companyCount / supplierCount ≥ 4`  
**Severity**: `medium`  
**Rationale**: High demand-to-supply ratio with thin supplier base. The ratio threshold (4:1) identifies ingredients where demand significantly outstrips supply-side resilience.

### 6.4 Supplier Quality Risk
**Trigger**: `RiskTier == 'high'` OR `QualityScore < 80` (both from `Supplier_Rating` table)  
**Severity**:

$$\text{severity} = \begin{cases} \text{high} & \text{if QualityScore} < 70 \\ \text{medium} & \text{otherwise} \end{cases}$$

**Rationale**: Quality and risk-tier scores come directly from the database. The 80/70 splits separate "concerning" from "critical" quality levels on the 0–100 scale.

### 6.5 Price Volatility Risk
**Trigger**: `PriceVolatility ≥ 0.25` (from `Price_Benchmark` table) AND `companyCount ≥ 3`  
**Severity**: `medium`  
**Rationale**: Volatility is a statistical measure from the benchmark data. 25% volatility = significant cost uncertainty. Must affect ≥ 3 companies to be network-relevant.

---

## 7. Recommendation Generation

Every recommendation type uses the same structural pattern:

1. **Compute 5 dimensions** — each a `[0, 1]` float derived from data
2. **Weighted sum** → `finalScore` ∈ `[0, 1]`
3. **Grade mapping** using shared thresholds
4. **Priority** derived from grade + secondary data heuristics
5. **Confidence** = the evidence-strength dimension
6. **Evidence trail** listing every data point that influenced the score

### 7.1 Consolidation Framework

$$S_{\text{consol}} = 0.35 \cdot D_1 + 0.25 \cdot D_2 + 0.20 \cdot D_3 + 0.10 \cdot D_4 + 0.10 \cdot D_5$$

| Dimension | Symbol | Formula | Data source |
|-----------|--------|---------|-------------|
| **Consolidation benefit** | $D_1$ | $0.6 \cdot \frac{\text{covered}}{\text{totalCompanies}} + 0.4 \cdot \text{clamp}\left(\frac{\text{currentSuppliers} - 1}{4}\right)$ | Company-supplier map |
| **Evidence confidence** | $D_2$ | $0.4_{\text{base}} + 0.3 \cdot \mathbb{1}[\text{costAnalysis}] + 0.2 \cdot \mathbb{1}[\text{ratingExists}] + 0.1 \cdot \mathbb{1}[\text{noSingleSource}]$ | Procurement history, supplier ratings |
| **Compliance fit** | $D_3$ | $\text{clamp}\left(\frac{Q + C}{200}\right)$, capped at 0.35 if $Q < 70$ or $C < 70$ | Supplier_Rating (QualityScore, ComplianceScore) |
| **Supplier diversification** | $D_4$ | Piecewise: $0$ if 1 supplier, $0.25$ if 2, $0.55$ if 3, $\text{clamp}\left(\frac{n-1}{4} + 0.25\right)$ if $n \geq 4$ | Global supplier count |
| **Switching feasibility** | $D_5$ | $0.4_{\text{base}} + 0.3 \cdot \frac{\text{Reliability}}{100} + 0.15 \cdot \left(1 - \frac{\min(\text{Lead}, 60)}{60}\right) + 0.15 \cdot \text{coverageRatio}$ | Supplier_Rating (ReliabilityScore, LeadTimeDays) |

**Why piecewise for $D_4$?** The relationship between supplier count and resilience is non-linear: going from 1→2 suppliers is a massive risk reduction, while going from 4→5 is marginal. The piecewise function models this diminishing-returns curve without a lookup table.

**Anti-monopoly veto** (see §8): If $D_4 < 0.30$ and the weighted score would yield `safe_to_consolidate`, the grade is **downgraded** to `review_required`.

### 7.2 Risk Mitigation Framework

$$S_{\text{risk}} = 0.30 \cdot D_1 + 0.25 \cdot D_2 + 0.20 \cdot D_3 + 0.15 \cdot D_4 + 0.10 \cdot D_5$$

| Dimension | Symbol | Formula | Data source |
|-----------|--------|---------|-------------|
| **Impact severity** | $D_1$ | Per risk type — see below | Varies |
| **Evidence strength** | $D_2$ | Per risk type — see below | Varies |
| **Mitigation feasibility** | $D_3$ | Per risk type — see below | Substitution groups, product counts |
| **Exposure breadth** | $D_4$ | $\text{clamp}\left(\frac{\text{companiesAffected}}{\text{totalCompanies}}\right)$ | Company counts |
| **Urgency** | $D_5$ | $0.85$ if high severity, $0.55$ if medium, $0.30$ if low | Severity (data-derived in §6) |

**Impact severity by risk type**:

| Risk type | Formula | Rationale |
|-----------|---------|-----------|
| single_source | $\text{clamp}\left(\frac{\text{companiesAffected}}{\text{totalCompanies}} \times 1.5\right)$ | Fraction of network at risk, amplified (1.5×) because single-source = binary failure |
| supplier_concentration | $\text{clamp}\left(\frac{\text{soleIngredients}}{\text{totalIngredients}} \times 3.0\right)$ | Fraction of portfolio dependent, amplified (3×) because concentration compounds |
| critical_ingredient | $\text{clamp}\left(\frac{\text{demand/supply ratio}}{10}\right)$ | Higher ratio = more imbalanced supply chain |
| supplier_quality | $\text{clamp}\left(1 - \frac{\text{QualityScore}}{100}\right)$ | Quality score directly from DB, inverted (lower quality = higher impact) |
| price_volatility | $\text{clamp}\left(\frac{\text{volatility}}{50}\right)$ | Volatility from Price_Benchmark, normalised to [0, 1] |

**Evidence strength by risk type**:

| Risk type | Formula | Rationale |
|-----------|---------|-----------|
| supplier_quality | $0.90$ (fixed) | Quality scores are direct measured data — highest possible evidence quality |
| price_volatility | $\text{clamp}(0.40 + 0.06 \cdot \min(\text{orderCount}, 10))$ | More historical orders = more statistically reliable volatility measure |
| single_source / critical | $0.55_{\text{base}} + 0.25 \cdot \mathbb{1}[\text{pricingExists}] + 0.15 \cdot \mathbb{1}[\text{ratingExists}]$ | Structural risk is observable from network topology; pricing + ratings add depth |

**Mitigation feasibility by risk type**:

| Risk type | Formula | Rationale |
|-----------|---------|-----------|
| single_source | $\text{clamp}(0.25 + 0.15 \cdot \min(|\text{altSuppliers}|, 4))$ | Alternative suppliers found via substitution groups — more alts = easier to mitigate |
| supplier_quality | $0.50$ if ≤ 5 products affected, else $0.30$ | Fewer products = easier to requalify supplier or switch |
| price_volatility | $0.55$ | Hedging/contracts are generally available but not always negotiable |

### 7.3 Substitution Framework

$$S_{\text{sub}} = 0.30 \cdot D_1 + 0.20 \cdot D_2 + 0.20 \cdot D_3 + 0.15 \cdot D_4 + 0.15 \cdot D_5$$

| Dimension | Symbol | Formula | Data source |
|-----------|--------|---------|-------------|
| **Similarity score** | $D_1$ | Variant: $\text{clamp}(\overline{J} + 0.10 \cdot \mathbb{1}[\text{sameCategory}])$. Functional: $\text{clamp}(0.30 + 0.04 \cdot \min(n, 5))$ | Jaccard similarity, category match |
| **Evidence strength** | $D_2$ | $0.35_{\text{base}} + 0.25 \cdot \frac{\text{membersWithPricing}}{n} + 0.20 \cdot \frac{\text{ratedSuppliers}}{\text{totalSuppliers}} + 0.10 \cdot \mathbb{1}[\text{sups} \geq 3] + 0.10 \cdot \mathbb{1}[n \geq 3]$ | Pricing data, supplier ratings |
| **Compliance compatibility** | $D_3$ | $\text{clamp}(0.65 + 0.35 \cdot \text{flagAgreement} - 0.10 \cdot |\text{allergens}|)$ | Quality flags (organic, vegan, etc.), allergen lists |
| **Network benefit** | $D_4$ | $0.25 \cdot \frac{\text{groupCompanies}}{\text{totalCompanies}} + 0.35 \cdot \text{clamp}\left(\frac{\text{groupSuppliers}}{5}\right) + 0.40 \cdot \frac{\text{bestMemberCompanies}}{\text{groupCompanies}}$ | Network topology |
| **Switching feasibility** | $D_5$ | $\text{clamp}(0.30 + 0.50 \cdot \text{bestShare} + 0.15 \cdot \mathbb{1}[\text{variant}])$ | Adoption data, substitution type |

**Flag agreement** (compliance compatibility):

$$\text{flagAgreement} = \frac{|\text{commonFlags}|}{|\text{allFlags}|}$$

where `commonFlags` = quality flags shared by ALL members, `allFlags` = union of all members' flags. If member A is organic and member B is not, switching one for the other may breach organic certification — this is captured mathematically.

**Why variant bonus (+0.15) in switching feasibility?** Variants are the same molecule in different forms. Switching from `organic-stevia` to `stevia` is formulation-safe; switching from `stevia` to `sucralose` requires reformulation and taste testing. The bonus reflects this lower switching barrier.

### 7.4 Cost Optimisation Framework

**Entry gate** (all must be true):
- ≥ 2 suppliers with pricing data
- Price spread ≥ 15%:  $\frac{P_{\max} - P_{\min}}{P_{\max}} \times 100 \geq 15$
- Cheapest supplier Quality ≥ 75/100
- Cheapest supplier Compliance ≥ 75/100

$$S_{\text{cost}} = 0.30 \cdot D_1 + 0.20 \cdot D_2 + 0.25 \cdot D_3 + 0.15 \cdot D_4 + 0.10 \cdot D_5$$

| Dimension | Symbol | Formula | Data source |
|-----------|--------|---------|-------------|
| **Savings magnitude** | $D_1$ | $\text{clamp}\left(\frac{\text{spreadPct}}{50}\right)$ | Price spread computed from procurement history |
| **Evidence strength** | $D_2$ | $0.25_{\text{base}} + 0.25 \cdot \text{clamp}\left(\frac{\text{orderCount}}{20}\right) + 0.15 \cdot \mathbb{1}[\text{qualityScore}] + 0.15 \cdot \mathbb{1}[\text{benchmark}] + 0.10 \cdot \text{clamp}\left(\frac{|\text{suppliers}|}{4}\right) + 0.10 \cdot \text{clamp}\left(\frac{\text{cheapestOrders}}{5}\right)$ | Procurement history, benchmarks |
| **Quality assurance** | $D_3$ | $\text{clamp}\left(\frac{Q/100 + C/100}{2}\right)$ | Supplier_Rating (QualityScore, ComplianceScore) |
| **Supplier reliability** | $D_4$ | $0.5 \cdot \frac{\text{ReliabilityScore}}{100} + 0.5 \cdot \frac{\text{onTimeRate}}{100}$ | Supplier_Rating + procurement on-time data |
| **Implementation ease** | $D_5$ | $0.40_{\text{base}} + 0.25 \cdot \mathbb{1}[\text{cheapestOrders} \geq 3] + 0.15 \cdot \mathbb{1}[\text{benchmark}] + 0.10 \cdot \text{clamp}\left(\frac{\text{supplierCount}}{4}\right) + 0.10 \cdot \text{clamp}\left(\frac{\text{companyCount}}{5}\right)$ | Procurement history, network data |

**Estimated savings**:

$$\text{estSavings} = (P_{\max} - P_{\min}) \times \frac{\text{totalSpend}}{\text{avgUnitPrice}} \times 0.5$$

The 0.5 factor is a **conservative volume assumption** — only 50% of volume is assumed shiftable. This is explicitly disclosed in the evidence trail as an assumption.

---

## 8. Grade Mapping & Veto Logic

All four frameworks share the same grade thresholds (defined once as named constants):

| Constant | Value | Meaning |
|----------|-------|---------|
| `GRADE_SAFE_THRESHOLD` | 0.70 | Score ≥ this → `safe_to_consolidate` / `recommended` |
| `GRADE_REJECT_THRESHOLD` | 0.30 | Score ≤ this → `not_recommended` |
| Between | — | `review_required` |

**Grade labels by framework type**:

| Framework | High grade | Mid grade | Low grade |
|-----------|-----------|-----------|-----------|
| Consolidation | `safe_to_consolidate` | `review_required` | `not_recommended` |
| Risk / Substitution / Cost | `recommended` | `review_required` | `not_recommended` |

### Anti-Monopoly Veto (Consolidation only)

Even when the weighted score crosses the safe threshold, if the **supplier diversification** dimension falls below the `DIVERSIFICATION_FLOOR` (0.30), the grade is forcibly downgraded:

$$\text{if } S \geq 0.70 \text{ AND } D_4 < 0.30 \implies \text{grade} \leftarrow \texttt{review\_required}$$

This prevents Agnes from recommending full consolidation onto a supplier that would become a monopoly. The evidence trail explicitly flags this veto: *"Concentration-risk veto fired"*.

### Priority derivation from grade

Priority is never a flat label — it combines the framework grade with a secondary data signal:

| Framework | Grade → Priority mapping |
|-----------|-----------------------|
| Consolidation | `safe_to_consolidate` + ≥ 3 companies → `high`; `review_required` + ≥ 5 companies → `medium`; `not_recommended` → `low` |
| Risk | `recommended` → `high`; `review_required` → `medium`; `not_recommended` → `low` |
| Substitution | `recommended` + ≥ 4 companies → `high`; `recommended` + < 4 → `medium`; `review_required` → `medium`; else → `low` |
| Cost | `recommended` + spread ≥ 30% → `high`; `recommended` → `medium`; `review_required` → `medium`; else → `low` |

---

## 9. Confidence Model

**Principle**: Confidence = the **evidence_strength** (or **evidence_confidence**) dimension of the applicable framework. It is never a flat constant.

This means confidence directly tells you *how much data backs this recommendation*:

| Factor that increases confidence | How much | Why |
|----------------------------------|----------|-----|
| Procurement history exists | +0.25 to +0.30 | Historical orders confirm the price/volume claims |
| Supplier ratings exist | +0.15 to +0.20 | Quality/compliance/reliability data validates supplier choice |
| More historical orders | Up to +0.25 (saturates at ~20 orders) | Statistical significance — more data points = more reliable averages |
| No single-source gaps | +0.10 | Complete supplier mapping = no hidden dependencies |
| Market benchmark exists | +0.15 | External price reference validates savings claims |
| Multiple suppliers rated | Proportional to rated/total ratio | Broader coverage of quality data |

**Example**: A consolidation recommendation where:
- Procurement history exists (+0.3)
- Supplier rating exists (+0.2)
- No single-source gaps (+0.1)
- Base existence (+0.4)

→ Evidence confidence = 1.0 (maximum), meaning the recommendation is fully backed by data.

**Example**: A substitution recommendation where:
- 2 of 3 members have pricing data (+0.25 × 2/3 = +0.167)
- 3 of 5 suppliers rated (+0.20 × 3/5 = +0.12)
- ≥3 suppliers in group (+0.10)
- ≥3 members (+0.10)
- Base (+0.35)

→ Evidence strength = 0.837

---

## 10. Evidence Trail Architecture

Every recommendation includes an `evidence[]` array of human-readable strings. Each string cites specific data:

### Consolidation Evidence
1. Network usage: *"{ingredient} is used by {N} companies, creating consolidation potential"*
2. Current coverage: *"{supplier} already serves {M}/{N} companies"*
3. Framework breakdown: *"Framework score {S}: leverage {D1}, evidence {D2}, compliance {D3}, diversification {D4}, switching {D5}"*
4. Veto flag (conditional): *"⚠️ Concentration-risk veto: network has ≤2 suppliers..."*
5. Single-source warning (conditional): *"⚠️ {K} SKU(s) have only one linked supplier"*
6. Allergen flag (conditional): *"Allergen considerations: {list}"*
7. Historical spend: *"Historical spend: ${X} across {Y} orders (avg ${Z}/kg)"*
8. Price vs. benchmark: *"Current avg price is {P}% above/below market benchmark"*

### Risk Mitigation Evidence
1. Risk description (from §6)
2. Supplier/scope details
3. Alternative suppliers (if found via substitution groups) or explicit "none found" disclosure
4. Framework breakdown with all 5 dimensions

### Substitution Evidence
1. Group type and members
2. Category
3. Best member's adoption data
4. Supplier pool size
5. Variant similarity note (for variant groups)
6. Allergen considerations (conditional)
7. Framework breakdown with all 5 dimensions

### Cost Optimisation Evidence
1. Cheapest supplier: price, quality, compliance, on-time rate, **order count**
2. Most expensive supplier: price, order count
3. Price spread + estimated savings with explicit 50% volume assumption
4. Market benchmark + volatility
5. Total historical spend + order count
6. Framework breakdown with all 5 dimensions

---

## 11. Named Constants Reference

Every tunable value is defined once at the top of `agnes_engine.py`:

### Framework Weights

| Constant | Dimensions | Sum |
|----------|-----------|-----|
| `PRIORITIZATION_WEIGHTS` | consolidation_benefit: 0.35, evidence_confidence: 0.25, compliance_fit: 0.20, supplier_diversification: 0.10, switching_feasibility: 0.10 | 1.00 |
| `RISK_WEIGHTS` | impact_severity: 0.30, evidence_strength: 0.25, mitigation_feasibility: 0.20, exposure_breadth: 0.15, urgency: 0.10 | 1.00 |
| `SUBSTITUTION_WEIGHTS` | similarity_score: 0.30, evidence_strength: 0.20, compliance_compatibility: 0.20, network_benefit: 0.15, switching_feasibility: 0.15 | 1.00 |
| `COST_WEIGHTS` | savings_magnitude: 0.30, evidence_strength: 0.20, quality_assurance: 0.25, supplier_reliability: 0.15, implementation_ease: 0.10 | 1.00 |

### Thresholds

| Constant | Value | Used by | Rationale |
|----------|-------|---------|-----------|
| `GRADE_SAFE_THRESHOLD` | 0.70 | All frameworks | Top 30% of score range = strong enough to act |
| `GRADE_REJECT_THRESHOLD` | 0.30 | All frameworks | Bottom 30% = insufficient basis for action |
| `DIVERSIFICATION_FLOOR` | 0.30 | Consolidation veto | Below this, the network lacks adequate backup suppliers |

### Substitution Detection

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Jaccard threshold (variant) | 0.40 | Empirically tuned — below this, names share too few tokens to be confident they're variants |
| Minimum token length | 4 characters | Filters out articles/prepositions ("non", "from") that add noise |
| Subcluster merge threshold | 0.25 | Lower than variant (0.40) because functional groups are broader |

### Risk Detection

| Parameter | Value | Data derivation |
|-----------|-------|-----------------|
| Single-source: min companies | 2 | Network risk only exists if ≥2 companies depend on one supplier |
| Supplier concentration: min sole ingredients | 3 | Below 3, concentration risk is manageable |
| Concentration severity split | 10 | 10+ sole ingredients = systemic dependency |
| Critical ingredient: min companies | 5, max suppliers: 2, min ratio: 4 | These define a structurally imbalanced ingredient — many buyers, few sources |
| Quality threshold | 80 (flag), 70 (high severity) | On a 0–100 scale: 80 = concerning, 70 = critical |
| Price volatility threshold | 0.25 (25%) | Statistical measure from benchmark data — 25% = significant uncertainty |
| Price volatility: min companies | 3 | Small-scope volatility is lower priority |

### Cost Optimisation

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Minimum price spread | 15% | Below this, savings don't justify switching costs |
| Quality floor | 75/100 | Won't recommend switching to a supplier below this quality |
| Compliance floor | 75/100 | Won't recommend switching below this compliance level |
| Volume shift assumption | 50% | Conservative — disclosed in evidence trail |

### Knowledge Base

| Constant | Size | Purpose |
|----------|------|---------|
| `FUNCTIONAL_CATEGORIES` | 17 categories | Keyword-based ingredient-to-category mapping |
| `ALLERGEN_MARKERS` | 7 allergen types | Name-based allergen detection |
| `QUALITY_FLAGS` | 6 flag types | Certification/attribute detection |
| `MODIFIER_TOKENS` | 18 tokens | Stripped during tokenisation to find functional root |

---

## 12. Design Principles

### No hallucinated numbers
Every value in a recommendation traces back to database records. Where data is absent, evidence_strength drops and confidence decreases accordingly. Agnes never invents data — it reports what it knows and how confident it is.

### Deterministic outputs
Given the same database, Agnes produces identical results every run. There is no randomness, no LLM inference in the scoring layer, no stochastic sampling. The engine is pure computation on structured data.

### Transparent reasoning
Every recommendation includes:
- The exact weighted score (to 4 decimal places)
- The value of each individual dimension
- The weight assigned to each dimension
- Human-readable evidence citing specific data points
- Caveats listing assumptions and required follow-up

### Separation of signal from judgement
The **dimensions** are the signal (data-derived). The **weights** are the judgement (how much each signal matters). Weights are explicit named constants that can be tuned without touching any calculation logic.

### Anti-monopoly by design
The consolidation framework structurally prevents recommending supply-chain fragility. The diversification dimension + floor veto ensure that "save money" never overrides "stay resilient".

### Evidence-proportional confidence
Confidence isn't a gut-feeling number. It's the evidence-strength dimension of the applicable framework — mathematically determined by how much supporting data exists. An analyst reading the evidence trail can verify every claim.

### Conservative assumptions
Where estimations are necessary (e.g., 50% volume shift in cost optimisation), the assumption is conservative and **explicitly disclosed** in the evidence trail. No hidden optimistic projections.
