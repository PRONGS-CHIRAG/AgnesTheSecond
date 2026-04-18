import { ReactNode } from "react";

export type StatAccent =
  | "indigo"
  | "emerald"
  | "amber"
  | "rose"
  | "slate"
  | "violet"
  | "sky";

const ACCENTS: Record<StatAccent, { bar: string; icon: string; label: string }> =
  {
    indigo: {
      bar: "from-indigo-500 to-violet-500",
      icon: "bg-indigo-50 text-indigo-600",
      label: "text-indigo-600",
    },
    emerald: {
      bar: "from-emerald-500 to-teal-500",
      icon: "bg-emerald-50 text-emerald-600",
      label: "text-emerald-700",
    },
    amber: {
      bar: "from-amber-500 to-orange-500",
      icon: "bg-amber-50 text-amber-600",
      label: "text-amber-700",
    },
    rose: {
      bar: "from-rose-500 to-pink-500",
      icon: "bg-rose-50 text-rose-600",
      label: "text-rose-700",
    },
    slate: {
      bar: "from-slate-500 to-slate-700",
      icon: "bg-slate-100 text-slate-600",
      label: "text-slate-600",
    },
    violet: {
      bar: "from-violet-500 to-fuchsia-500",
      icon: "bg-violet-50 text-violet-600",
      label: "text-violet-700",
    },
    sky: {
      bar: "from-sky-500 to-blue-500",
      icon: "bg-sky-50 text-sky-600",
      label: "text-sky-700",
    },
  };

export function StatCard({
  label,
  value,
  sublabel,
  accent = "indigo",
  icon,
}: {
  label: string;
  value: ReactNode;
  sublabel?: ReactNode;
  accent?: StatAccent;
  icon?: ReactNode;
}) {
  const a = ACCENTS[accent];
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div
        className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${a.bar}`}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div
            className={`text-[11px] font-semibold uppercase tracking-wide ${a.label}`}
          >
            {label}
          </div>
          <div className="mt-1 truncate text-2xl font-semibold text-slate-900">
            {value}
          </div>
          {sublabel && (
            <div className="mt-1 truncate text-xs text-slate-500">
              {sublabel}
            </div>
          )}
        </div>
        {icon && (
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg ${a.icon}`}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
