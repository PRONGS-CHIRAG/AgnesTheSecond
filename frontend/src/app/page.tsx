"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  FlaskConical,
  Gauge,
  Link2,
  Network,
  ScrollText,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Empty, ErrorState } from "@/components/empty";
import { AssessmentBadge, GradeBadge } from "@/components/grade-badge";
import { ScoreBar, ScoreRadial } from "@/components/score-bar";
import { Spinner } from "@/components/spinner";
import { StatCard } from "@/components/stat-card";
import { Donut, type DonutSlice } from "@/components/donut";
import { HorizontalBars } from "@/components/horizontal-bars";
import { OpportunityHero } from "@/components/opportunity-hero";
import { ClaimCard } from "@/components/claim-card";
import { RecommendationRow } from "@/components/recommendation-row";
import { CollapseSection } from "@/components/collapse-section";
import { SupplyNetworkSection } from "@/components/supply-network-section";
import { useDashboard } from "@/lib/useDashboard";
import type {
  CanonicalMaterial,
  DashboardBundle,
  SourcingRecommendation,
  SubstituteAssessment,
  SubstituteEvidence,
} from "@/lib/schema";
import { cn, formatScore, humanAge, prettyKey } from "@/lib/utils";

const ASSESS_TONE: Record<string, DonutSlice["tone"]> = {
  recommend: "good",
  recommend_with_caveats: "warn",
  do_not_recommend: "bad",
  insufficient_evidence: "muted",
};

export default function DashboardPage() {
  const { data, isLoading, isError, error } = useDashboard();

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Could not reach the Agnes API."
        detail={
          (error as Error | undefined)?.message ??
          "Is the FastAPI server running on http://localhost:8000?"
        }
      />
    );
  }

  return <DashboardView bundle={data} />;
}

/* ─────────────────────────── view ─────────────────────────── */

function DashboardView({ bundle }: { bundle: DashboardBundle }) {
  const s = bundle.summary;
  const registry = bundle.registry;
  const rec = bundle.recommendations;
  const asmt = bundle.assessments;
  const ev = bundle.evidence;
  const cands = bundle.candidates;
  const missing = new Set(bundle.missing);

  const statusFor = (name: string) =>
    s.artifacts.find((a) => a.name === name) ?? null;

  const topOpp = useMemo(() => {
    const list = rec?.opportunities ?? [];
    return [...list].sort(
      (a, b) => b.aggregate_final_score - a.aggregate_final_score,
    )[0];
  }, [rec]);

  const opportunitiesSorted = useMemo(() => {
    const list = rec?.opportunities ?? [];
    return [...list].sort(
      (a, b) => b.aggregate_final_score - a.aggregate_final_score,
    );
  }, [rec]);

  const rowsByOpportunity = useMemo(() => {
    const out = new Map<string, SourcingRecommendation[]>();
    for (const r of rec?.items ?? []) {
      if (!out.has(r.source_key)) out.set(r.source_key, []);
      out.get(r.source_key)!.push(r);
    }
    for (const arr of out.values()) {
      arr.sort((a, b) => b.final_score - a.final_score);
    }
    return out;
  }, [rec]);

  const partialPhases = [
    cands?.partial ? "candidates" : null,
    ev?.partial ? "evidence" : null,
    asmt?.partial ? "assessments" : null,
    rec?.partial ? "recommendations" : null,
  ].filter(Boolean) as string[];

  const oldestArtifact = useMemo(() => {
    const withTs = s.artifacts.filter(
      (a) => a.present && a.generated_at,
    ) as Array<{ name: string; generated_at: string }>;
    if (withTs.length === 0) return null;
    return withTs.reduce((a, b) =>
      new Date(a.generated_at).getTime() < new Date(b.generated_at).getTime()
        ? a
        : b,
    );
  }, [s.artifacts]);

  return (
    <div className="space-y-8">
      {/* 1. Header strip */}
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="flex items-center gap-2 text-2xl font-semibold">
              <Sparkles className="h-5 w-5 text-accent" />
              Agnes command center
            </h1>
            <p className="text-sm text-fg-muted">
              Every canonical material, candidate, claim, assessment, and
              recommendation — rendered from a single request against the
              FastAPI artifact bundle.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {oldestArtifact ? (
              <span className="chip" title={oldestArtifact.generated_at}>
                oldest · {humanAge(oldestArtifact.generated_at)} ({oldestArtifact.name})
              </span>
            ) : null}
            {missing.size > 0 ? (
              <span className="chip border-warn/40 bg-warn/10 text-warn">
                {missing.size} phase{missing.size === 1 ? "" : "s"} not yet run
              </span>
            ) : (
              <span className="chip border-good/40 bg-good/10 text-good">
                <CheckCircle2 className="h-3 w-3" /> all phases present
              </span>
            )}
          </div>
        </div>

        {partialPhases.length > 0 ? (
          <div className="rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-warn">
            <div className="flex items-center gap-2 font-semibold">
              <AlertTriangle className="h-4 w-4" />
              Partial run detected in {partialPhases.join(", ")}
            </div>
            <div className="mt-1 text-warn/80">
              Typically an LLM quota or budget ceiling. Open{" "}
              <Link className="link" href="/runs">
                the Runs console
              </Link>{" "}
              to re-run with a higher budget or different model.
            </div>
          </div>
        ) : null}
      </header>

      {/* 2. KPI row */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <a href="#materials" className="contents">
          <StatCard
            title="Canonical materials"
            icon={<Boxes className="h-4 w-4" />}
            present={statusFor("registry")?.present}
            generatedAt={statusFor("registry")?.generated_at}
            value={s.canonical?.unique_canonical_keys ?? "—"}
            subtitle={
              s.canonical
                ? `${s.canonical.assigned} assigned · ${s.canonical.unassigned} unassigned`
                : "Phase 2 not run"
            }
          />
        </a>
        <a href="#candidates" className="contents">
          <StatCard
            title="Candidates"
            icon={<Link2 className="h-4 w-4" />}
            present={statusFor("candidates")?.present}
            generatedAt={statusFor("candidates")?.generated_at}
            value={s.candidates?.n_candidates ?? "—"}
            subtitle={
              s.candidates
                ? `${s.candidates.n_targets} sources · avg top ${
                    s.candidates.avg_top_score
                      ? Number(s.candidates.avg_top_score).toFixed(2)
                      : "—"
                  }`
                : "Phase 4 not run"
            }
          />
        </a>
        <a href="#evidence" className="contents">
          <StatCard
            title="Evidence pairs"
            icon={<FlaskConical className="h-4 w-4" />}
            present={statusFor("evidence")?.present}
            generatedAt={statusFor("evidence")?.generated_at}
            value={s.evidence?.n_pairs ?? "—"}
            subtitle={
              s.evidence
                ? `${s.evidence.n_api_calls} api · ${s.evidence.n_cache_hits} cache${
                    s.evidence.partial ? " · partial" : ""
                  }`
                : "Phase 5 not run"
            }
          />
        </a>
        <a href="#assessments" className="contents">
          <StatCard
            title="Assessments"
            icon={<ScrollText className="h-4 w-4" />}
            present={statusFor("assessments")?.present}
            generatedAt={statusFor("assessments")?.generated_at}
            value={s.assessments?.n_tuples ?? "—"}
            subtitle={
              s.assessments
                ? countsToSubtitle(
                    s.assessments.counts_by_class as Record<string, number>,
                  )
                : "Phase 6 not run"
            }
          />
        </a>
        <a href="#opportunities" className="contents">
          <StatCard
            title="Opportunities"
            icon={<Gauge className="h-4 w-4" />}
            present={statusFor("recommendations")?.present}
            generatedAt={statusFor("recommendations")?.generated_at}
            value={s.recommendations?.n_opportunities ?? "—"}
            subtitle={
              s.recommendations
                ? countsToSubtitle(
                    s.recommendations.counts_by_grade as Record<string, number>,
                  )
                : "Phase 7 not run"
            }
          />
        </a>
        <a href="#supply-network" className="contents">
          <StatCard
            title="Supply network"
            icon={<Network className="h-4 w-4" />}
            present={bundle.supply_network != null}
            value={bundle.supply_network?.aggregates.n_suppliers ?? "—"}
            subtitle={
              bundle.supply_network
                ? `${bundle.supply_network.aggregates.n_companies} procurers · ${bundle.supply_network.aggregates.n_supplier_products} edges`
                : "Database unavailable"
            }
          />
        </a>
      </section>

      {/* 3. Top opportunity hero */}
      <section>
        <SectionHeader
          title="Top consolidation opportunity"
          link={{ href: "/opportunities", label: "See all" }}
        />
        {topOpp ? (
          <div className="mt-3">
            <OpportunityHero opp={topOpp} />
          </div>
        ) : (
          <Empty
            className="mt-3"
            title="No opportunities yet."
            description="Run Phase 4 → 5 → 6 → 7 to populate the sourcing recommendation board."
            action={
              <Link className="btn-primary" href="/runs">
                Open runs console
              </Link>
            }
          />
        )}
      </section>

      {/* 4. Opportunities table */}
      <section id="opportunities">
        <SectionHeader
          title={`All opportunities (${opportunitiesSorted.length})`}
          subtitle="Ranked by aggregate final score."
          link={{ href: "/opportunities", label: "Dedicated view" }}
        />
        {opportunitiesSorted.length === 0 ? (
          <Empty
            className="mt-3"
            title="No consolidation opportunities."
            description="Run Phase 7 to populate this board."
          />
        ) : (
          <div className="mt-3 overflow-hidden rounded-xl border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                  <th className="px-4 py-2">Source → Best candidate</th>
                  <th className="px-4 py-2">Grade</th>
                  <th className="px-4 py-2">Final</th>
                  <th className="px-4 py-2">Sourcing</th>
                  <th className="px-4 py-2">Coverage</th>
                  <th className="px-4 py-2">Suppliers</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {opportunitiesSorted.map((o) => (
                  <tr
                    key={o.source_key}
                    className="border-t border-border hover:bg-bg-muted/40"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium">{o.source_display_name}</div>
                      <div className="text-xs text-fg-muted">
                        → {o.best_candidate_display_name}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <GradeBadge grade={o.recommendation_grade} />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreRadial
                        value={o.aggregate_final_score}
                        size={52}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar
                        value={o.aggregate_sourcing_benefit}
                        tone="good"
                        className="w-28"
                      />
                    </td>
                    <td className="px-4 py-3 text-xs text-fg-soft">
                      {o.n_products_covered} products ·{" "}
                      {o.n_companies_covered} companies
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1">
                        <span className="chip">
                          {o.unique_current_suppliers.length} current
                        </span>
                        <span className="chip border-accent/40 bg-accent/10 text-accent">
                          {o.unique_recommended_suppliers.length} recommended
                        </span>
                        {o.review_required ? (
                          <span className="chip border-warn/40 bg-warn/10 text-warn">
                            review
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        className="btn-ghost"
                        href={`/opportunities/${encodeURIComponent(o.source_key)}`}
                      >
                        Open <ArrowUpRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 5. Recommendations by opportunity */}
      <section id="recommendations">
        <SectionHeader
          title="Per-tuple recommendations"
          subtitle="Every company × finished-product pairing grouped by opportunity."
        />
        {missing.has("recommendations") ? (
          <Empty
            className="mt-3"
            title="No recommendations yet."
            description="Run Phase 7 to generate per-tuple sourcing calls."
            action={
              <Link className="btn-primary" href="/runs">
                Open runs console
              </Link>
            }
          />
        ) : (
          <div className="mt-3 space-y-3">
            {opportunitiesSorted.map((o) => {
              const rows = rowsByOpportunity.get(o.source_key) ?? [];
              return (
                <CollapseSection
                  key={o.source_key}
                  defaultOpen={o.source_key === topOpp?.source_key}
                  title={
                    <span>
                      {o.source_display_name}{" "}
                      <span className="text-fg-muted">→</span>{" "}
                      <span className="text-accent">
                        {o.best_candidate_display_name}
                      </span>
                    </span>
                  }
                  subtitle={`${rows.length} tuple${rows.length === 1 ? "" : "s"} · ${o.n_companies_covered} companies`}
                  rightSlot={
                    <>
                      <GradeBadge grade={o.recommendation_grade} />
                      <span className="chip font-mono">
                        final {formatScore(o.aggregate_final_score)}
                      </span>
                    </>
                  }
                >
                  <div className="flex flex-col gap-2">
                    {rows.map((r) => (
                      <RecommendationRow
                        key={`${r.company_id}-${r.finished_product_id}-${r.candidate_key}`}
                        r={r}
                      />
                    ))}
                  </div>
                </CollapseSection>
              );
            })}
          </div>
        )}
      </section>

      {/* 6. Evidence highlights */}
      <section id="evidence">
        <SectionHeader
          title={`Evidence (${ev?.n_pairs ?? 0} pairs)`}
          subtitle="Grounded claims with polarity, confidence, and citations."
        />
        {missing.has("evidence") ? (
          <Empty
            className="mt-3"
            title="No grounded evidence yet."
            description="Run Phase 5 to fetch evidence for your top candidates."
            action={
              <Link className="btn-primary" href="/runs">
                Open runs console
              </Link>
            }
          />
        ) : (
          <EvidenceSection items={ev?.items ?? []} />
        )}
      </section>

      {/* 7. Assessments */}
      <section id="assessments">
        <SectionHeader
          title={`Assessments (${asmt?.n_tuples ?? 0})`}
          subtitle="Rule + LLM decisions per source × candidate × tuple."
        />
        {missing.has("assessments") ? (
          <Empty
            className="mt-3"
            title="No assessments yet."
            description="Run Phase 6 to synthesize compliance-aware decisions."
            action={
              <Link className="btn-primary" href="/runs">
                Open runs console
              </Link>
            }
          />
        ) : (
          <AssessmentsSection
            items={asmt?.items ?? []}
            counts={asmt?.counts_by_class ?? {}}
          />
        )}
      </section>

      {/* 8. Canonical materials — family / role / histogram + preview */}
      <section id="materials">
        <SectionHeader
          title={`Canonical materials (${registry?.total ?? 0})`}
          subtitle="Distribution across ingredient families, functional roles, and parser confidence."
          link={
            registry
              ? { href: "/materials", label: "Browse all" }
              : undefined
          }
        />
        {missing.has("registry") || !registry ? (
          <Empty
            className="mt-3"
            title="No canonical registry yet."
            description="Run Phase 2 to canonicalize raw materials."
          />
        ) : (
          <>
            <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
              <HorizontalBars
                title={`Ingredient families (${registry.families.length})`}
                tone="accent"
                rows={Object.entries(registry.family_counts).map(([k, v]) => ({
                  key: k,
                  label: prettyKey(k),
                  value: v,
                }))}
                maxRows={12}
              />
              <HorizontalBars
                title={`Functional roles (${registry.roles.length})`}
                tone="good"
                rows={Object.entries(registry.role_counts).map(([k, v]) => ({
                  key: k,
                  label: prettyKey(k),
                  value: v,
                }))}
                maxRows={12}
              />
              <HorizontalBars
                title="Canonicalization confidence"
                tone="warn"
                rows={registry.confidence_histogram.map((b) => ({
                  key: b.bucket,
                  label: b.bucket,
                  value: b.n,
                }))}
              />
            </div>
            <MaterialsPreview items={registry.items.slice(0, 12)} total={registry.total} />
          </>
        )}
      </section>

      {/* 8.5 Supply network (DB-backed) */}
      <section id="supply-network">
        <SectionHeader
          title={
            bundle.supply_network
              ? `Supply network (${bundle.supply_network.aggregates.n_suppliers} suppliers · ${bundle.supply_network.aggregates.n_companies} procurers · ${bundle.supply_network.aggregates.n_raw_materials} raw materials)`
              : "Supply network"
          }
          subtitle="Interactive tables connecting procurers, suppliers, products, and raw materials."
        />
        {bundle.supply_network ? (
          <div className="mt-3">
            <SupplyNetworkSection bundle={bundle.supply_network} />
          </div>
        ) : (
          <Empty
            className="mt-3"
            title="Supply network unavailable."
            description="The challenge SQLite DB could not be reached. Check AGNES_DB_PATH and that outputs/reports is populated."
          />
        )}
      </section>

      {/* 9. Candidates peek (phase 4) */}
      <section id="candidates">
        <SectionHeader
          title={`Substitute candidates (${cands?.candidates.length ?? 0})`}
          subtitle="Embedding + family/role scored pairs that seed the evidence phase."
        />
        {missing.has("candidates") ? (
          <Empty
            className="mt-3"
            title="No candidates yet."
            description="Run Phase 4 to generate substitute candidates."
            action={
              <Link className="btn-primary" href="/runs">
                Open runs console
              </Link>
            }
          />
        ) : cands && cands.candidates.length > 0 ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                  <th className="px-4 py-2">Source → candidate</th>
                  <th className="px-4 py-2">Family</th>
                  <th className="px-4 py-2">Score</th>
                  <th className="px-4 py-2">Features</th>
                </tr>
              </thead>
              <tbody>
                {cands.candidates.map((c, i) => (
                  <tr
                    key={`${c.source_key}-${c.candidate_key}-${i}`}
                    className="border-t border-border"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium">
                        {prettyKey(c.source_key)}{" "}
                        <span className="text-fg-muted">→</span>{" "}
                        <span className="text-accent">
                          {prettyKey(c.candidate_key)}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.roles.map((r) => (
                          <span key={r} className="chip">
                            {prettyKey(r)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-fg-soft">
                      {c.family ? prettyKey(c.family) : "—"}
                    </td>
                    <td className="px-4 py-3 w-48">
                      <ScoreBar
                        value={c.score}
                        tone="accent"
                        label="score"
                      />
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-fg-muted">
                      <FeatureRow label="family" value={c.features.family_match} />
                      <FeatureRow label="role" value={c.features.role_match} />
                      <FeatureRow label="lex" value={c.features.lexical_sim} />
                      <FeatureRow label="embed" value={c.features.embed_sim} />
                      {typeof c.features.supplier_overlap === "number" ? (
                        <FeatureRow
                          label="supplier"
                          value={c.features.supplier_overlap}
                        />
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty className="mt-3" title="No candidates produced." />
        )}
      </section>

      {/* 10. Pipeline health footer */}
      <section>
        <SectionHeader title="Pipeline health" />
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          <PhaseHealth
            name="Canonical registry"
            artifact={statusFor("registry")}
            stats={
              registry
                ? [
                    ["materials", registry.total],
                    ["unique keys", registry.unique_canonical_keys ?? "—"],
                    [
                      "coverage",
                      registry.coverage
                        ? `${registry.coverage.assigned} ok · ${registry.coverage.unassigned} missing`
                        : "—",
                    ],
                    ["taxonomy", registry.taxonomy_version ?? "—"],
                  ]
                : []
            }
          />
          <PhaseHealth
            name="Candidates"
            artifact={statusFor("candidates")}
            partial={cands?.partial}
            stats={
              cands
                ? [
                    ["targets", cands.n_targets],
                    ["with candidates", cands.n_with_candidates],
                    ["top K", cands.top_k],
                    ["min score", formatScore(cands.min_score)],
                    ["embedding", cands.embedding_model ?? "—"],
                  ]
                : []
            }
          />
          <PhaseHealth
            name="Evidence"
            artifact={statusFor("evidence")}
            partial={ev?.partial}
            stats={
              ev
                ? [
                    ["pairs", ev.n_pairs],
                    ["cache hits", ev.n_cache_hits],
                    ["api calls", ev.n_api_calls],
                    ["failures", ev.n_failures],
                    ["duration", `${(ev.duration_ms / 1000).toFixed(1)}s`],
                    ["llm", ev.llm_model],
                  ]
                : []
            }
          />
          <PhaseHealth
            name="Assessments"
            artifact={statusFor("assessments")}
            partial={asmt?.partial}
            stats={
              asmt
                ? [
                    ["tuples", asmt.n_tuples],
                    ["rules", asmt.n_rules_decisions],
                    ["llm", asmt.n_llm_decisions],
                    ["cache", asmt.n_cache_hits],
                    ["failures", asmt.n_failures],
                    ["no evidence", asmt.n_without_evidence],
                  ]
                : []
            }
          />
          <PhaseHealth
            name="Recommendations"
            artifact={statusFor("recommendations")}
            partial={rec?.partial}
            stats={
              rec
                ? [
                    ["tuples", rec.n_tuples],
                    ["opportunities", rec.n_opportunities],
                    ["api calls", rec.n_api_calls],
                    ["failures", rec.n_failures],
                    ["duration", `${(rec.duration_ms / 1000).toFixed(1)}s`],
                  ]
                : []
            }
          />
        </div>
      </section>
    </div>
  );
}

/* ─────────────────────────── sub-sections ─────────────────────────── */

function EvidenceSection({ items }: { items: SubstituteEvidence[] }) {
  if (items.length === 0) {
    return (
      <Empty
        className="mt-3"
        title="No evidence items."
        description="Run Phase 5 against a source to fetch grounded claims."
      />
    );
  }
  return (
    <div className="mt-3 flex flex-col gap-3">
      {items.map((e) => (
        <div key={`${e.source_key}-${e.candidate_key}`} className="card px-5 py-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-fg-muted">
                {prettyKey(e.source_key)}
              </div>
              <div className="text-lg font-semibold">
                <span className="text-fg-muted">→</span>{" "}
                <span className="text-accent">{prettyKey(e.candidate_key)}</span>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="chip">{e.claims.length} claims</span>
              <span className="chip">{e.n_citations} citations</span>
              {e.any_contradictions ? (
                <span className="chip border-bad/40 bg-bad/10 text-bad">
                  <ShieldAlert className="h-3 w-3" /> contradictions
                </span>
              ) : null}
              <span className="chip">{e.llm_model}</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {e.claims.map((c) => (
              <ClaimCard key={`${e.candidate_key}-${c.key}`} claim={c} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function AssessmentsSection({
  items,
  counts,
}: {
  items: SubstituteAssessment[];
  counts: Record<string, number>;
}) {
  const donutSlices: DonutSlice[] = Object.entries(counts).map(([k, v]) => ({
    key: k,
    label: prettyKey(k),
    value: v,
    tone: ASSESS_TONE[k] ?? "muted",
  }));

  return (
    <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[auto,1fr]">
      <div className="card px-4 py-4">
        <div className="mb-2 text-sm font-semibold">Recommendation mix</div>
        <Donut slices={donutSlices} centerLabel="tuples" size={160} />
      </div>
      <div className="card px-4 py-4">
        <div className="mb-2 text-sm font-semibold">All assessed tuples</div>
        {items.length === 0 ? (
          <div className="py-6 text-center text-sm text-fg-muted">
            No assessments to show.
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                  <th className="px-3 py-2">Class</th>
                  <th className="px-3 py-2">Company / product</th>
                  <th className="px-3 py-2">Source → candidate</th>
                  <th className="px-3 py-2">Acceptability</th>
                  <th className="px-3 py-2">Path</th>
                  <th className="px-3 py-2">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a, idx) => (
                  <tr
                    key={`${a.company_id}-${a.finished_product_id}-${a.candidate_key}-${idx}`}
                    className="border-t border-border"
                  >
                    <td className="px-3 py-3">
                      <AssessmentBadge klass={a.recommendation_class} />
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-medium">
                        {a.company_name ?? `Company ${a.company_id}`}
                      </div>
                      <div className="text-xs text-fg-muted">
                        {a.finished_product_sku ??
                          `Product #${a.finished_product_id}`}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <div>{a.source_display_name}</div>
                      <div className="text-accent">
                        → {a.candidate_display_name}
                      </div>
                    </td>
                    <td className="px-3 py-3 w-40">
                      <ScoreBar value={a.acceptability} tone="good" />
                      <div className="mt-1 font-mono text-[11px] text-fg-muted">
                        {formatScore(a.acceptability)}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <span className="chip">{a.decision_path}</span>
                    </td>
                    <td className="px-3 py-3 text-xs text-fg-soft">
                      <p className="line-clamp-3">{a.rationale}</p>
                      {a.caveats.length > 0 || a.contradictions.length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {a.caveats.map((c) => (
                            <span
                              key={`cav-${c}`}
                              className="chip border-warn/40 bg-warn/10 text-warn"
                            >
                              caveat: {c}
                            </span>
                          ))}
                          {a.contradictions.map((c) => (
                            <span
                              key={`con-${c}`}
                              className="chip border-bad/40 bg-bad/10 text-bad"
                            >
                              contradiction: {c}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function MaterialsPreview({
  items,
  total,
}: {
  items: CanonicalMaterial[];
  total: number;
}) {
  if (!items || items.length === 0) {
    return null;
  }
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">
          Preview · first {items.length} of {total}
        </h3>
        <Link className="link text-xs" href="/materials">
          Browse all →
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items.map((m) => (
          <div
            key={`${m.company_id}-${m.raw_product_id}`}
            className="card-muted flex flex-col gap-1.5 px-3 py-3"
          >
            <div className="truncate text-sm font-semibold" title={m.normalized_name}>
              {m.normalized_name}
            </div>
            <div className="truncate text-[11px] text-fg-muted" title={m.sku}>
              {m.sku}
            </div>
            <div className="flex flex-wrap gap-1">
              <span className="chip">{prettyKey(m.ingredient_family)}</span>
              <span className="chip border-accent/40 bg-accent/10 text-accent">
                {prettyKey(m.functional_role)}
              </span>
            </div>
            <ScoreBar value={m.confidence} tone="accent" label="confidence" />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────── misc helpers ─────────────────────────── */

function SectionHeader({
  title,
  subtitle,
  link,
}: {
  title: string;
  subtitle?: string;
  link?: { href: string; label: string };
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle ? (
          <p className="text-xs text-fg-muted">{subtitle}</p>
        ) : null}
      </div>
      {link ? (
        <Link className="btn-ghost" href={link.href}>
          {link.label} <ArrowUpRight className="h-4 w-4" />
        </Link>
      ) : null}
    </div>
  );
}

function PhaseHealth({
  name,
  artifact,
  partial,
  stats,
}: {
  name: string;
  artifact: { present: boolean; generated_at?: string | null } | null;
  partial?: boolean;
  stats: Array<[string, React.ReactNode]>;
}) {
  return (
    <div className="card px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">{name}</div>
        <div className="flex items-center gap-1.5">
          {partial ? (
            <span className="chip border-warn/40 bg-warn/10 text-warn">
              partial
            </span>
          ) : null}
          {artifact?.present === false ? (
            <span className="chip border-warn/40 bg-warn/10 text-warn">missing</span>
          ) : (
            <span className="chip" title={artifact?.generated_at ?? undefined}>
              {humanAge(artifact?.generated_at ?? null)}
            </span>
          )}
        </div>
      </div>
      {stats.length > 0 ? (
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          {stats.map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-2">
              <dt className="truncate text-fg-muted">{k}</dt>
              <dd className="truncate font-mono text-fg">{v ?? "—"}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function FeatureRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span>{label}</span>
      <span>{value.toFixed(2)}</span>
    </div>
  );
}

function countsToSubtitle(counts: Record<string, number> | undefined): string {
  if (!counts) return "";
  return Object.entries(counts)
    .map(([k, v]) => `${v} ${prettyKey(k)}`)
    .join(" · ");
}

/* ─────────────────────────── skeleton ─────────────────────────── */

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Spinner label="Loading Agnes dashboard…" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "card flex h-24 animate-pulse flex-col gap-2 px-4 py-3",
            )}
          >
            <div className="h-3 w-24 rounded bg-bg-muted" />
            <div className="h-6 w-16 rounded bg-bg-muted" />
            <div className="h-3 w-32 rounded bg-bg-muted" />
          </div>
        ))}
      </div>
      <div className="card h-40 animate-pulse" />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="card h-64 animate-pulse" />
        <div className="card h-64 animate-pulse" />
        <div className="card h-64 animate-pulse" />
      </div>
    </div>
  );
}

