import { ExternalLink } from "lucide-react";
import type { CitationRef } from "@/lib/schema";
import { cn } from "@/lib/utils";

function domainOf(url: string, hint?: string | null): string {
  if (hint) return hint;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function CitationChip({
  citation,
  className,
  compact = false,
}: {
  citation: CitationRef;
  className?: string;
  compact?: boolean;
}) {
  const d = domainOf(citation.url, citation.domain ?? undefined);
  const favicon = `https://www.google.com/s2/favicons?sz=32&domain=${encodeURIComponent(d)}`;
  const title = citation.title?.trim() || d;
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "group inline-flex max-w-full items-center gap-2 rounded-full border border-border bg-bg-muted/60 px-2 py-1 text-xs text-fg-soft transition-colors hover:border-accent/50 hover:bg-accent/10 hover:text-accent",
        compact && "py-0.5",
        className,
      )}
      title={citation.url}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={favicon}
        alt=""
        width={14}
        height={14}
        className="h-3.5 w-3.5 rounded-sm"
        loading="lazy"
      />
      <span className="truncate" style={{ maxWidth: compact ? 140 : 220 }}>
        {title}
      </span>
      <span className="text-fg-muted">· {d}</span>
      <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100" />
    </a>
  );
}
