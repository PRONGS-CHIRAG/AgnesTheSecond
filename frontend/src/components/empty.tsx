import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Empty({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "card flex flex-col items-center gap-2 px-6 py-12 text-center",
        className,
      )}
    >
      {icon ? <div className="text-fg-muted">{icon}</div> : null}
      <div className="text-base font-semibold text-fg">{title}</div>
      {description ? (
        <div className="max-w-md text-sm text-fg-muted">{description}</div>
      ) : null}
      {action ? <div className="pt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  detail,
  className,
}: {
  title: string;
  detail?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad",
        className,
      )}
    >
      <div className="font-semibold">{title}</div>
      {detail ? <div className="mt-1 text-bad/80">{detail}</div> : null}
    </div>
  );
}
