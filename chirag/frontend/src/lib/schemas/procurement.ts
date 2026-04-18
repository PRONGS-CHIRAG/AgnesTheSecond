import { z } from "zod";

export const TopSupplierSchema = z.object({
  supplier_id: z.number().int(),
  supplier_name: z.string(),
  total_spend: z.number().nonnegative(),
  n_orders: z.number().int().nonnegative(),
  on_time_rate: z.number(),
});
export type TopSupplier = z.infer<typeof TopSupplierSchema>;

export const TopIngredientSchema = z.object({
  base_name: z.string(),
  display_name: z.string(),
  total_spend: z.number().nonnegative(),
  n_orders: z.number().int().nonnegative(),
  n_suppliers: z.number().int().nonnegative(),
});
export type TopIngredient = z.infer<typeof TopIngredientSchema>;

export const ProcurementOverviewSchema = z.object({
  partial: z.boolean(),
  total_spend: z.number().nonnegative(),
  n_orders: z.number().int().nonnegative(),
  n_suppliers: z.number().int().nonnegative(),
  n_ingredients: z.number().int().nonnegative(),
  on_time_rate: z.number(),
  top_suppliers: z.array(TopSupplierSchema).default([]),
  top_ingredients: z.array(TopIngredientSchema).default([]),
});
export type ProcurementOverview = z.infer<typeof ProcurementOverviewSchema>;

export const SavingsOpportunitySchema = z.object({
  base_name: z.string(),
  display_name: z.string(),
  spread_pct: z.number(),
  signal: z.number().min(0).max(1),
  estimated_savings_usd: z.number().nonnegative(),
  best_supplier_id: z.number().int().nullable(),
  best_supplier_name: z.string().nullable(),
  best_supplier_price: z.number().nullable(),
  current_weighted_avg_price: z.number().nullable(),
  meets_gates: z.boolean(),
  evidence: z.array(z.string()).default([]),
});
export type SavingsOpportunity = z.infer<typeof SavingsOpportunitySchema>;

export const SavingsReportSchema = z.object({
  partial: z.boolean(),
  n_ingredients_evaluated: z.number().int().nonnegative(),
  n_opportunities: z.number().int().nonnegative(),
  total_estimated_savings_usd: z.number().nonnegative(),
  opportunities: z.array(SavingsOpportunitySchema).default([]),
});
export type SavingsReport = z.infer<typeof SavingsReportSchema>;

export const SupplierSummarySchema = z.object({
  supplier_id: z.number().int(),
  supplier_name: z.string(),
  total_spend: z.number().nonnegative(),
  n_orders: z.number().int().nonnegative(),
  n_ingredients: z.number().int().nonnegative(),
  on_time_rate: z.number(),
  avg_quality_pass_rate: z.number(),
  quality_score: z.number().nullable(),
  compliance_score: z.number().nullable(),
  reliability_score: z.number().nullable(),
  lead_time_days: z.number().int().nullable(),
  risk_tier: z.string().nullable(),
  certifications: z.array(z.string()).default([]),
});
export type SupplierSummary = z.infer<typeof SupplierSummarySchema>;

export const SuppliersReportSchema = z.object({
  partial: z.boolean(),
  n_suppliers: z.number().int().nonnegative(),
  suppliers: z.array(SupplierSummarySchema).default([]),
});
export type SuppliersReport = z.infer<typeof SuppliersReportSchema>;
