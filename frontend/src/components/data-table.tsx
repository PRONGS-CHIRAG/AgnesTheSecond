"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type ColumnDef<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  sortBy?: (row: T) => string | number;
  width?: string;
  align?: "left" | "right" | "center";
  className?: string;
};

type SortDir = "asc" | "desc" | null;

export function DataTable<T>({
  columns,
  rows,
  initialSort,
  emptyMessage = "No rows.",
  maxHeight = "max-h-[520px]",
  rowKey,
  onRowClick,
}: {
  columns: ColumnDef<T>[];
  rows: T[];
  initialSort?: { key: string; dir: SortDir };
  emptyMessage?: string;
  maxHeight?: string;
  rowKey: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
}) {
  const [sortKey, setSortKey] = useState<string | null>(
    initialSort?.key ?? null,
  );
  const [sortDir, setSortDir] = useState<SortDir>(initialSort?.dir ?? null);

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col || !col.sortBy) return rows;
    const copy = rows.slice();
    const dirMul = sortDir === "asc" ? 1 : -1;
    copy.sort((a, b) => {
      const va = col.sortBy!(a);
      const vb = col.sortBy!(b);
      if (typeof va === "number" && typeof vb === "number") {
        return (va - vb) * dirMul;
      }
      return String(va).localeCompare(String(vb)) * dirMul;
    });
    return copy;
  }, [rows, sortKey, sortDir, columns]);

  const onHeaderClick = (col: ColumnDef<T>) => {
    if (!col.sortBy) return;
    if (sortKey !== col.key) {
      setSortKey(col.key);
      setSortDir("desc");
      return;
    }
    if (sortDir === "desc") {
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortKey(null);
      setSortDir(null);
    } else {
      setSortDir("desc");
    }
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className={cn("overflow-auto", maxHeight)}>
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-bg-card">
            <tr className="bg-bg-muted/70 text-left text-xs uppercase tracking-wide text-fg-muted">
              {columns.map((col) => {
                const active = sortKey === col.key && sortDir;
                const align =
                  col.align === "right"
                    ? "text-right"
                    : col.align === "center"
                      ? "text-center"
                      : "text-left";
                return (
                  <th
                    key={col.key}
                    className={cn(
                      "px-3 py-2 font-semibold",
                      align,
                      col.sortBy
                        ? "cursor-pointer select-none hover:text-fg"
                        : "",
                      col.className,
                    )}
                    style={col.width ? { width: col.width } : undefined}
                    onClick={() => onHeaderClick(col)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.header}
                      {col.sortBy ? (
                        active ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : (
                            <ArrowDown className="h-3 w-3" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        )
                      ) : null}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-sm text-fg-muted"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sorted.map((row, i) => (
                <tr
                  key={rowKey(row, i)}
                  className={cn(
                    "border-t border-border hover:bg-bg-muted/40",
                    onRowClick ? "cursor-pointer" : "",
                  )}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => {
                    const align =
                      col.align === "right"
                        ? "text-right"
                        : col.align === "center"
                          ? "text-center"
                          : "text-left";
                    return (
                      <td
                        key={col.key}
                        className={cn("px-3 py-2 align-top", align, col.className)}
                      >
                        {col.cell(row, i)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-border bg-bg-card px-3 py-1.5 text-[11px] text-fg-muted">
        <span>
          {sorted.length === rows.length
            ? `${sorted.length} row${sorted.length === 1 ? "" : "s"}`
            : `${sorted.length} of ${rows.length} rows`}
        </span>
        {sortKey ? (
          <span>
            sorted by {sortKey} {sortDir === "asc" ? "↑" : "↓"}
          </span>
        ) : null}
      </div>
    </div>
  );
}
