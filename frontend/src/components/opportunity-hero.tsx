import Link from "next/link";
import { ArrowUpRight, Database } from "lucide-react";
import { GradeBadge } from "@/components/grade-badge";
import { ScoreBar, ScoreRadial } from "@/components/score-bar";
import type { ConsolidationOpportunity } from "@/lib/schema";

export function OpportunityHero({
  opp,
  compact = false,
}: {
  opp: ConsolidationOpportunity;
  compact?: boolean;
}) {
  const radialSize = compact ? 88 : 104;
  return (
    <div className="card grid grid-cols-1 gap-6 px-5 py-5 md:grid-cols-[auto,1fr,auto]">
      <div className="flex items-center justify-center">
        <ScoreRadial
          value={opp.aggregate_final_score}
          label="final"
          size={radialSize}
        />
      </div>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <GradeBadge grade={opp.recommendation_grade} />
          <span className="chip">
            {opp.n_products_covered} products · {opp.n_companies_covered} companies
          </span>
          <span className="chip">via {opp.decision_path}</span>
          {opp.review_required ? (
            <span className="chip border-warn/40 bg-warn/10 text-warn">
              review required
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-baseline gap-x-3">
          <div className="text-xl font-semibold">{opp.source_display_name}</div>
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
            label="Final score"
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
      <div className="flex flex-col items-stretch justify-center gap-2">
        <Link
          className="btn-primary justify-center"
          href={`/opportunities/${encodeURIComponent(opp.source_key)}`}
        >
          Drill into evidence
          <ArrowUpRight className="h-4 w-4" />
        </Link>
        <Link className="btn justify-center" href="/opportunities">
          <Database className="h-4 w-4" />
          Full list
        </Link>
      </div>
    </div>
  );
}
