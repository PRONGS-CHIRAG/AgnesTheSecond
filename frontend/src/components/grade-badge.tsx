import { cn } from "@/lib/utils";
import type { Grade } from "@/lib/schema";

const LABEL: Record<Grade, string> = {
  safe_to_consolidate: "Safe to consolidate",
  likely_safe_review_required: "Likely safe · review",
  potential_substitute_insufficient_evidence: "Insufficient evidence",
  not_recommended: "Not recommended",
};

const STYLE: Record<Grade, string> = {
  safe_to_consolidate: "border-good/50 bg-good/15 text-good",
  likely_safe_review_required: "border-warn/50 bg-warn/15 text-warn",
  potential_substitute_insufficient_evidence: "border-fg-muted/40 bg-fg-muted/15 text-fg-muted",
  not_recommended: "border-bad/50 bg-bad/15 text-bad",
};

export function GradeBadge({
  grade,
  className,
}: {
  grade: Grade;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        STYLE[grade],
        className,
      )}
    >
      {LABEL[grade]}
    </span>
  );
}

const ASSESS_LABEL: Record<string, string> = {
  recommend: "Recommend",
  recommend_with_caveats: "Recommend · caveats",
  do_not_recommend: "Do not recommend",
  insufficient_evidence: "Insufficient evidence",
};

const ASSESS_STYLE: Record<string, string> = {
  recommend: "border-good/50 bg-good/15 text-good",
  recommend_with_caveats: "border-warn/50 bg-warn/15 text-warn",
  do_not_recommend: "border-bad/50 bg-bad/15 text-bad",
  insufficient_evidence: "border-fg-muted/40 bg-fg-muted/15 text-fg-muted",
};

export function AssessmentBadge({
  klass,
  className,
}: {
  klass: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        ASSESS_STYLE[klass] ?? "border-border bg-bg-muted text-fg-soft",
        className,
      )}
    >
      {ASSESS_LABEL[klass] ?? klass}
    </span>
  );
}

const POLARITY_STYLE: Record<string, string> = {
  supports: "border-good/50 bg-good/15 text-good",
  contradicts: "border-bad/50 bg-bad/15 text-bad",
  mixed: "border-warn/50 bg-warn/15 text-warn",
  unknown: "border-fg-muted/40 bg-fg-muted/15 text-fg-muted",
};

export function PolarityBadge({ polarity }: { polarity: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        POLARITY_STYLE[polarity] ?? "border-border bg-bg-muted text-fg-soft",
      )}
    >
      {polarity}
    </span>
  );
}
