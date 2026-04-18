import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { humanAge } from "@/lib/utils";

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  present,
  generatedAt,
  children,
  className,
}: {
  title: string;
  value: ReactNode;
  subtitle?: string;
  icon?: ReactNode;
  present?: boolean;
  generatedAt?: string | null;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("card flex flex-col gap-2 px-4 py-3", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-fg-muted">
          {icon ? <span className="text-fg-soft">{icon}</span> : null}
          <span>{title}</span>
        </div>
        {present === false ? (
          <span className="chip border-warn/40 bg-warn/10 text-warn">missing</span>
        ) : generatedAt ? (
          <span className="chip" title={generatedAt}>
            {humanAge(generatedAt)}
          </span>
        ) : null}
      </div>
      <div className="text-2xl font-semibold text-fg">{value}</div>
      {subtitle ? (
        <div className="text-xs text-fg-muted">{subtitle}</div>
      ) : null}
      {children}
    </div>
  );
}
