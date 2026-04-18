"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function CollapseSection({
  title,
  subtitle,
  rightSlot,
  defaultOpen = false,
  children,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  rightSlot?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={cn("card px-4 py-3", className)}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 text-left"
      >
        <div className="text-fg-muted">
          {open ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="truncate text-sm font-semibold">{title}</div>
          {subtitle ? (
            <div className="truncate text-xs text-fg-muted">{subtitle}</div>
          ) : null}
        </div>
        {rightSlot ? <div className="flex items-center gap-2">{rightSlot}</div> : null}
      </button>
      {open ? <div className="mt-3">{children}</div> : null}
    </div>
  );
}
