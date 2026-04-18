export type ProgressTone = "emerald" | "indigo" | "amber" | "rose" | "violet";

const TONES: Record<ProgressTone, string> = {
  emerald: "bg-gradient-to-r from-emerald-400 to-emerald-600",
  indigo: "bg-gradient-to-r from-indigo-400 to-indigo-600",
  amber: "bg-gradient-to-r from-amber-400 to-amber-600",
  rose: "bg-gradient-to-r from-rose-400 to-rose-600",
  violet: "bg-gradient-to-r from-violet-400 to-violet-600",
};

export function ProgressBar({
  value,
  tone = "emerald",
  showValue = true,
  width = "w-16",
}: {
  value: number;
  tone?: ProgressTone;
  showValue?: boolean;
  width?: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="inline-flex items-center gap-2">
      <div
        className={`h-1.5 overflow-hidden rounded-full bg-slate-200 ${width}`}
      >
        <div
          className={`h-full rounded-full ${TONES[tone]}`}
          style={{ width: `${v}%` }}
        />
      </div>
      {showValue && (
        <span className="tabular-nums text-xs text-slate-700">
          {v.toFixed(0)}%
        </span>
      )}
    </div>
  );
}

export function scoreTone(value: number): ProgressTone {
  if (value >= 90) return "emerald";
  if (value >= 75) return "violet";
  if (value >= 50) return "amber";
  return "rose";
}
