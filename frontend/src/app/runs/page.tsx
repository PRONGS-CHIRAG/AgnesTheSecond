"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/empty";
import { RunPanel, type FieldSpec } from "@/components/run-panel";
import { Spinner } from "@/components/spinner";

const PHASE4_FIELDS: FieldSpec[] = [
  {
    name: "target",
    label: "Single canonical key",
    kind: "text",
    placeholder: "e.g. calcium-citrate",
    help: "Leave empty and enable `all` for a full sweep.",
  },
  {
    name: "all",
    label: "Score every canonical key (--all)",
    kind: "boolean",
  },
  {
    name: "top_k",
    label: "Top K per source",
    kind: "number",
    placeholder: "10",
    min: 1,
    max: 100,
  },
  {
    name: "min_score",
    label: "Min score",
    kind: "number",
    placeholder: "0.5",
    min: 0,
    max: 1,
    step: 0.05,
  },
  { name: "cross_family", label: "Allow cross-family", kind: "boolean" },
  { name: "no_cache", label: "Bypass cache", kind: "boolean" },
  { name: "dry_run", label: "Dry run (no LLM)", kind: "boolean" },
];

const PHASE5_FIELDS: FieldSpec[] = [
  {
    name: "top_sources",
    label: "Top sources",
    kind: "number",
    placeholder: "3",
    min: 0,
    max: 500,
  },
  {
    name: "per_source",
    label: "Per source",
    kind: "number",
    placeholder: "3",
    min: 0,
    max: 50,
  },
  {
    name: "max_total",
    label: "Max new API calls",
    kind: "number",
    placeholder: "15",
    min: 0,
    max: 500,
    help: "Hard cap for this run.",
  },
  {
    name: "source",
    label: "Source filter (canonical key)",
    kind: "text",
  },
  {
    name: "model",
    label: "LLM model",
    kind: "text",
    placeholder: "gpt-4o-mini",
  },
  { name: "no_cache", label: "Bypass cache", kind: "boolean" },
  { name: "dry_run", label: "Dry run (count only)", kind: "boolean" },
];

const PHASE6_FIELDS: FieldSpec[] = [
  {
    name: "max_llm_calls",
    label: "Max LLM calls",
    kind: "number",
    placeholder: "5",
    min: 0,
    max: 500,
  },
  {
    name: "model",
    label: "LLM model",
    kind: "text",
    placeholder: "gpt-4o-mini",
  },
  {
    name: "source",
    label: "Source filter",
    kind: "text",
  },
  {
    name: "company",
    label: "Company ID filter",
    kind: "number",
  },
  { name: "no_cache", label: "Bypass cache", kind: "boolean" },
  { name: "dry_run", label: "Dry run (rules only)", kind: "boolean" },
];

const PHASE7_FIELDS: FieldSpec[] = [
  {
    name: "top_n_polish",
    label: "Top N to LLM-polish",
    kind: "number",
    placeholder: "3",
    min: 0,
    max: 100,
  },
  {
    name: "max_llm_calls",
    label: "Max LLM calls",
    kind: "number",
    placeholder: "3",
    min: 0,
    max: 500,
  },
  {
    name: "model",
    label: "LLM model",
    kind: "text",
    placeholder: "gpt-4o-mini",
  },
  {
    name: "source",
    label: "Source filter",
    kind: "text",
  },
  {
    name: "company",
    label: "Company ID filter",
    kind: "number",
  },
  {
    name: "min_grade",
    label: "Min grade",
    kind: "select",
    options: [
      { label: "safe_to_consolidate", value: "safe_to_consolidate" },
      {
        label: "likely_safe_review_required",
        value: "likely_safe_review_required",
      },
      {
        label: "potential_substitute_insufficient_evidence",
        value: "potential_substitute_insufficient_evidence",
      },
      { label: "not_recommended", value: "not_recommended" },
    ],
  },
  { name: "no_cache", label: "Bypass cache", kind: "boolean" },
  { name: "dry_run", label: "Dry run", kind: "boolean" },
];

export default function RunsPage() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });

  if (summary.isError) {
    return (
      <ErrorState
        title="Could not reach the Agnes API."
        detail={(summary.error as Error | undefined)?.message}
      />
    );
  }

  const artifact = (name: string) =>
    summary.data?.artifacts.find((a) => a.name === name);
  const partial = (k: "candidates" | "evidence" | "assessments" | "recommendations") =>
    Boolean(summary.data?.[k]?.partial);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Pipeline runs</h1>
        <p className="text-sm text-fg-muted">
          Trigger Phase 4–7 with the same flags as the CLI, tail logs in real
          time, and watch the rest of the UI refresh when a run finishes.
        </p>
      </header>

      {summary.isLoading ? (
        <div className="card flex items-center justify-center px-4 py-10">
          <Spinner label="Loading pipeline state…" />
        </div>
      ) : null}

      <RunPanel
        phase="phase4"
        title="Phase 4 · Substitute candidates"
        description="Score every canonical target and emit substitute_candidates.json."
        produces="substitute_candidates.json"
        generatedAt={artifact("candidates")?.generated_at}
        partial={partial("candidates")}
        fields={PHASE4_FIELDS}
        invalidateKeys={[["summary"], ["opportunities"]]}
      />
      <RunPanel
        phase="phase5"
        title="Phase 5 · Grounded evidence"
        description="Enrich top candidates with grounded LLM claims and web-search citations."
        produces="substitute_evidence.json"
        generatedAt={artifact("evidence")?.generated_at}
        partial={partial("evidence")}
        fields={PHASE5_FIELDS}
        invalidateKeys={[["summary"], ["opportunities"]]}
      />
      <RunPanel
        phase="phase6"
        title="Phase 6 · Compliance assessment"
        description="Rules-first verdicts with LLM polish per (company × product × candidate)."
        produces="substitute_assessments.json"
        generatedAt={artifact("assessments")?.generated_at}
        partial={partial("assessments")}
        fields={PHASE6_FIELDS}
        invalidateKeys={[["summary"], ["opportunities"]]}
      />
      <RunPanel
        phase="phase7"
        title="Phase 7 · Sourcing recommendations"
        description="Rank recommendations, surface consolidation opportunities."
        produces="sourcing_recommendations.json"
        generatedAt={artifact("recommendations")?.generated_at}
        partial={partial("recommendations")}
        fields={PHASE7_FIELDS}
        invalidateKeys={[["summary"], ["opportunities"]]}
      />
    </div>
  );
}
