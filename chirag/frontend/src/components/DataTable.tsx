"use client";

import { Fragment, ReactNode, useMemo, useState } from "react";

export type Column<T> = {
  key: string;
  header: string;
  accessor?: (row: T) => string | number | null | undefined;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right" | "center";
  width?: string;
  className?: string;
  headerClassName?: string;
};

export type SortDir = "asc" | "desc";

type Props<T> = {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, i: number) => string | number;
  searchKeys?: Array<(row: T) => string>;
  searchPlaceholder?: string;
  initialSort?: { key: string; dir: SortDir };
  emptyMessage?: string;
  toolbar?: ReactNode;
  density?: "compact" | "regular";
  expandable?: {
    render: (row: T) => ReactNode;
  };
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  searchKeys = [],
  searchPlaceholder = "Search…",
  initialSort,
  emptyMessage = "No rows match your filters.",
  toolbar,
  density = "regular",
  expandable,
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: SortDir } | null>(
    initialSort ?? null,
  );
  const [expanded, setExpanded] = useState<Set<string | number>>(new Set());

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const q = query.trim().toLowerCase();
    return rows.filter((r) =>
      searchKeys.some((fn) => (fn(r) ?? "").toLowerCase().includes(q)),
    );
  }, [rows, query, searchKeys]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.accessor) return filtered;
    const acc = col.accessor;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const va = acc(a);
      const vb = acc(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") {
        return sort.dir === "asc" ? va - vb : vb - va;
      }
      const sa = String(va).toLowerCase();
      const sb = String(vb).toLowerCase();
      if (sa < sb) return sort.dir === "asc" ? -1 : 1;
      if (sa > sb) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [filtered, sort, columns]);

  function toggleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "desc" };
      if (prev.dir === "desc") return { key, dir: "asc" };
      return null;
    });
  }

  function toggleExpanded(key: string | number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-2.5";
  const totalCols = columns.length + (expandable ? 1 : 0);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white px-3 py-2">
        <div className="relative min-w-[220px] flex-1">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <svg
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="7" />
            <path strokeLinecap="round" d="m20 20-3.5-3.5" />
          </svg>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="tabular-nums">
            {sorted.length.toLocaleString()}{" "}
            {sorted.length === 1 ? "row" : "rows"}
          </span>
          {sort && (
            <button
              type="button"
              onClick={() => setSort(null)}
              className="rounded border border-slate-200 bg-white px-2 py-0.5 font-medium hover:bg-slate-100"
            >
              Clear sort
            </button>
          )}
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="rounded border border-slate-200 bg-white px-2 py-0.5 font-medium hover:bg-slate-100"
            >
              Clear filter
            </button>
          )}
        </div>
        {toolbar && (
          <div className="flex items-center gap-2">{toolbar}</div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-white text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr className="border-b border-slate-200">
              {expandable && <th className="w-8" />}
              {columns.map((c) => {
                const isSorted = sort?.key === c.key;
                const alignCls =
                  c.align === "right"
                    ? "text-right"
                    : c.align === "center"
                      ? "text-center"
                      : "text-left";
                return (
                  <th
                    key={c.key}
                    className={`${cellPadding} ${alignCls} font-semibold ${c.headerClassName ?? ""}`}
                    style={c.width ? { width: c.width } : undefined}
                  >
                    {c.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-slate-900"
                      >
                        {c.header}
                        <span
                          className={
                            isSorted ? "text-indigo-500" : "text-slate-300"
                          }
                        >
                          {isSorted ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}
                        </span>
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={totalCols}
                  className="px-3 py-8 text-center text-sm text-slate-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sorted.map((row, i) => {
                const rk = rowKey(row, i);
                const isExpanded = expanded.has(rk);
                return (
                  <Fragment key={rk}>
                    <tr className="border-b border-slate-100 transition hover:bg-slate-50/70">
                      {expandable && (
                        <td className="w-8 px-2 text-center text-slate-400">
                          <button
                            type="button"
                            onClick={() => toggleExpanded(rk)}
                            aria-label={isExpanded ? "Collapse row" : "Expand row"}
                            className="inline-flex h-6 w-6 items-center justify-center rounded hover:bg-slate-100"
                          >
                            <span
                              className={`transition-transform ${isExpanded ? "rotate-90" : ""}`}
                            >
                              ›
                            </span>
                          </button>
                        </td>
                      )}
                      {columns.map((c) => {
                        const alignCls =
                          c.align === "right"
                            ? "text-right"
                            : c.align === "center"
                              ? "text-center"
                              : "text-left";
                        return (
                          <td
                            key={c.key}
                            className={`${cellPadding} ${alignCls} ${c.className ?? ""}`}
                          >
                            {c.render ? c.render(row) : (c.accessor?.(row) ?? "")}
                          </td>
                        );
                      })}
                    </tr>
                    {expandable && isExpanded && (
                      <tr className="border-b border-slate-100 bg-slate-50/70">
                        <td />
                        <td
                          colSpan={columns.length}
                          className="px-3 py-3 text-sm text-slate-700"
                        >
                          {expandable.render(row)}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
