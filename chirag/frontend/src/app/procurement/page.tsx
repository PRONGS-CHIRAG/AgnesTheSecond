"use client";

import { useEffect, useState } from "react";

import { Badge, BadgeTone } from "@/components/Badge";
import { Column, DataTable } from "@/components/DataTable";
import { ProgressBar, scoreTone } from "@/components/ProgressBar";
import { StatCard } from "@/components/StatCard";
import { fetchJSON } from "@/lib/api";
import { usd, usdCompact } from "@/lib/format";
import {
  ProcurementOverview,
  ProcurementOverviewSchema,
  SavingsOpportunity,
  SavingsReport,
  SavingsReportSchema,
  SupplierSummary,
  SuppliersReport,
  SuppliersReportSchema,
  TopIngredient,
  TopSupplier,
} from "@/lib/schemas/procurement";

type Tab = "overview" | "savings" | "suppliers";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "savings", label: "Cost savings", icon: "↓" },
  { id: "suppliers", label: "Suppliers", icon: "⊛" },
];

function onTimeTone(v: number) {
  if (v >= 90) return "emerald" as const;
  if (v >= 75) return "amber" as const;
  return "rose" as const;
}

export default function ProcurementPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<ProcurementOverview | null>(null);
  const [savings, setSavings] = useState<SavingsReport | null>(null);
  const [suppliers, setSuppliers] = useState<SuppliersReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchJSON("/api/procurement/overview", ProcurementOverviewSchema),
      fetchJSON("/api/procurement/savings", SavingsReportSchema),
      fetchJSON("/api/procurement/suppliers", SuppliersReportSchema),
    ])
      .then(([o, s, sup]) => {
        if (cancelled) return;
        setOverview(o);
        setSavings(s);
        setSuppliers(sup);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          (err as Error)?.message ||
            "Failed to load procurement data. Is the backend running?",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const partial =
    overview?.partial || savings?.partial || suppliers?.partial || false;

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Procurement
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Spend, savings, and supplier scorecards derived from your PO history.
        </p>
      </header>

      {partial && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <span>⚠</span>
          <span>
            Procurement tables are missing. Run{" "}
            <code className="rounded bg-amber-100 px-1 font-mono">
              uv run python scripts/seed_procurement_mock.py --apply
            </code>{" "}
            to populate them.
          </span>
        </div>
      )}

      <nav className="mb-6 flex w-fit gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm font-medium transition ${
              tab === t.id
                ? "bg-slate-900 text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>

      {loading && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
          Loading…
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {tab === "overview" && overview && (
            <OverviewTab overview={overview} />
          )}
          {tab === "savings" && savings && <SavingsTab savings={savings} />}
          {tab === "suppliers" && suppliers && (
            <SuppliersTab suppliers={suppliers} />
          )}
        </>
      )}
    </main>
  );
}

function OverviewTab({ overview }: { overview: ProcurementOverview }) {
  const supplierCols: Column<TopSupplier>[] = [
    {
      key: "supplier_name",
      header: "Supplier",
      accessor: (r) => r.supplier_name,
      sortable: true,
      render: (r) => (
        <span className="font-medium text-slate-800">{r.supplier_name}</span>
      ),
    },
    {
      key: "total_spend",
      header: "Spend",
      accessor: (r) => r.total_spend,
      sortable: true,
      align: "right",
      render: (r) => (
        <span className="font-mono text-slate-800">
          {usdCompact(r.total_spend)}
        </span>
      ),
    },
    {
      key: "n_orders",
      header: "Orders",
      accessor: (r) => r.n_orders,
      sortable: true,
      align: "right",
      render: (r) => (
        <span className="tabular-nums text-slate-700">
          {r.n_orders.toLocaleString()}
        </span>
      ),
    },
    {
      key: "on_time_rate",
      header: "On-time",
      accessor: (r) => r.on_time_rate,
      sortable: true,
      align: "right",
      render: (r) => (
        <ProgressBar value={r.on_time_rate} tone={onTimeTone(r.on_time_rate)} />
      ),
    },
  ];

  const ingredientCols: Column<TopIngredient>[] = [
    {
      key: "display_name",
      header: "Ingredient",
      accessor: (r) => r.display_name,
      sortable: true,
      render: (r) => (
        <span className="font-medium text-slate-800">{r.display_name}</span>
      ),
    },
    {
      key: "total_spend",
      header: "Spend",
      accessor: (r) => r.total_spend,
      sortable: true,
      align: "right",
      render: (r) => (
        <span className="font-mono text-slate-800">
          {usdCompact(r.total_spend)}
        </span>
      ),
    },
    {
      key: "n_orders",
      header: "Orders",
      accessor: (r) => r.n_orders,
      sortable: true,
      align: "right",
    },
    {
      key: "n_suppliers",
      header: "Suppliers",
      accessor: (r) => r.n_suppliers,
      sortable: true,
      align: "right",
      render: (r) =>
        r.n_suppliers === 1 ? (
          <Badge tone="danger">1 (single)</Badge>
        ) : (
          <span className="tabular-nums text-slate-700">{r.n_suppliers}</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard
          label="Total spend"
          value={usdCompact(overview.total_spend)}
          sublabel={`${overview.n_orders.toLocaleString()} orders`}
          accent="indigo"
          icon="$"
        />
        <StatCard
          label="Orders"
          value={overview.n_orders.toLocaleString()}
          accent="violet"
          icon="▦"
        />
        <StatCard
          label="Suppliers"
          value={overview.n_suppliers}
          accent="sky"
          icon="⊛"
        />
        <StatCard
          label="Ingredients"
          value={overview.n_ingredients}
          accent="amber"
          icon="▾"
        />
        <StatCard
          label="On-time"
          value={`${overview.on_time_rate.toFixed(1)}%`}
          accent={overview.on_time_rate >= 90 ? "emerald" : "amber"}
          icon="✓"
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-slate-700">
            Top suppliers by spend
          </h2>
          <DataTable<TopSupplier>
            columns={supplierCols}
            rows={overview.top_suppliers}
            rowKey={(r) => r.supplier_id}
            searchKeys={[(r) => r.supplier_name]}
            initialSort={{ key: "total_spend", dir: "desc" }}
            searchPlaceholder="Search suppliers…"
          />
        </section>
        <section>
          <h2 className="mb-2 text-sm font-semibold text-slate-700">
            Top ingredients by spend
          </h2>
          <DataTable<TopIngredient>
            columns={ingredientCols}
            rows={overview.top_ingredients}
            rowKey={(r) => r.base_name}
            searchKeys={[(r) => r.display_name]}
            initialSort={{ key: "total_spend", dir: "desc" }}
            searchPlaceholder="Search ingredients…"
          />
        </section>
      </div>
    </div>
  );
}

function SavingsTab({ savings }: { savings: SavingsReport }) {
  const cols: Column<SavingsOpportunity>[] = [
    {
      key: "display_name",
      header: "Ingredient",
      accessor: (r) => r.display_name,
      sortable: true,
      render: (r) => (
        <div>
          <div className="font-medium text-slate-800">{r.display_name}</div>
          <div className="mt-0.5 text-xs text-slate-500">
            Best: {r.best_supplier_name ?? "—"}
            {r.best_supplier_price !== null
              ? ` · $${r.best_supplier_price.toFixed(2)}`
              : ""}
          </div>
        </div>
      ),
    },
    {
      key: "spread_pct",
      header: "Spread",
      accessor: (r) => r.spread_pct,
      sortable: true,
      align: "right",
      render: (r) => (
        <Badge
          tone={
            r.spread_pct >= 25
              ? "danger"
              : r.spread_pct >= 15
                ? "warning"
                : "neutral"
          }
        >
          {r.spread_pct.toFixed(1)}%
        </Badge>
      ),
    },
    {
      key: "estimated_savings_usd",
      header: "Est. savings",
      accessor: (r) => r.estimated_savings_usd,
      sortable: true,
      align: "right",
      render: (r) => (
        <span className="font-mono font-semibold text-emerald-700">
          {usd(r.estimated_savings_usd)}
        </span>
      ),
    },
    {
      key: "signal",
      header: "Signal",
      accessor: (r) => r.signal,
      sortable: true,
      align: "right",
      render: (r) => (
        <ProgressBar
          value={r.signal * 100}
          tone="indigo"
          showValue={false}
          width="w-14"
        />
      ),
    },
    {
      key: "meets_gates",
      header: "Gates",
      accessor: (r) => (r.meets_gates ? 1 : 0),
      sortable: true,
      render: (r) =>
        r.meets_gates ? (
          <Badge tone="success">Passes</Badge>
        ) : (
          <Badge tone="neutral">Below threshold</Badge>
        ),
    },
  ];

  if (savings.opportunities.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
        No qualifying cost-savings opportunities detected. Signals require a
        ≥15% price spread with the cheapest supplier passing both quality and
        compliance gates.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <StatCard
          label="Total est. savings"
          value={usdCompact(savings.total_estimated_savings_usd)}
          accent="emerald"
          icon="↓"
        />
        <StatCard
          label="Opportunities"
          value={savings.n_opportunities}
          accent="indigo"
          icon="◎"
        />
        <StatCard
          label="Ingredients evaluated"
          value={savings.n_ingredients_evaluated}
          accent="violet"
          icon="▾"
        />
      </div>

      <DataTable<SavingsOpportunity>
        columns={cols}
        rows={savings.opportunities}
        rowKey={(r) => r.base_name}
        searchKeys={[
          (r) => r.display_name,
          (r) => r.best_supplier_name ?? "",
        ]}
        initialSort={{ key: "estimated_savings_usd", dir: "desc" }}
        searchPlaceholder="Search by ingredient or supplier…"
        expandable={{
          render: (r) =>
            r.evidence.length > 0 ? (
              <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
                {r.evidence.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-slate-500">
                No evidence entries listed for this opportunity.
              </div>
            ),
        }}
      />
    </div>
  );
}

function SuppliersTab({ suppliers }: { suppliers: SuppliersReport }) {
  const cols: Column<SupplierSummary>[] = [
    {
      key: "supplier_name",
      header: "Supplier",
      accessor: (r) => r.supplier_name,
      sortable: true,
      render: (r) => (
        <div>
          <div className="font-medium text-slate-800">{r.supplier_name}</div>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {r.certifications.length > 0 ? (
              r.certifications.map((c) => (
                <Badge key={c} tone="violet">
                  {c}
                </Badge>
              ))
            ) : (
              <span className="text-xs text-slate-400">
                no certifications
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "total_spend",
      header: "Spend",
      accessor: (r) => r.total_spend,
      sortable: true,
      align: "right",
      render: (r) => (
        <span className="font-mono text-slate-800">
          {usdCompact(r.total_spend)}
        </span>
      ),
    },
    {
      key: "n_orders",
      header: "Orders",
      accessor: (r) => r.n_orders,
      sortable: true,
      align: "right",
    },
    {
      key: "n_ingredients",
      header: "SKUs",
      accessor: (r) => r.n_ingredients,
      sortable: true,
      align: "right",
    },
    {
      key: "on_time_rate",
      header: "On-time",
      accessor: (r) => r.on_time_rate,
      sortable: true,
      align: "right",
      render: (r) => (
        <ProgressBar value={r.on_time_rate} tone={onTimeTone(r.on_time_rate)} />
      ),
    },
    {
      key: "quality_score",
      header: "Quality",
      accessor: (r) => r.quality_score ?? -1,
      sortable: true,
      align: "right",
      render: (r) =>
        r.quality_score !== null ? (
          <ProgressBar
            value={r.quality_score}
            tone={scoreTone(r.quality_score)}
          />
        ) : (
          <span className="text-slate-400">—</span>
        ),
    },
    {
      key: "compliance_score",
      header: "Compliance",
      accessor: (r) => r.compliance_score ?? -1,
      sortable: true,
      align: "right",
      render: (r) =>
        r.compliance_score !== null ? (
          <ProgressBar
            value={r.compliance_score}
            tone={scoreTone(r.compliance_score)}
          />
        ) : (
          <span className="text-slate-400">—</span>
        ),
    },
    {
      key: "lead_time_days",
      header: "Lead",
      accessor: (r) => r.lead_time_days ?? -1,
      sortable: true,
      align: "right",
      render: (r) =>
        r.lead_time_days !== null ? (
          <span className="tabular-nums text-slate-700">
            {r.lead_time_days}d
          </span>
        ) : (
          <span className="text-slate-400">—</span>
        ),
    },
    {
      key: "risk_tier",
      header: "Risk",
      accessor: (r) => r.risk_tier ?? "",
      sortable: true,
      render: (r) => {
        if (!r.risk_tier) return <span className="text-slate-400">—</span>;
        const tone: BadgeTone =
          r.risk_tier === "high"
            ? "danger"
            : r.risk_tier === "medium"
              ? "warning"
              : "success";
        return <Badge tone={tone}>{r.risk_tier}</Badge>;
      },
    },
  ];

  return (
    <DataTable<SupplierSummary>
      columns={cols}
      rows={suppliers.suppliers}
      rowKey={(r) => r.supplier_id}
      searchKeys={[
        (r) => r.supplier_name,
        (r) => r.certifications.join(" "),
      ]}
      initialSort={{ key: "total_spend", dir: "desc" }}
      searchPlaceholder="Search suppliers or certifications…"
    />
  );
}
