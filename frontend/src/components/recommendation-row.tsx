import { ArrowRight } from "lucide-react";
import { GradeBadge } from "@/components/grade-badge";
import { ScoreBar } from "@/components/score-bar";
import type { SourcingRecommendation } from "@/lib/schema";
import { formatScore } from "@/lib/utils";

export function RecommendationRow({ r }: { r: SourcingRecommendation }) {
  return (
    <div className="card-muted grid grid-cols-1 gap-3 px-4 py-3 md:grid-cols-[1.2fr,1fr,1fr,1fr]">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <GradeBadge grade={r.recommendation_grade} />
          <span className="chip text-xs">via {r.decision_path}</span>
          {r.review_required ? (
            <span className="chip border-warn/40 bg-warn/10 text-warn">
              review
            </span>
          ) : null}
        </div>
        <div className="mt-1 text-sm font-semibold">
          {r.company_name ?? `Company ${r.company_id}`}
        </div>
        <div className="text-xs text-fg-muted">
          {r.finished_product_sku ?? `Product #${r.finished_product_id}`}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1 text-xs">
          <span className="text-fg-soft">{r.source_display_name}</span>
          <ArrowRight className="h-3 w-3 text-fg-muted" />
          <span className="font-semibold text-accent">
            {r.candidate_display_name}
          </span>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <ScoreBar value={r.final_score} label="Final" tone="accent" />
        <ScoreBar value={r.acceptability} label="Acceptability" tone="good" />
        <ScoreBar
          value={r.sourcing_benefit}
          label="Sourcing benefit"
          tone="warn"
        />
        {typeof r.substitute_score === "number" ? (
          <div className="text-[11px] font-mono text-fg-muted">
            substitute {formatScore(r.substitute_score)}
          </div>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 text-xs">
        <div className="text-fg-muted">Current suppliers</div>
        <div className="flex flex-wrap gap-1">
          {r.current_suppliers.length === 0 ? (
            <span className="text-fg-muted">—</span>
          ) : (
            r.current_suppliers.map((s) => (
              <span key={`cur-${s}`} className="chip">
                {s}
              </span>
            ))
          )}
        </div>
        <div className="mt-1 text-fg-muted">Recommended</div>
        <div className="flex flex-wrap gap-1">
          {r.recommended_suppliers.length === 0 ? (
            <span className="text-fg-muted">—</span>
          ) : (
            r.recommended_suppliers.map((s) => (
              <span
                key={`rec-${s}`}
                className="chip border-accent/40 bg-accent/10 text-accent"
              >
                {s}
              </span>
            ))
          )}
        </div>
      </div>
      <div className="flex flex-col gap-2 text-xs">
        <p className="line-clamp-4 text-fg-soft" title={r.tradeoff_summary}>
          {r.tradeoff_summary}
        </p>
        {r.caveats.length > 0 || r.risk_notes.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {r.caveats.map((c) => (
              <span
                key={`cav-${c}`}
                className="chip border-warn/40 bg-warn/10 text-warn"
              >
                caveat: {c}
              </span>
            ))}
            {r.risk_notes.map((c) => (
              <span
                key={`risk-${c}`}
                className="chip border-bad/40 bg-bad/10 text-bad"
              >
                risk: {c}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
