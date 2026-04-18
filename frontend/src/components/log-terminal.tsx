"use client";

import { useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/utils";

export interface LogLine {
  ts: number;
  stream: "stdout" | "stderr";
  text: string;
}

const LEVEL_CLASS: Record<string, string> = {
  debug: "text-fg-muted",
  info: "text-fg-soft",
  warn: "text-warn",
  warning: "text-warn",
  error: "text-bad",
  critical: "text-bad",
};

function classifyLine(line: LogLine): string {
  const lower = line.text.toLowerCase();
  if (line.stream === "stderr") return LEVEL_CLASS.error;
  if (lower.includes(" error") || lower.startsWith("error")) return LEVEL_CLASS.error;
  if (lower.includes("traceback")) return LEVEL_CLASS.error;
  if (lower.includes("429") || lower.includes("resource_exhausted"))
    return LEVEL_CLASS.error;
  if (lower.includes("[warn") || lower.includes(" warning")) return LEVEL_CLASS.warn;
  if (lower.includes("[info") || lower.includes("phase")) return LEVEL_CLASS.info;
  return "text-fg-soft";
}

export function LogTerminal({
  logs,
  emptyLabel = "Waiting for output…",
  className,
}: {
  logs: LogLine[];
  emptyLabel?: string;
  className?: string;
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight < 40;
      stickRef.current = nearBottom;
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (stickRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" });
    }
  }, [logs.length]);

  const rendered = useMemo(() => logs.slice(-2000), [logs]);

  return (
    <div
      ref={wrapRef}
      className={cn(
        "max-h-[28rem] overflow-auto rounded-lg border border-border bg-black/40 p-3 font-mono text-xs",
        className,
      )}
    >
      {rendered.length === 0 ? (
        <div className="py-6 text-center text-fg-muted">{emptyLabel}</div>
      ) : (
        <pre className="whitespace-pre-wrap break-words">
          {rendered.map((l, i) => (
            <div key={i} className={classifyLine(l)}>
              {l.text}
            </div>
          ))}
          <div ref={bottomRef} />
        </pre>
      )}
    </div>
  );
}
