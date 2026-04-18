import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export function SupplierBadge({
  name,
  soleSource,
  className,
}: {
  name: string;
  soleSource?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "chip max-w-[14rem]",
        soleSource
          ? "border-warn/40 bg-warn/10 text-warn"
          : "border-accent/40 bg-accent/10 text-accent",
        className,
      )}
      title={soleSource ? `${name} · sole source` : name}
    >
      {soleSource ? <AlertTriangle className="h-3 w-3 shrink-0" /> : null}
      <span className="truncate">{name}</span>
    </span>
  );
}
