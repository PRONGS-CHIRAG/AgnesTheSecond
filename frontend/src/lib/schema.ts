import { z } from "zod";

export const ArtifactStatus = z.object({
  name: z.string(),
  present: z.boolean(),
  path: z.string(),
  size_bytes: z.number().int().nullable().optional(),
  mtime_ns: z.number().int().nullable().optional(),
  generated_at: z.string().datetime().nullable().optional(),
});
export type ArtifactStatus = z.infer<typeof ArtifactStatus>;

export const Summary = z.object({
  artifacts: z.array(ArtifactStatus),
  canonical: z.record(z.any()).nullable().optional(),
  candidates: z.record(z.any()).nullable().optional(),
  evidence: z.record(z.any()).nullable().optional(),
  assessments: z.record(z.any()).nullable().optional(),
  recommendations: z.record(z.any()).nullable().optional(),
});
export type Summary = z.infer<typeof Summary>;

export const CanonicalMaterial = z.object({
  raw_product_id: z.number().int(),
  sku: z.string(),
  company_id: z.number().int(),
  normalized_name: z.string(),
  canonical_key: z.string(),
  ingredient_family: z.string(),
  functional_role: z.string(),
  confidence: z.number(),
  missing_info: z.array(z.string()),
  parse_ok: z.boolean(),
  taxonomy_version: z.string(),
});
export type CanonicalMaterial = z.infer<typeof CanonicalMaterial>;

export const RegistryPage = z.object({
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
  q: z.string().nullable(),
  family: z.string().nullable(),
  role: z.string().nullable(),
  families: z.array(z.string()),
  roles: z.array(z.string()),
  items: z.array(CanonicalMaterial),
});
export type RegistryPage = z.infer<typeof RegistryPage>;

export const CandidateFeatures = z
  .object({
    family_match: z.number(),
    role_match: z.number(),
    lexical_sim: z.number(),
    embed_sim: z.number(),
    supplier_overlap: z.number().optional(),
    co_company_overlap: z.number().optional(),
    missing_signals: z.array(z.string()).optional(),
  })
  .passthrough();

export const SubstituteCandidate = z
  .object({
    source_key: z.string(),
    candidate_key: z.string(),
    family: z.string().nullable(),
    roles: z.array(z.string()),
    score: z.number(),
    features: CandidateFeatures,
    embedding_model: z.string().nullable().optional(),
    taxonomy_version: z.string().optional(),
    graph_schema_version: z.string().optional(),
    schema_version: z.string().optional(),
  })
  .passthrough();
export type SubstituteCandidate = z.infer<typeof SubstituteCandidate>;

export const SubstituteCandidateReport = z
  .object({
    schema_version: z.string().optional(),
    generated_at: z.string(),
    embedding_model: z.string().nullable().optional(),
    weights: z.record(z.number()).optional(),
    min_score: z.number(),
    top_k: z.number().int(),
    cross_family: z.boolean().optional(),
    n_targets: z.number().int(),
    n_with_candidates: z.number().int(),
    n_without_candidates: z.number().int(),
    avg_top_score: z.number().nullable(),
    duration_ms: z.number().int().optional(),
    partial: z.boolean(),
    targets: z.array(z.record(z.any())).optional(),
    candidates: z.array(SubstituteCandidate),
  })
  .passthrough();
export type SubstituteCandidateReport = z.infer<typeof SubstituteCandidateReport>;

export const CitationRef = z.object({
  url: z.string(),
  title: z.string().nullable().optional(),
  domain: z.string().nullable().optional(),
  retrieved_at: z.string().optional(),
});
export type CitationRef = z.infer<typeof CitationRef>;

export const EvidenceClaim = z.object({
  key: z.string(),
  value: z.string(),
  polarity: z.enum(["supports", "contradicts", "mixed", "unknown"]),
  confidence: z.number(),
  citations: z.array(CitationRef),
  grounding_strength: z.enum(["grounded", "parametric"]),
});
export type EvidenceClaim = z.infer<typeof EvidenceClaim>;

export const SubstituteEvidence = z
  .object({
    source_key: z.string(),
    candidate_key: z.string(),
    claims: z.array(EvidenceClaim),
    n_citations: z.number().int(),
    any_contradictions: z.boolean(),
    retrieved_at: z.string(),
    llm_model: z.string(),
    schema_version: z.string().optional(),
  })
  .passthrough();
export type SubstituteEvidence = z.infer<typeof SubstituteEvidence>;

export const EvidenceReport = z
  .object({
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string(),
    n_sources: z.number().int(),
    n_pairs: z.number().int(),
    n_cache_hits: z.number().int(),
    n_api_calls: z.number().int(),
    n_failures: z.number().int(),
    duration_ms: z.number().int(),
    partial: z.boolean(),
    items: z.array(SubstituteEvidence),
  })
  .passthrough();
export type EvidenceReport = z.infer<typeof EvidenceReport>;

export const SubstituteAssessment = z
  .object({
    company_id: z.number().int(),
    company_name: z.string().nullable().optional(),
    finished_product_id: z.number().int(),
    finished_product_sku: z.string().nullable().optional(),
    source_key: z.string(),
    candidate_key: z.string(),
    source_display_name: z.string(),
    candidate_display_name: z.string(),
    recommendation_class: z.enum([
      "recommend",
      "recommend_with_caveats",
      "do_not_recommend",
      "insufficient_evidence",
    ]),
    acceptability: z.number(),
    missing_information: z.array(z.string()),
    contradictions: z.array(z.string()),
    caveats: z.array(z.string()),
    rationale: z.string(),
    decision_path: z.enum(["rules", "llm"]),
    citations_used: z.array(CitationRef),
    substitute_score: z.number().nullable().optional(),
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string().nullable().optional(),
  })
  .passthrough();
export type SubstituteAssessment = z.infer<typeof SubstituteAssessment>;

export const AssessmentReport = z
  .object({
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string().nullable().optional(),
    weights: z.record(z.number()),
    thresholds: z.record(z.number()),
    n_tuples: z.number().int(),
    n_rules_decisions: z.number().int(),
    n_llm_decisions: z.number().int(),
    n_cache_hits: z.number().int(),
    n_api_calls: z.number().int(),
    n_failures: z.number().int(),
    n_without_evidence: z.number().int(),
    counts_by_class: z.record(z.number()),
    duration_ms: z.number().int(),
    partial: z.boolean(),
    items: z.array(SubstituteAssessment),
  })
  .passthrough();
export type AssessmentReport = z.infer<typeof AssessmentReport>;

export const Grade = z.enum([
  "safe_to_consolidate",
  "likely_safe_review_required",
  "potential_substitute_insufficient_evidence",
  "not_recommended",
]);
export type Grade = z.infer<typeof Grade>;

export const SourcingSignals = z.object({
  source_supplier_count: z.number().int(),
  candidate_supplier_count: z.number().int(),
  shared_supplier_ids: z.array(z.number().int()),
  company_supplier_overlap: z.number(),
  concentration_relief: z.number(),
  missing_signals: z.array(z.string()),
});

export const SourcingRecommendation = z
  .object({
    company_id: z.number().int(),
    company_name: z.string().nullable().optional(),
    finished_product_id: z.number().int(),
    finished_product_sku: z.string().nullable().optional(),
    source_key: z.string(),
    candidate_key: z.string(),
    source_display_name: z.string(),
    candidate_display_name: z.string(),
    recommendation_grade: Grade,
    final_score: z.number(),
    acceptability: z.number(),
    substitute_score: z.number().nullable().optional(),
    sourcing_benefit: z.number(),
    signals: SourcingSignals,
    current_suppliers: z.array(z.string()),
    recommended_suppliers: z.array(z.string()),
    caveats: z.array(z.string()),
    risk_notes: z.array(z.string()),
    review_required: z.boolean(),
    tradeoff_summary: z.string(),
    citations: z.array(CitationRef),
    decision_path: z.enum(["rules", "llm"]),
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string().nullable().optional(),
  })
  .passthrough();
export type SourcingRecommendation = z.infer<typeof SourcingRecommendation>;

export const ConsolidationOpportunity = z
  .object({
    source_key: z.string(),
    source_display_name: z.string(),
    best_candidate_key: z.string(),
    best_candidate_display_name: z.string(),
    n_products_covered: z.number().int(),
    n_companies_covered: z.number().int(),
    aggregate_final_score: z.number(),
    aggregate_sourcing_benefit: z.number(),
    recommendation_grade: Grade,
    unique_current_suppliers: z.array(z.string()),
    unique_recommended_suppliers: z.array(z.string()),
    review_required: z.boolean(),
    tradeoff_summary: z.string(),
    risk_notes: z.array(z.string()),
    top_row_keys: z.array(z.string()),
    decision_path: z.enum(["rules", "llm"]),
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string().nullable().optional(),
  })
  .passthrough();
export type ConsolidationOpportunity = z.infer<typeof ConsolidationOpportunity>;

export const RecommendationReport = z
  .object({
    schema_version: z.string().optional(),
    generated_at: z.string(),
    llm_model: z.string().nullable().optional(),
    weights: z.record(z.number()),
    thresholds: z.record(z.number()),
    n_tuples: z.number().int(),
    n_opportunities: z.number().int(),
    n_cache_hits: z.number().int(),
    n_api_calls: z.number().int(),
    n_failures: z.number().int(),
    counts_by_grade: z.record(z.number()),
    duration_ms: z.number().int(),
    partial: z.boolean(),
    items: z.array(SourcingRecommendation),
    opportunities: z.array(ConsolidationOpportunity),
  })
  .passthrough();
export type RecommendationReport = z.infer<typeof RecommendationReport>;

export const OpportunityDetail = z.object({
  opportunity: ConsolidationOpportunity,
  rows: z.array(SourcingRecommendation),
  evidence: z.array(SubstituteEvidence),
  assessments: z.array(SubstituteAssessment),
  candidates: z.array(SubstituteCandidate),
});
export type OpportunityDetail = z.infer<typeof OpportunityDetail>;

export const ConfidenceBucket = z.object({
  bucket: z.string(),
  lo: z.number(),
  hi: z.number(),
  n: z.number().int(),
});
export type ConfidenceBucket = z.infer<typeof ConfidenceBucket>;

export const RegistryBundle = z.object({
  total: z.number().int(),
  families: z.array(z.string()),
  roles: z.array(z.string()),
  family_counts: z.record(z.number().int()),
  role_counts: z.record(z.number().int()),
  confidence_histogram: z.array(ConfidenceBucket),
  taxonomy_version: z.string().nullable().optional(),
  generated_at: z.string().nullable().optional(),
  coverage: z.record(z.number().int()).nullable().optional(),
  unique_canonical_keys: z.number().int().nullable().optional(),
  items: z.array(CanonicalMaterial),
});
export type RegistryBundle = z.infer<typeof RegistryBundle>;

export const CompanyNode = z.object({
  id: z.number().int(),
  name: z.string(),
  finished_good_count: z.number().int(),
  raw_material_count: z.number().int(),
  supplier_count: z.number().int(),
});
export type CompanyNode = z.infer<typeof CompanyNode>;

export const SupplierNode = z.object({
  id: z.number().int(),
  name: z.string(),
  product_count: z.number().int(),
  canonical_key_count: z.number().int(),
  company_count: z.number().int(),
  sole_source_count: z.number().int(),
  top_families: z.array(z.string()),
});
export type SupplierNode = z.infer<typeof SupplierNode>;

export const ProductType = z.enum(["finished-good", "raw-material"]);
export type ProductType = z.infer<typeof ProductType>;

export const ProductNode = z.object({
  id: z.number().int(),
  sku: z.string(),
  company_id: z.number().int(),
  company_name: z.string(),
  type: ProductType,
  normalized_name: z.string().nullable().optional(),
  canonical_key: z.string().nullable().optional(),
  ingredient_family: z.string().nullable().optional(),
  functional_role: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  supplier_count: z.number().int().nullable().optional(),
  bom_count: z.number().int().nullable().optional(),
});
export type ProductNode = z.infer<typeof ProductNode>;

export const SupplierProductEdge = z.object({
  supplier_id: z.number().int(),
  supplier_name: z.string(),
  product_id: z.number().int(),
  product_sku: z.string(),
  company_id: z.number().int(),
  company_name: z.string(),
  canonical_key: z.string().nullable().optional(),
  ingredient_family: z.string().nullable().optional(),
  functional_role: z.string().nullable().optional(),
});
export type SupplierProductEdge = z.infer<typeof SupplierProductEdge>;

export const CompanySupplierEdge = z.object({
  company_id: z.number().int(),
  company_name: z.string(),
  supplier_id: z.number().int(),
  supplier_name: z.string(),
  shared_raw_count: z.number().int(),
  canonical_keys: z.array(z.string()),
});
export type CompanySupplierEdge = z.infer<typeof CompanySupplierEdge>;

export const ProductRawEdge = z.object({
  finished_product_id: z.number().int(),
  finished_sku: z.string(),
  company_id: z.number().int(),
  company_name: z.string(),
  raw_product_id: z.number().int(),
  raw_sku: z.string(),
  canonical_key: z.string().nullable().optional(),
  ingredient_family: z.string().nullable().optional(),
});
export type ProductRawEdge = z.infer<typeof ProductRawEdge>;

export const SupplierRawEdge = z.object({
  supplier_id: z.number().int(),
  supplier_name: z.string(),
  raw_product_id: z.number().int(),
  raw_sku: z.string(),
  canonical_key: z.string(),
  ingredient_family: z.string().nullable().optional(),
  functional_role: z.string().nullable().optional(),
});
export type SupplierRawEdge = z.infer<typeof SupplierRawEdge>;

export const SupplyNetworkAggregates = z.object({
  n_companies: z.number().int(),
  n_suppliers: z.number().int(),
  n_finished_goods: z.number().int(),
  n_raw_materials: z.number().int(),
  n_supplier_products: z.number().int(),
  n_bom_edges: z.number().int(),
  top_families: z.array(z.tuple([z.string(), z.number().int()])),
  top_roles: z.array(z.tuple([z.string(), z.number().int()])),
  sole_source_raw_ids: z.array(z.number().int()),
});
export type SupplyNetworkAggregates = z.infer<typeof SupplyNetworkAggregates>;

export const SupplyNetworkBundle = z.object({
  schema_version: z.string(),
  generated_at: z.string(),
  aggregates: SupplyNetworkAggregates,
  companies: z.array(CompanyNode),
  suppliers: z.array(SupplierNode),
  products: z.array(ProductNode),
  supplier_product_edges: z.array(SupplierProductEdge),
  company_supplier_edges: z.array(CompanySupplierEdge),
  product_raw_edges: z.array(ProductRawEdge),
  supplier_raw_edges: z.array(SupplierRawEdge),
});
export type SupplyNetworkBundle = z.infer<typeof SupplyNetworkBundle>;

export const DashboardBundle = z.object({
  summary: Summary,
  registry: RegistryBundle.nullable().optional(),
  candidates: SubstituteCandidateReport.nullable().optional(),
  evidence: EvidenceReport.nullable().optional(),
  assessments: AssessmentReport.nullable().optional(),
  recommendations: RecommendationReport.nullable().optional(),
  opportunity_details: z.array(OpportunityDetail),
  supply_network: SupplyNetworkBundle.nullable().optional(),
  missing: z.array(z.string()),
});
export type DashboardBundle = z.infer<typeof DashboardBundle>;

export const RunStatus = z.enum([
  "starting",
  "running",
  "succeeded",
  "failed",
  "cancelled",
]);
export type RunStatus = z.infer<typeof RunStatus>;

export const RunMeta = z.object({
  run_id: z.string(),
  phase: z.string(),
  args: z.array(z.string()),
  status: RunStatus,
  started_at: z.number(),
  ended_at: z.number().nullable().optional(),
  exit_code: z.number().nullable().optional(),
  error: z.string().nullable().optional(),
  pid: z.number().nullable().optional(),
  log_count: z.number().int().optional(),
});
export type RunMeta = z.infer<typeof RunMeta>;

export const RunSnapshot = RunMeta.extend({
  logs: z
    .array(
      z.object({
        ts: z.number(),
        stream: z.enum(["stdout", "stderr"]),
        text: z.string(),
      }),
    )
    .default([]),
});
export type RunSnapshot = z.infer<typeof RunSnapshot>;
