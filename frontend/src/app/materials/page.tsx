"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Empty, ErrorState } from "@/components/empty";
import { Spinner } from "@/components/spinner";
import { formatScore } from "@/lib/utils";

const PAGE_SIZE = 50;

export default function MaterialsPage() {
  const [q, setQ] = useState("");
  const [family, setFamily] = useState("");
  const [role, setRole] = useState("");
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["registry", { q, family, role, offset }],
    queryFn: () =>
      api.registry({
        q: q || undefined,
        family: family || undefined,
        role: role || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    placeholderData: keepPreviousData,
  });

  const total = query.data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Canonical materials</h1>
        <p className="text-sm text-fg-muted">
          Paginated browse of every SKU after Phase 2 canonicalization.
        </p>
      </header>

      <div className="card grid grid-cols-1 gap-3 px-4 py-3 md:grid-cols-[1fr,auto,auto]">
        <label className="relative">
          <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-fg-muted" />
          <input
            placeholder="Search name / sku / canonical key…"
            className="input pl-8"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <select
          className="input md:w-48"
          value={family}
          onChange={(e) => {
            setFamily(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All families</option>
          {(query.data?.families ?? []).map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <select
          className="input md:w-48"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All roles</option>
          {(query.data?.roles ?? []).map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      {query.isLoading ? (
        <div className="card flex items-center justify-center px-4 py-10">
          <Spinner label="Loading materials…" />
        </div>
      ) : query.isError ? (
        <ErrorState
          title="Could not load registry."
          detail={(query.error as Error | undefined)?.message}
        />
      ) : total === 0 ? (
        <Empty
          title="No materials match."
          description="Try clearing filters or widen the search."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-bg-muted/60 text-left text-xs uppercase tracking-wide text-fg-muted">
                  <th className="px-4 py-2">Canonical key</th>
                  <th className="px-4 py-2">Family / role</th>
                  <th className="px-4 py-2">Company</th>
                  <th className="px-4 py-2">SKU</th>
                  <th className="px-4 py-2">Conf.</th>
                </tr>
              </thead>
              <tbody>
                {(query.data?.items ?? []).map((m) => (
                  <tr
                    key={`${m.raw_product_id}-${m.canonical_key}`}
                    className="border-t border-border hover:bg-bg-muted/40"
                  >
                    <td className="px-4 py-2">
                      <div className="font-mono text-xs">{m.canonical_key}</div>
                      <div className="text-xs text-fg-muted">
                        {m.normalized_name}
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <div>{m.ingredient_family}</div>
                      <div className="text-xs text-fg-muted">
                        {m.functional_role}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-fg-soft">
                      #{m.company_id}
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-fg-soft">
                      {m.sku}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {formatScore(m.confidence)}
                      {!m.parse_ok ? (
                        <div className="text-[10px] text-warn">parse fail</div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm">
            <div className="text-fg-muted">
              {total.toLocaleString()} materials · page {page} / {pages}
            </div>
            <div className="flex items-center gap-2">
              <button
                className="btn"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                <ChevronLeft className="h-4 w-4" />
                Prev
              </button>
              <button
                className="btn"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
