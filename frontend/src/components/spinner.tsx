import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function Spinner({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2 text-fg-muted", className)}>
      <Loader2 className="h-4 w-4 animate-spin" />
      {label ? <span className="text-sm">{label}</span> : null}
    </div>
  );
}
