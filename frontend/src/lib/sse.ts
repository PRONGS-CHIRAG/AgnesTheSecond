"use client";

export type SseEvent =
  | { event: "status"; data: { run_id: string; phase: string; status: string; pid: number | null } }
  | { event: "log"; data: { ts: number; stream: "stdout" | "stderr"; text: string } }
  | {
      event: "done";
      data: {
        run_id: string;
        status: string;
        exit_code: number | null;
        ended_at: number | null;
        error: string | null;
      };
    };

export interface SseHandlers {
  onStatus?: (d: Extract<SseEvent, { event: "status" }>["data"]) => void;
  onLog?: (d: Extract<SseEvent, { event: "log" }>["data"]) => void;
  onDone?: (d: Extract<SseEvent, { event: "done" }>["data"]) => void;
  onError?: (err: unknown) => void;
}

export function subscribeToRun(url: string, handlers: SseHandlers): () => void {
  let source: EventSource | null = null;
  try {
    source = new EventSource(url);
  } catch (err) {
    handlers.onError?.(err);
    return () => {};
  }

  const parse = <K extends SseEvent["event"]>(ev: MessageEvent, kind: K) => {
    try {
      const data = JSON.parse(ev.data);
      if (kind === "status") handlers.onStatus?.(data);
      else if (kind === "log") handlers.onLog?.(data);
      else if (kind === "done") handlers.onDone?.(data);
    } catch (err) {
      handlers.onError?.(err);
    }
  };

  source.addEventListener("status", (ev) => parse(ev as MessageEvent, "status"));
  source.addEventListener("log", (ev) => parse(ev as MessageEvent, "log"));
  source.addEventListener("done", (ev) => parse(ev as MessageEvent, "done"));
  source.onerror = (err) => {
    handlers.onError?.(err);
  };

  return () => {
    try {
      source?.close();
    } catch {
      // ignore
    }
  };
}
