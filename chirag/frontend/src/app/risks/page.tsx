"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/Badge";
import { Column, DataTable } from "@/components/DataTable";
import { ProgressBar } from "@/components/ProgressBar";
import { StatCard } from "@/components/StatCard";
import { fetchJSON } from "@/lib/api";
import {
  RiskItem,
  RiskSeverity,
  RiskType,
  SupplyRiskReport,
  SupplyRiskReportSchema,
} from "@/lib/schemas/risks";

const TYPE_LABELS: Record<RiskType, string> = {
  single_source: "Single source",
  supplier_concentration: "Supplier concentration",
  critical_ingredient: "Critical ingredient",
  supplier_quality: "Supplier quality",
  price_volatility: "Price volatility",
};

const TYPE_ICONS: Record<RiskType, string> = {
  single_source: "⊙",
  supplier_concentration: "▦",
  critical_ingredient: "★",
  supplier_quality: "✗",
  price_volatility: "~",
};

const SEVERITY_ORDER: Record<RiskSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

type ApiError = { error: string; artifact?: string };

export default function RisksPage() {
  const [report, setReport] = useState<SupplyRiskReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<"all" | RiskSeverity>(
    "all",
  );
  const [typeFilter, setTypeFilter] = useState<"all" | RiskType>("all");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchJSON("/api/risks", SupplyRiskReportSchema)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const apiErr = err as { detail?: ApiError };
        if (apiErr?.detail?.error === "artifact_missing") {
          setError(
            "Phase 6.5 has not been run yet. Run `uv run python scripts/phase6_5_risks.py`.",
          );
        } else {
          setError(
            err instanceof Error ? err.message : "Failed to load supply risks.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo<RiskItem[]>(() => {
    if (!report) return [];
    return report.items
      .filter((r) => severityFilter === "all" || r.severity === severityFilter)
      .filter((r) => typeFilter === "all" || r.type === typeFilter);
  }, [report, severityFilter, typeFilter]);

  const cols: Column<RiskItem>[] = useMemo(
    () => [
      {
        key: "severity",
        header: "Severity",
        accessor: (r) => -SEVERITY_ORDER[r.severity],
        sortable: true,
        render: (r) => (
          <Badge
            tone={
              r.severity === "high"
                ? "danger"
                : r.severity === "medium"
                  ? "warning"
                  : "neutral"
            }
          >
            {r.severity.toUpperCase()}
          </Badge>
        ),
      },
      {
        key: "type",
        header: "Type",
        accessor: (r) => TYPE_LABELS[r.type],
        sortable: true,
        render: (r) => (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-700">
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-md bg-slate-100 text-slate-600">
              {TYPE_ICONS[r.type]}
            </span>
            {TYPE_LABELS[r.type]}
          </span>
        ),
      },
      {
        key: "label",
        header: "Risk",
        accessor: (r) => r.label,
        sortable: true,
        render: (r) => (
          <div>
            <div className="font-medium text-slate-800">{r.label}</div>
            <div className="mt-0.5 line-clamp-1 text-xs text-slate-500">
              {r.description}
            </div>
          </div>
        ),
      },
      {
        key: "score",
        header: "Score",
        accessor: (r) => r.score,
        sortable: true,
        align: "right",
        render: (r) => (
          <ProgressBar
            value={r.score * 100}
            tone={
              r.severity === "high"
                ? "rose"
                : r.severity === "medium"
                  ? "amber"
                  : "indigo"
            }
            width="w-16"
          />
        ),
      },
      {
        key: "n_companies_affected",
        header: "Cos.",
        accessor: (r) => r.n_companies_affected,
        sortable: true,
        align: "right",
        render: (r) => (
          <span className="tabular-nums text-slate-700">
            {r.n_companies_affected}
          </span>
        ),
      },
      {
        key: "n_products_affected",
        header: "Products",
        accessor: (r) => r.n_products_affected,
        sortable: true,
        align: "right",
        render: (r) => (
          <span className="tabular-nums text-slate-700">
            {r.n_products_affected}
          </span>
        ),
      },
      {
        key: "n_suppliers",
        header: "Suppliers",
        accessor: (r) => r.n_suppliers,
        sortable: true,
        align: "right",
        render: (r) => (
          <span className="tabular-nums text-slate-700">
            {r.n_suppliers}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Supply risks
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Deterministic risk register across single-source, concentration,
          criticality, supplier quality, and price-volatility signals.
        </p>
      </header>

      {loading && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
          Loading supply risks…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {error}
        </div>
      )}

      {report && !error && (
        <div className="space-y-6">
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total risks"
              value={report.n_total}
              accent="slate"
              icon="△"
            />
            <StatCard
              label="High severity"
              value={report.by_severity["high"] ?? 0}
              accent="rose"
              icon="!"
            />
            <StatCard
              label="Medium severity"
              value={report.by_severity["medium"] ?? 0}
              accent="amber"
              icon="·"
            />
            <StatCard
              label="Taxonomy / schema"
              value={`${report.taxonomy_version}`}
              sublabel={`schema ${report.schema_version}`}
              accent="violet"
              icon="#"
            />
          </section>

          <section className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Severity
              </span>
              <SegmentedControl
                value={severityFilter}
                onChange={(v) => setSeverityFilter(v as "all" | RiskSeverity)}
                options={[
                  { id: "all", label: "All" },
                  { id: "high", label: "High", tone: "rose" },
                  { id: "medium", label: "Medium", tone: "amber" },
                  { id: "low", label: "Low", tone: "slate" },
                ]}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Type
              </span>
              <SegmentedControl
                value={typeFilter}
                onChange={(v) => setTypeFilter(v as "all" | RiskType)}
                options={[
                  { id: "all", label: "All" },
                  ...(Object.entries(TYPE_LABELS) as [RiskType, string][]).map(
                    ([id, label]) => ({ id, label }),
                  ),
                ]}
              />
            </div>
            <span className="ml-auto text-xs text-slate-500">
              {filtered.length} of {report.n_total} risks shown
            </span>
          </section>

          <DataTable<RiskItem>
            columns={cols}
            rows={filtered}
            rowKey={(r) => `${r.type}:${r.key}`}
            searchKeys={[
              (r) => r.label,
              (r) => r.description,
              (r) => r.recommendation,
              (r) => TYPE_LABELS[r.type],
            ]}
            initialSort={{ key: "score", dir: "desc" }}
            searchPlaceholder="Search risks, labels, or recommendations…"
            expandable={{
              render: (r) => (
                <div className="space-y-2">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Description
                    </div>
                    <p className="mt-0.5 text-sm text-slate-700">
                      {r.description}
                    </p>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Recommendation
                    </div>
                    <p className="mt-0.5 text-sm text-slate-700">
                      {r.recommendation}
                    </p>
                  </div>
                  {r.evidence.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Evidence
                      </div>
                      <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-xs text-slate-600">
                        {r.evidence.slice(0, 8).map((e, i) => (
                          <li key={i}>{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ),
            }}
          />
        </div>
      )}
    </main>
  );
}

type SegmentOption = {
  id: string;
  label: string;
  tone?: "rose" | "amber" | "slate";
};

function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: SegmentOption[];
}) {
  return (
    <div className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-0.5">
      {options.map((o) => {
        const active = value === o.id;
        const activeTone =
          o.tone === "rose"
            ? "bg-rose-600 text-white"
            : o.tone === "amber"
              ? "bg-amber-500 text-white"
              : "bg-slate-900 text-white";
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              active ? activeTone : "text-slate-600 hover:bg-white"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
