"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Play, StopCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { subscribeToRun } from "@/lib/sse";
import { LogTerminal, type LogLine } from "@/components/log-terminal";
import { cn, humanAge } from "@/lib/utils";

export type PhaseId = "phase4" | "phase5" | "phase6" | "phase7";

export interface FieldSpec {
  name: string;
  label: string;
  kind: "text" | "number" | "boolean" | "select";
  placeholder?: string;
  help?: string;
  options?: { label: string; value: string }[];
  min?: number;
  max?: number;
  step?: number;
}

export interface RunPanelProps {
  phase: PhaseId;
  title: string;
  description: string;
  produces: string;
  generatedAt: string | null | undefined;
  partial?: boolean;
  fields: FieldSpec[];
  invalidateKeys: string[][];
}

export function RunPanel(props: RunPanelProps) {
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<
    "idle" | "starting" | "running" | "succeeded" | "failed" | "cancelled"
  >("idle");
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [quotaWarning, setQuotaWarning] = useState<string | null>(null);
  const unsubRef = useRef<null | (() => void)>(null);

  useEffect(() => {
    return () => {
      unsubRef.current?.();
    };
  }, []);

  const running = status === "starting" || status === "running";

  const body = useMemo(() => buildBody(props.fields, values), [props.fields, values]);

  async function onStart() {
    setSubmitting(true);
    setLogs([]);
    setQuotaWarning(null);
    setStatus("starting");
    try {
      const res = await api.startPhase(props.phase, body);
      setRunId(res.run_id);
      const unsub = subscribeToRun(api.sseUrl(res.run_id), {
        onStatus: (d) => {
          setStatus(d.status as typeof status);
        },
        onLog: (d) => {
          setLogs((prev) => [...prev, d]);
          if (/429|rate_limit|insufficient_quota|resource_exhausted/i.test(d.text)) {
            setQuotaWarning(
              "LLM rate-limit or quota error detected. Try a different model, re-run with --dry-run, or wait for the limit to reset.",
            );
          }
        },
        onDone: (d) => {
          setStatus(d.status as typeof status);
          if (d.status === "succeeded") {
            toast.success(`${props.phase} finished`, {
              description: `Refreshed ${props.produces}.`,
            });
            for (const key of props.invalidateKeys) {
              qc.invalidateQueries({ queryKey: key });
            }
          } else if (d.status === "cancelled") {
            toast.message(`${props.phase} cancelled`);
          } else {
            toast.error(`${props.phase} failed`, {
              description: d.error ?? `exit_code=${d.exit_code}`,
            });
          }
        },
        onError: () => {
          // EventSource errors fire on stream close too — ignore silently.
        },
      });
      unsubRef.current?.();
      unsubRef.current = unsub;
    } catch (err) {
      const msg = (err as Error).message ?? "Failed to start run";
      setStatus("failed");
      toast.error(`${props.phase} could not start`, { description: msg });
    } finally {
      setSubmitting(false);
    }
  }

  async function onCancel() {
    if (!runId) return;
    try {
      await api.cancelRun(runId);
      toast.message(`Cancelling ${props.phase}…`);
    } catch (err) {
      toast.error("Cancel failed", { description: (err as Error).message });
    }
  }

  return (
    <div className="card flex flex-col gap-4 px-5 py-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Zap className="h-4 w-4 text-accent" />
            {props.title}
          </h2>
          <p className="mt-1 text-sm text-fg-muted">{props.description}</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          <span
            className={cn(
              "chip",
              status === "succeeded"
                ? "border-good/40 bg-good/10 text-good"
                : status === "failed"
                  ? "border-bad/40 bg-bad/10 text-bad"
                  : running
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : undefined,
            )}
          >
            {status}
          </span>
          <span className="chip">produces {props.produces}</span>
          <span className="chip" title={props.generatedAt ?? undefined}>
            {props.generatedAt ? humanAge(props.generatedAt) : "never run"}
          </span>
          {props.partial ? (
            <span className="chip border-warn/40 bg-warn/10 text-warn">
              partial
            </span>
          ) : null}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {props.fields.map((f) => (
          <FieldInput
            key={f.name}
            spec={f}
            value={values[f.name]}
            onChange={(v) => setValues((prev) => ({ ...prev, [f.name]: v }))}
          />
        ))}
      </div>

      {quotaWarning ? (
        <div className="flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          <AlertTriangle className="mt-0.5 h-4 w-4" />
          <span>{quotaWarning}</span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          className="btn-primary"
          disabled={submitting || running}
          onClick={onStart}
        >
          <Play className="h-4 w-4" />
          {running ? "Running…" : "Run"}
        </button>
        <button className="btn" disabled={!running || !runId} onClick={onCancel}>
          <StopCircle className="h-4 w-4" />
          Cancel
        </button>
        {runId ? (
          <span className="font-mono text-xs text-fg-muted">run {runId}</span>
        ) : null}
      </div>

      <LogTerminal logs={logs} />
    </div>
  );
}

function buildBody(
  fields: FieldSpec[],
  values: Record<string, string | boolean>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) {
    const v = values[f.name];
    if (v === undefined || v === "" || v === null) continue;
    if (f.kind === "boolean") {
      if (v === true) out[f.name] = true;
    } else if (f.kind === "number") {
      const num = typeof v === "string" ? Number(v) : Number.NaN;
      if (!Number.isNaN(num)) out[f.name] = num;
    } else {
      out[f.name] = v;
    }
  }
  return out;
}

function FieldInput({
  spec,
  value,
  onChange,
}: {
  spec: FieldSpec;
  value: string | boolean | undefined;
  onChange: (v: string | boolean) => void;
}) {
  if (spec.kind === "boolean") {
    return (
      <label className="flex items-center gap-2 rounded-md border border-border bg-bg-muted px-3 py-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="font-medium">{spec.label}</span>
        {spec.help ? (
          <span className="text-xs text-fg-muted">({spec.help})</span>
        ) : null}
      </label>
    );
  }
  if (spec.kind === "select") {
    return (
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-fg-muted">{spec.label}</span>
        <select
          className="input"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">default</option>
          {(spec.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {spec.help ? (
          <span className="text-xs text-fg-muted">{spec.help}</span>
        ) : null}
      </label>
    );
  }
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-fg-muted">{spec.label}</span>
      <input
        type={spec.kind === "number" ? "number" : "text"}
        className="input"
        placeholder={spec.placeholder}
        value={(value as string) ?? ""}
        min={spec.min}
        max={spec.max}
        step={spec.step}
        onChange={(e) => onChange(e.target.value)}
      />
      {spec.help ? (
        <span className="text-xs text-fg-muted">{spec.help}</span>
      ) : null}
    </label>
  );
}
