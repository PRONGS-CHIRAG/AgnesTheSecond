import { cn } from "@/lib/utils";

export type DonutSlice = {
  key: string;
  label: string;
  value: number;
  /** Optional tone override (picks stroke + legend-dot color). */
  tone?: "good" | "accent" | "warn" | "bad" | "muted";
};

const TONE_ORDER: Array<NonNullable<DonutSlice["tone"]>> = [
  "good",
  "accent",
  "warn",
  "bad",
  "muted",
];

// Explicitly listed so Tailwind's JIT keeps these classes.
const STROKE_BY_TONE: Record<NonNullable<DonutSlice["tone"]>, string> = {
  good: "stroke-good",
  accent: "stroke-accent",
  warn: "stroke-warn",
  bad: "stroke-bad",
  muted: "stroke-fg-muted",
};
const DOT_BY_TONE: Record<NonNullable<DonutSlice["tone"]>, string> = {
  good: "bg-good",
  accent: "bg-accent",
  warn: "bg-warn",
  bad: "bg-bad",
  muted: "bg-fg-muted",
};

/**
 * Lightweight SVG donut chart. No external dependencies; colors come from the
 * tailwind tone palette so dark mode is automatic.
 */
export function Donut({
  slices,
  size = 160,
  thickness = 16,
  centerLabel,
  centerValue,
  className,
}: {
  slices: DonutSlice[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string | number;
  className?: string;
}) {
  const total = slices.reduce((a, s) => a + Math.max(0, s.value), 0);
  const radius = size / 2 - thickness / 2 - 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * radius;

  let offset = 0;

  return (
    <div className={cn("flex items-center gap-6", className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          className="stroke-bg-muted"
          strokeWidth={thickness}
          fill="none"
        />
        {total > 0 &&
          slices.map((s, i) => {
            const frac = Math.max(0, s.value) / total;
            const dash = frac * circ;
            const gap = circ - dash;
            const rot = (offset / circ) * 360 - 90;
            offset += dash;
            const tone = s.tone ?? TONE_ORDER[i % TONE_ORDER.length];
            return (
              <circle
                key={s.key}
                cx={cx}
                cy={cy}
                r={radius}
                className={STROKE_BY_TONE[tone]}
                strokeWidth={thickness}
                strokeDasharray={`${dash} ${gap}`}
                strokeDashoffset={0}
                fill="none"
                strokeLinecap="butt"
                transform={`rotate(${rot} ${cx} ${cy})`}
              />
            );
          })}
        <g>
          <text
            x={cx}
            y={cy - 2}
            textAnchor="middle"
            className="fill-fg font-mono text-2xl font-semibold"
          >
            {centerValue ?? total}
          </text>
          {centerLabel ? (
            <text
              x={cx}
              y={cy + 16}
              textAnchor="middle"
              className="fill-fg-muted text-[10px] uppercase tracking-wide"
            >
              {centerLabel}
            </text>
          ) : null}
        </g>
      </svg>
      <ul className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
        {slices.map((s, i) => {
          const tone = s.tone ?? TONE_ORDER[i % TONE_ORDER.length];
          const pct = total === 0 ? 0 : Math.round((s.value / total) * 100);
          return (
            <li
              key={s.key}
              className="flex items-center gap-2 text-fg-soft"
            >
              <span
                className={cn(
                  "inline-block h-2.5 w-2.5 rounded-full",
                  DOT_BY_TONE[tone],
                )}
              />
              <span className="flex-1 truncate">{s.label}</span>
              <span className="font-mono text-xs text-fg-muted">
                {s.value} · {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
