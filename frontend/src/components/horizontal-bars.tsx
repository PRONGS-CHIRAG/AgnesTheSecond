import { cn } from "@/lib/utils";
import { prettyKey } from "@/lib/utils";

export type BarRow = {
  key: string;
  label?: string;
  value: number;
};

/**
 * Horizontal bar chart (tailwind-only; no dependencies). Useful for
 * family/role distributions and confidence histograms.
 */
export function HorizontalBars({
  title,
  rows,
  tone = "accent",
  maxRows,
  className,
  valueFormatter,
  labelSuffix,
}: {
  title?: string;
  rows: BarRow[];
  tone?: "accent" | "good" | "warn" | "bad" | "muted";
  maxRows?: number;
  className?: string;
  valueFormatter?: (v: number) => string;
  labelSuffix?: (row: BarRow) => string | null;
}) {
  const toneBg =
    tone === "good"
      ? "bg-good/70"
      : tone === "warn"
        ? "bg-warn/70"
        : tone === "bad"
          ? "bg-bad/70"
          : tone === "muted"
            ? "bg-fg-muted/70"
            : "bg-accent/70";

  const sliced = maxRows ? rows.slice(0, maxRows) : rows;
  const max = sliced.reduce((a, r) => Math.max(a, r.value), 0);

  return (
    <div className={cn("card px-4 py-4", className)}>
      {title ? (
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-sm font-semibold text-fg">{title}</h3>
          {maxRows && rows.length > maxRows ? (
            <span className="text-xs text-fg-muted">
              top {maxRows} of {rows.length}
            </span>
          ) : null}
        </div>
      ) : null}
      {sliced.length === 0 ? (
        <div className="py-4 text-center text-sm text-fg-muted">No data.</div>
      ) : (
        <ul className="flex flex-col gap-2">
          {sliced.map((r) => {
            const pct = max === 0 ? 0 : (r.value / max) * 100;
            const suffix = labelSuffix?.(r);
            return (
              <li key={r.key} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="truncate text-fg-soft" title={r.label ?? r.key}>
                    {r.label ?? prettyKey(r.key)}
                    {suffix ? (
                      <span className="ml-1 text-fg-muted">{suffix}</span>
                    ) : null}
                  </span>
                  <span className="font-mono text-fg-muted">
                    {valueFormatter ? valueFormatter(r.value) : r.value}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-[width]", toneBg)}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
