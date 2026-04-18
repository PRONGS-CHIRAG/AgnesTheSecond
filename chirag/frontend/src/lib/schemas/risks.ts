import { z } from "zod";

export const RiskSeveritySchema = z.enum(["high", "medium", "low"]);
export type RiskSeverity = z.infer<typeof RiskSeveritySchema>;

export const RiskTypeSchema = z.enum([
  "single_source",
  "supplier_concentration",
  "critical_ingredient",
  "supplier_quality",
  "price_volatility",
]);
export type RiskType = z.infer<typeof RiskTypeSchema>;

export const RiskItemSchema = z.object({
  type: RiskTypeSchema,
  severity: RiskSeveritySchema,
  key: z.string(),
  label: z.string(),
  description: z.string(),
  recommendation: z.string(),
  score: z.number().min(0).max(1),
  n_companies_affected: z.number().int().nonnegative().default(0),
  n_products_affected: z.number().int().nonnegative().default(0),
  n_suppliers: z.number().int().nonnegative().default(0),
  evidence: z.array(z.string()).default([]),
});
export type RiskItem = z.infer<typeof RiskItemSchema>;

export const SupplyRiskReportSchema = z.object({
  schema_version: z.string(),
  taxonomy_version: z.string(),
  generated_at: z.string(),
  items: z.array(RiskItemSchema).default([]),
  by_severity: z.record(z.string(), z.number().int().nonnegative()).default({}),
  by_type: z.record(z.string(), z.number().int().nonnegative()).default({}),
  n_total: z.number().int().nonnegative().default(0),
  partial: z.boolean().default(false),
});
export type SupplyRiskReport = z.infer<typeof SupplyRiskReportSchema>;
