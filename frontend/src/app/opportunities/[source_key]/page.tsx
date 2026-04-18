"use client";

import Link from "next/link";
import { use, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/empty";
import {
  AssessmentBadge,
  GradeBadge,
  PolarityBadge,
} from "@/components/grade-badge";
import { ScoreBar, ScoreRadial } from "@/components/score-bar";
import { Spinner } from "@/components/spinner";
import type {
  OpportunityDetail,
  SourcingRecommendation,
  SubstituteAssessment,
  SubstituteEvidence,
} from "@/lib/schema";
import { formatScore, prettyKey } from "@/lib/utils";

const TABS = ["Recommendations", "Evidence", "Assessment"] as const;
type Tab = (typeof TABS)[number];

export default function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ source_key: string }>;
}) {
  const { source_key } = use(params);
  const [tab, setTab] = useState<Tab>("Recommendations");

  const q = useQuery({
    queryKey: ["opportunity", source_key],
    queryFn: () => api.opportunity(source_key),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (q.isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Spinner label="Loading opportunity…" />
      </div>
    );
  }
  if (q.isError || !q.data) {
    return (
      <ErrorState
        title="Could not load this opportunity."
        detail={(q.error as Error | undefined)?.message}
      />
    );
  }

  const detail = q.data;
  const opp = detail.opportunity;

  return (
    <div className="space-y-6">
      <Link className="btn-ghost w-fit" href="/opportunities">
        <ArrowLeft className="h-4 w-4" />
        All opportunities
      </Link>

      <header className="card grid grid-cols-1 gap-5 px-5 py-5 md:grid-cols-[auto,1fr]">
        <div className="flex items-center justify-center">
          <ScoreRadial
            value={opp.aggregate_final_score}
            label="final"
            size={104}
          />
        </div>
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <GradeBadge grade={opp.recommendation_grade} />
            <span className="chip">
              {opp.n_products_covered} products · {opp.n_companies_covered}{" "}
              companies
            </span>
            <span className="chip">via {opp.decision_path}</span>
            {opp.review_required ? (
              <span className="chip border-warn/40 bg-warn/10 text-warn">
                review required
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <div className="text-xl font-semibold">
              {opp.source_display_name}
            </div>
            <div className="text-fg-muted">→</div>
            <div className="text-xl font-semibold text-accent">
              {opp.best_candidate_display_name}
            </div>
          </div>
          <p className="max-w-3xl text-sm leading-relaxed text-fg-soft">
            {opp.tradeoff_summary}
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <ScoreBar
              value={opp.aggregate_final_score}
              label="Final"
              tone="accent"
            />
            <ScoreBar
              value={opp.aggregate_sourcing_benefit}
              label="Sourcing benefit"
              tone="good"
            />
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs uppercase tracking-wide text-fg-muted">
              Suppliers
            </span>
            {opp.unique_current_suppliers.map((s) => (
              <span key={s} className="chip">
                {s}
              </span>
            ))}
          </div>
          {opp.risk_notes.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs uppercase tracking-wide text-fg-muted">
                Risks
              </span>
              {opp.risk_notes.map((r) => (
                <span
                  key={r}
                  className="chip border-warn/40 bg-warn/10 text-warn"
                >
                  {r}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </header>

      <div className="flex items-center gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={
              "border-b-2 px-4 py-2 text-sm transition-colors " +
              (tab === t
                ? "border-accent text-fg"
                : "border-transparent text-fg-muted hover:text-fg")
            }
          >
            {t}
            {tabCount(t, detail) !== undefined ? (
              <span className="ml-2 chip">{tabCount(t, detail)}</span>
            ) : null}
          </button>
        ))}
      </div>

      {tab === "Recommendations" ? (
        <RecommendationsTab rows={detail.rows} />
      ) : tab === "Evidence" ? (
        <EvidenceTab evidence={detail.evidence} />
      ) : (
        <AssessmentTab assessments={detail.assessments} />
      )}
    </div>
  );
}

function tabCount(t: Tab, d: OpportunityDetail): number | undefined {
  if (t === "Recommendations") return d.rows.length;
  if (t === "Evidence") return d.evidence.length;
  if (t === "Assessment") return d.assessments.length;
  return undefined;
}

function RecommendationsTab({ rows }: { rows: SourcingRecommendation[] }) {
  if (rows.length === 0) {
    return (
      <div className="card px-4 py-10 text-center text-sm text-fg-muted">
        No per-tuple recommendations for this source.
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
            <th className="px-4 py-2">Company / product</th>
            <th className="px-4 py-2">Candidate</th>
            <th className="px-4 py-2">Grade</th>
            <th className="px-4 py-2">Scores</th>
            <th className="px-4 py-2">Suppliers</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`${r.company_id}-${r.finished_product_id}-${r.candidate_key}`}
              className="border-t border-border"
            >
              <td className="px-4 py-3">
                <div className="font-medium">
                  {r.company_name ?? `Company ${r.company_id}`}
                </div>
                <div className="text-xs text-fg-muted">
                  {r.finished_product_sku ??
                    `Product #${r.finished_product_id}`}
                </div>
              </td>
              <td className="px-4 py-3">
                <div className="font-medium">{r.candidate_display_name}</div>
                <div className="text-xs text-fg-muted">{r.candidate_key}</div>
              </td>
              <td className="px-4 py-3">
                <GradeBadge grade={r.recommendation_grade} />
                <div className="mt-1 text-xs text-fg-muted">
                  via {r.decision_path}
                  {r.review_required ? " · review" : ""}
                </div>
              </td>
              <td className="px-4 py-3 font-mono text-xs">
                final {formatScore(r.final_score)} · accept{" "}
                {formatScore(r.acceptability)}
                <br />
                sub {formatScore(r.substitute_score)} · source{" "}
                {formatScore(r.sourcing_benefit)}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {r.current_suppliers.map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
                {r.risk_notes.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {r.risk_notes.map((n) => (
                      <span
                        key={n}
                        className="chip border-warn/40 bg-warn/10 text-warn"
                      >
                        {n}
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
  );
}

function EvidenceTab({ evidence }: { evidence: SubstituteEvidence[] }) {
  if (evidence.length === 0) {
    return (
      <div className="card px-4 py-10 text-center text-sm text-fg-muted">
        No grounded evidence yet for this source. Run Phase 5 to populate.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {evidence.map((e) => (
        <div key={e.candidate_key} className="card px-5 py-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <div className="text-sm uppercase tracking-wide text-fg-muted">
                candidate
              </div>
              <div className="text-lg font-semibold">
                {prettyKey(e.candidate_key)}
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-fg-muted">
              <span className="chip">{e.n_citations} citations</span>
              {e.any_contradictions ? (
                <span className="chip border-bad/40 bg-bad/10 text-bad">
                  contradictions
                </span>
              ) : null}
              <span className="chip">{e.llm_model}</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3">
            {e.claims.map((c) => (
              <div key={c.key} className="card-muted px-3 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold">
                    {prettyKey(c.key)}
                  </div>
                  <div className="flex items-center gap-2">
                    <PolarityBadge polarity={c.polarity} />
                    <span className="chip">{c.grounding_strength}</span>
                    <span className="chip">
                      conf {formatScore(c.confidence)}
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-fg-soft">{c.value}</p>
                {c.citations.length > 0 ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer select-none text-xs text-fg-muted">
                      {c.citations.length} citations
                    </summary>
                    <ul className="mt-2 space-y-1 text-xs">
                      {c.citations.map((cit, i) => (
                        <li key={i}>
                          <a
                            className="link inline-flex items-center gap-1"
                            href={cit.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink className="h-3 w-3" />
                            <span className="truncate">
                              {cit.title ?? cit.domain ?? cit.url}
                            </span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function AssessmentTab({
  assessments,
}: {
  assessments: SubstituteAssessment[];
}) {
  const byCandidate = useMemo(() => {
    const out = new Map<string, SubstituteAssessment[]>();
    for (const a of assessments) {
      if (!out.has(a.candidate_key)) out.set(a.candidate_key, []);
      out.get(a.candidate_key)!.push(a);
    }
    return Array.from(out.entries()).sort((a, b) =>
      a[0].localeCompare(b[0]),
    );
  }, [assessments]);

  if (assessments.length === 0) {
    return (
      <div className="card px-4 py-10 text-center text-sm text-fg-muted">
        No assessments yet. Run Phase 6 to populate.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {byCandidate.map(([candidate, items]) => (
        <div key={candidate} className="card px-5 py-4">
          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold">{prettyKey(candidate)}</div>
            <span className="chip">{items.length} tuples</span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3">
            {items.map((a, idx) => (
              <div
                key={`${a.company_id}-${a.finished_product_id}-${idx}`}
                className="card-muted px-3 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">
                      {a.company_name ?? `Company ${a.company_id}`}
                    </div>
                    <div className="text-xs text-fg-muted">
                      {a.finished_product_sku ??
                        `Product #${a.finished_product_id}`}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <AssessmentBadge klass={a.recommendation_class} />
                    <span className="chip">
                      accept {formatScore(a.acceptability)}
                    </span>
                    <span className="chip">via {a.decision_path}</span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-fg-soft">{a.rationale}</p>
                {a.caveats.length > 0 || a.contradictions.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {a.caveats.map((c) => (
                      <span
                        key={`caveat-${c}`}
                        className="chip border-warn/40 bg-warn/10 text-warn"
                      >
                        caveat: {c}
                      </span>
                    ))}
                    {a.contradictions.map((c) => (
                      <span
                        key={`contra-${c}`}
                        className="chip border-bad/40 bg-bad/10 text-bad"
                      >
                        contradiction: {c}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
