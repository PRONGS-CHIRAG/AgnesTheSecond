"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { PolarityBadge } from "@/components/grade-badge";
import { CitationChip } from "@/components/citation-chip";
import { ScoreBar } from "@/components/score-bar";
import type { EvidenceClaim } from "@/lib/schema";
import { cn, prettyKey } from "@/lib/utils";

export function ClaimCard({
  claim,
  className,
}: {
  claim: EvidenceClaim;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const top = claim.citations.slice(0, 3);
  const rest = claim.citations.slice(3);
  return (
    <div className={cn("card-muted px-3 py-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold capitalize">
          {prettyKey(claim.key)}
        </div>
        <div className="flex items-center gap-2">
          <PolarityBadge polarity={claim.polarity} />
          <span
            className={cn(
              "chip",
              claim.grounding_strength === "grounded"
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-fg-muted/40 bg-fg-muted/10 text-fg-muted",
            )}
          >
            {claim.grounding_strength}
          </span>
        </div>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-fg-soft">{claim.value}</p>
      <div className="mt-3 flex items-center gap-3">
        <ScoreBar
          value={claim.confidence}
          tone={
            claim.polarity === "contradicts"
              ? "bad"
              : claim.polarity === "mixed"
                ? "warn"
                : "accent"
          }
          className="w-32"
        />
        <span className="font-mono text-xs text-fg-muted">
          confidence {claim.confidence.toFixed(2)}
        </span>
      </div>
      {claim.citations.length > 0 ? (
        <div className="mt-3 flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {top.map((c, i) => (
              <CitationChip key={`${c.url}-${i}`} citation={c} />
            ))}
            {rest.length > 0 ? (
              <button
                onClick={() => setOpen((v) => !v)}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-muted/60 px-2 py-1 text-xs text-fg-muted transition-colors hover:text-fg"
              >
                {open ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                {open ? "Hide" : `+${rest.length} more`}
              </button>
            ) : null}
          </div>
          {open && rest.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {rest.map((c, i) => (
                <CitationChip key={`${c.url}-extra-${i}`} citation={c} />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
