"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { ArrowUpRight, Filter, Search } from "lucide-react";
import { Empty, ErrorState } from "@/components/empty";
import { GradeBadge } from "@/components/grade-badge";
import { ScoreBar } from "@/components/score-bar";
import { Spinner } from "@/components/spinner";
import { useDashboard } from "@/lib/useDashboard";
import type {
  ConsolidationOpportunity,
  Grade,
} from "@/lib/schema";
import { prettyKey } from "@/lib/utils";

const ALL_GRADES: Grade[] = [
  "safe_to_consolidate",
  "likely_safe_review_required",
  "potential_substitute_insufficient_evidence",
  "not_recommended",
];

type StatusFilter = "all" | "analyzed" | "not_analyzed" | Grade;
type SortKey =
  | "aggregate_final_score"
  | "aggregate_sourcing_benefit"
  | "n_products_covered"
  | "source_key";

type OpportunityRow =
  | { kind: "analyzed"; source_key: string; display_name: string; opp: ConsolidationOpportunity }
  | {
      kind: "unanalyzed";
      source_key: string;
      display_name: string;
      occurrences: number;
      family: string | null;
      role: string | null;
    };

export default function OpportunitiesPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("aggregate_final_score");
  const [picker, setPicker] = useState("");

  const { data, isLoading, isError, error } = useDashboard();

  const opportunities = data?.recommendations?.opportunities ?? [];
  const registry = data?.registry;

  /* Build the union of all source_keys: Phase 7 opportunities + registry canonical_keys. */
  const rows = useMemo<OpportunityRow[]>(() => {
    const byKey = new Map<string, OpportunityRow>();
    for (const opp of opportunities) {
      byKey.set(opp.source_key, {
        kind: "analyzed",
        source_key: opp.source_key,
        display_name: opp.source_display_name,
        opp,
      });
    }
    if (registry?.items?.length) {
      const countByKey = new Map<
        string,
        { display: string; family: string | null; role: string | null; count: number }
      >();
      for (const m of registry.items) {
        const cur = countByKey.get(m.canonical_key);
        if (cur) {
          cur.count += 1;
        } else {
          countByKey.set(m.canonical_key, {
            display: m.normalized_name ?? prettyKey(m.canonical_key),
            family: m.ingredient_family ?? null,
            role: m.functional_role ?? null,
            count: 1,
          });
        }
      }
      for (const [key, info] of countByKey) {
        if (byKey.has(key)) continue;
        byKey.set(key, {
          kind: "unanalyzed",
          source_key: key,
          display_name: info.display,
          occurrences: info.count,
          family: info.family,
          role: info.role,
        });
      }
    }
    return Array.from(byKey.values());
  }, [opportunities, registry]);

  const filtered = useMemo(() => {
    let out = rows;
    if (filter === "analyzed") {
      out = out.filter((r) => r.kind === "analyzed");
    } else if (filter === "not_analyzed") {
      out = out.filter((r) => r.kind === "unanalyzed");
    } else if (filter !== "all") {
      out = out.filter(
        (r) => r.kind === "analyzed" && r.opp.recommendation_grade === filter,
      );
    }
    const copy = [...out];
    copy.sort((a, b) => {
      if (sortKey === "source_key") {
        return a.source_key.localeCompare(b.source_key);
      }
      const av =
        a.kind === "analyzed"
          ? (a.opp[sortKey as keyof ConsolidationOpportunity] as number | undefined)
          : undefined;
      const bv =
        b.kind === "analyzed"
          ? (b.opp[sortKey as keyof ConsolidationOpportunity] as number | undefined)
          : undefined;
      if (av == null && bv == null) return a.source_key.localeCompare(b.source_key);
      if (av == null) return 1;
      if (bv == null) return -1;
      return Number(bv) - Number(av);
    });
    return copy;
  }, [rows, filter, sortKey]);

  const totals = useMemo(() => {
    let analyzed = 0;
    let unanalyzed = 0;
    for (const r of rows) {
      if (r.kind === "analyzed") analyzed += 1;
      else unanalyzed += 1;
    }
    return { analyzed, unanalyzed, total: rows.length };
  }, [rows]);

  const datalistId = "source-key-options";

  const onPickerSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const key = picker.trim();
    if (!key) return;
    router.push(`/opportunities/${encodeURIComponent(key)}`);
  };

  const pickerKeys = useMemo(
    () =>
      rows
        .map((r) => ({ key: r.source_key, name: r.display_name }))
        .sort((a, b) => a.key.localeCompare(b.key)),
    [rows],
  );

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Consolidation opportunities</h1>
        <p className="text-sm text-fg-muted">
          Every canonical raw material appears as a potential{" "}
          <code>source_key</code>. Analyzed rows show Phase 7 scores; unanalyzed
          rows can be queued for a run.
        </p>
      </header>

      {/* Source-key selector */}
      <form
        onSubmit={onPickerSubmit}
        className="card flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-end"
      >
        <div className="flex-1">
          <label
            htmlFor="source-key-input"
            className="mb-1 block text-[11px] uppercase tracking-wide text-fg-muted"
          >
            Select a source key
            <span className="ml-2 text-fg-soft">
              ({pickerKeys.length} available)
            </span>
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
            <input
              id="source-key-input"
              className="input pl-8"
              list={datalistId}
              placeholder="e.g. calcium-citrate"
              value={picker}
              onChange={(e) => setPicker(e.target.value)}
              autoComplete="off"
            />
            <datalist id={datalistId}>
              {pickerKeys.map((k) => (
                <option key={k.key} value={k.key}>
                  {k.name}
                </option>
              ))}
            </datalist>
          </div>
        </div>
        <button
          type="submit"
          className="btn-primary h-[38px] self-end sm:self-auto"
          disabled={!picker.trim()}
        >
          Open <ArrowUpRight className="h-4 w-4" />
        </button>
      </form>

      {/* Filter chips + sort */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-fg-muted">
          <Filter className="h-4 w-4" />
          Status
        </div>
        <div className="flex flex-wrap gap-1">
          <GradeChip
            active={filter === "all"}
            onClick={() => setFilter("all")}
            label={`All (${totals.total})`}
          />
          <GradeChip
            active={filter === "analyzed"}
            onClick={() => setFilter("analyzed")}
            label={`Analyzed (${totals.analyzed})`}
          />
          <GradeChip
            active={filter === "not_analyzed"}
            onClick={() => setFilter("not_analyzed")}
            label={`Not analyzed (${totals.unanalyzed})`}
          />
          {ALL_GRADES.map((g) => (
            <GradeChip
              key={g}
              active={filter === g}
              onClick={() => setFilter(g)}
              label={prettyKey(g)}
            />
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <span className="text-fg-muted">Sort</span>
          <select
            className="input w-auto"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            <option value="aggregate_final_score">Final score</option>
            <option value="aggregate_sourcing_benefit">Sourcing benefit</option>
            <option value="n_products_covered">Products covered</option>
            <option value="source_key">Source key (A–Z)</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="card flex items-center justify-center px-4 py-10">
          <Spinner label="Loading opportunities…" />
        </div>
      ) : isError ? (
        <ErrorState
          title="Could not load opportunities."
          detail={(error as Error | undefined)?.message}
        />
      ) : filtered.length === 0 ? (
        <Empty
          title="No opportunities match."
          description="Clear the filters or run Phase 2 to populate the registry."
          action={
            <Link className="btn" href="/runs">
              Runs console
            </Link>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                <th className="px-4 py-2">Source → Best candidate</th>
                <th className="px-4 py-2">Grade</th>
                <th className="px-4 py-2">Final</th>
                <th className="px-4 py-2">Sourcing</th>
                <th className="px-4 py-2">Coverage</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) =>
                r.kind === "analyzed" ? (
                  <tr
                    key={r.source_key}
                    className="border-t border-border hover:bg-bg-muted/40"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium">{r.opp.source_display_name}</div>
                      <div className="text-xs text-fg-muted">
                        → {r.opp.best_candidate_display_name}
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] text-fg-muted">
                        {r.source_key}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <GradeBadge grade={r.opp.recommendation_grade} />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar
                        value={r.opp.aggregate_final_score}
                        tone="accent"
                        className="w-32"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar
                        value={r.opp.aggregate_sourcing_benefit}
                        tone="good"
                        className="w-32"
                      />
                    </td>
                    <td className="px-4 py-3 text-xs text-fg-soft">
                      {r.opp.n_products_covered} products ·{" "}
                      {r.opp.n_companies_covered} companies
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        className="btn-ghost"
                        href={`/opportunities/${encodeURIComponent(r.source_key)}`}
                      >
                        Open <ArrowUpRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ) : (
                  <tr
                    key={r.source_key}
                    className="border-t border-border hover:bg-bg-muted/40"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium">{r.display_name}</div>
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {r.family ? (
                          <span className="chip text-[10px]">
                            {prettyKey(r.family)}
                          </span>
                        ) : null}
                        {r.role ? (
                          <span className="chip border-accent/40 bg-accent/10 text-[10px] text-accent">
                            {prettyKey(r.role)}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] text-fg-muted">
                        {r.source_key}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="chip border-warn/40 bg-warn/10 text-warn">
                        not analyzed
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-fg-muted">—</td>
                    <td className="px-4 py-3 text-xs text-fg-muted">—</td>
                    <td className="px-4 py-3 text-xs text-fg-soft">
                      {r.occurrences} material{r.occurrences === 1 ? "" : "s"} in registry
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        className="btn-ghost"
                        href={`/opportunities/${encodeURIComponent(r.source_key)}`}
                      >
                        Open <ArrowUpRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function GradeChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "rounded-full border px-3 py-1 text-xs transition-colors " +
        (active
          ? "border-accent bg-accent/20 text-accent"
          : "border-border bg-bg-muted text-fg-muted hover:text-fg")
      }
    >
      {label}
    </button>
  );
}
