import { cn } from "@/lib/utils";

export function ScoreBar({
  value,
  label,
  className,
  tone = "accent",
}: {
  value: number | null | undefined;
  label?: string;
  className?: string;
  tone?: "accent" | "good" | "warn" | "bad" | "muted";
}) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value));
  const toneClass =
    tone === "good"
      ? "bg-good"
      : tone === "warn"
        ? "bg-warn"
        : tone === "bad"
          ? "bg-bad"
          : tone === "muted"
            ? "bg-fg-muted"
            : "bg-accent";
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label ? (
        <div className="flex items-center justify-between text-xs text-fg-muted">
          <span>{label}</span>
          <span className="font-mono">
            {value === null || value === undefined ? "—" : value.toFixed(2)}
          </span>
        </div>
      ) : null}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-muted">
        <div
          className={cn("h-full rounded-full transition-[width]", toneClass)}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
    </div>
  );
}

export function ScoreRadial({
  value,
  size = 84,
  label,
}: {
  value: number | null | undefined;
  size?: number;
  label?: string;
}) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value));
  const radius = size / 2 - 6;
  const circ = 2 * Math.PI * radius;
  const offset = circ * (1 - pct);
  const stroke =
    pct >= 0.7 ? "stroke-good" : pct >= 0.4 ? "stroke-warn" : "stroke-bad";
  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className="stroke-bg-muted"
          strokeWidth={6}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className={stroke}
          strokeWidth={6}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-mono text-lg font-semibold">
          {value === null || value === undefined ? "—" : value.toFixed(2)}
        </div>
        {label ? (
          <div className="text-[10px] uppercase tracking-wide text-fg-muted">
            {label}
          </div>
        ) : null}
      </div>
    </div>
  );
}
