"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatCard, StatAccent } from "@/components/StatCard";
import { fetchJSON } from "@/lib/api";
import { usdCompact } from "@/lib/format";
import {
  ProcurementOverview,
  ProcurementOverviewSchema,
  SavingsReport,
  SavingsReportSchema,
} from "@/lib/schemas/procurement";
import {
  SupplyRiskReport,
  SupplyRiskReportSchema,
} from "@/lib/schemas/risks";

type Stats = {
  overview: ProcurementOverview | null;
  savings: SavingsReport | null;
  risks: SupplyRiskReport | null;
};

export default function HomePage() {
  const [stats, setStats] = useState<Stats>({
    overview: null,
    savings: null,
    risks: null,
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchJSON("/api/procurement/overview", ProcurementOverviewSchema).catch(
        () => null,
      ),
      fetchJSON("/api/procurement/savings", SavingsReportSchema).catch(
        () => null,
      ),
      fetchJSON("/api/risks", SupplyRiskReportSchema).catch(() => null),
    ])
      .then(([overview, savings, risks]) => {
        if (!cancelled) setStats({ overview, savings, risks });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load stats.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-10">
      <header className="mb-10">
        <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />
          Hackathon MVP · Phases 0–7 online
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          Your supply chain, with{" "}
          <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 bg-clip-text text-transparent">
            receipts
          </span>
          .
        </h1>
        <p className="mt-3 max-w-2xl text-slate-600">
          Agnes 2 finds substitutions, flags risks, and surfaces sourcing savings
          — grounded in your PO history, supplier records, and a 7-phase
          evidence pipeline.
        </p>
      </header>

      <section className="mb-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total spend"
          value={stats.overview ? usdCompact(stats.overview.total_spend) : "—"}
          sublabel={
            stats.overview
              ? `${stats.overview.n_orders.toLocaleString()} orders`
              : "loading…"
          }
          accent="indigo"
          icon="$"
        />
        <StatCard
          label="Suppliers"
          value={stats.overview?.n_suppliers ?? "—"}
          sublabel={
            stats.overview
              ? `${stats.overview.on_time_rate.toFixed(1)}% on-time`
              : "loading…"
          }
          accent="violet"
          icon="⊛"
        />
        <StatCard
          label="Est. savings"
          value={
            stats.savings
              ? usdCompact(stats.savings.total_estimated_savings_usd)
              : "—"
          }
          sublabel={
            stats.savings
              ? `${stats.savings.n_opportunities} opportunities`
              : "loading…"
          }
          accent="emerald"
          icon="↓"
        />
        <StatCard
          label="Open risks"
          value={stats.risks?.n_total ?? "—"}
          sublabel={
            stats.risks
              ? `${stats.risks.by_severity["high"] ?? 0} high · ${
                  stats.risks.by_severity["medium"] ?? 0
                } med`
              : "loading…"
          }
          accent={
            (stats.risks?.by_severity["high"] ?? 0) > 0 ? "rose" : "amber"
          }
          icon="△"
        />
      </section>

      {error && (
        <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NavCard
          href="/chat"
          title="Chat with Agnes 2"
          description="Ask in plain English. Agnes 2 plans, calls tools, and returns grounded answers — every step is auditable."
          accent="indigo"
          badge="LLM + 6 tools"
          icon="💬"
        />
        <NavCard
          href="/procurement"
          title="Procurement dashboard"
          description="Spend, savings, and supplier scorecards — all sortable, filterable, and quantified."
          accent="emerald"
          badge="Phase 7 + PO data"
          icon="📊"
        />
        <NavCard
          href="/risks"
          title="Supply risk register"
          description="Single-source, concentration, criticality, quality, and price-volatility signals with clear next actions."
          accent="rose"
          badge="Phase 6.5"
          icon="⚠"
        />
      </section>

      <section className="mt-12">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Inspect the API directly
        </h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {[
            { href: "/api/health", label: "GET /api/health" },
            { href: "/api/summary", label: "GET /api/summary" },
            {
              href: "/api/procurement/savings",
              label: "GET /api/procurement/savings",
            },
            { href: "/api/risks", label: "GET /api/risks" },
          ].map((l) => (
            <li key={l.href}>
              <a
                href={l.href}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow"
              >
                <span className="font-mono text-slate-800">{l.label}</span>
                <span className="text-slate-400">↗</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

const ACCENT_STYLES: Record<
  StatAccent,
  { bar: string; badge: string; dot: string }
> = {
  indigo: {
    bar: "from-indigo-500 via-violet-500 to-fuchsia-500",
    badge: "border-indigo-200 bg-indigo-50 text-indigo-700",
    dot: "bg-indigo-500",
  },
  emerald: {
    bar: "from-emerald-500 to-teal-500",
    badge: "border-emerald-200 bg-emerald-50 text-emerald-700",
    dot: "bg-emerald-500",
  },
  rose: {
    bar: "from-rose-500 to-pink-500",
    badge: "border-rose-200 bg-rose-50 text-rose-700",
    dot: "bg-rose-500",
  },
  amber: {
    bar: "from-amber-500 to-orange-500",
    badge: "border-amber-200 bg-amber-50 text-amber-700",
    dot: "bg-amber-500",
  },
  violet: {
    bar: "from-violet-500 to-fuchsia-500",
    badge: "border-violet-200 bg-violet-50 text-violet-700",
    dot: "bg-violet-500",
  },
  slate: {
    bar: "from-slate-500 to-slate-700",
    badge: "border-slate-200 bg-slate-50 text-slate-700",
    dot: "bg-slate-500",
  },
  sky: {
    bar: "from-sky-500 to-blue-500",
    badge: "border-sky-200 bg-sky-50 text-sky-700",
    dot: "bg-sky-500",
  },
};

function NavCard({
  href,
  title,
  description,
  badge,
  accent,
  icon,
}: {
  href: string;
  title: string;
  description: string;
  badge?: string;
  accent: StatAccent;
  icon?: string;
}) {
  const s = ACCENT_STYLES[accent];
  return (
    <Link
      href={href}
      className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
    >
      <div
        className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${s.bar}`}
      />
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {icon && (
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-base">
              {icon}
            </span>
          )}
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        </div>
        {badge && (
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${s.badge}`}
          >
            {badge}
          </span>
        )}
      </div>
      <p className="text-sm leading-relaxed text-slate-600">{description}</p>
      <span className="mt-auto flex items-center gap-1 pt-4 text-sm font-medium text-slate-700 group-hover:text-slate-900">
        Open
        <span className="transition group-hover:translate-x-0.5">→</span>
      </span>
    </Link>
  );
}
