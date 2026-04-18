"use client";

import { useEffect, useRef, useState } from "react";

import { Markdown } from "@/components/Markdown";
import { fetchJSON } from "@/lib/api";
import {
  ChatMessage,
  ChatResponse,
  ChatResponseSchema,
  ChatStep,
} from "@/lib/schemas/chat";

type Turn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: ChatStep[];
  finishReason?: ChatResponse["finish_reason"];
};

const MAX_HISTORY_MESSAGES = 12;

const SUGGESTIONS: { icon: string; tone: string; q: string }[] = [
  {
    icon: "⚠",
    tone: "border-rose-200 bg-rose-50 text-rose-800 hover:bg-rose-100",
    q: "What are the highest-severity supply risks right now?",
  },
  {
    icon: "↓",
    tone: "border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100",
    q: "What consolidation opportunity has the highest estimated savings?",
  },
  {
    icon: "⊚",
    tone: "border-indigo-200 bg-indigo-50 text-indigo-800 hover:bg-indigo-100",
    q: "Find substitute candidates for vitamin-c-ascorbic-acid.",
  },
  {
    icon: "▾",
    tone: "border-violet-200 bg-violet-50 text-violet-800 hover:bg-violet-100",
    q: "Analyze the BOM of any finished good containing 'orange juice'.",
  },
];

function uid() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length, pending]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || pending) return;

    const userTurn: Turn = { id: uid(), role: "user", content: message };
    const history: ChatMessage[] = turns
      .slice(-MAX_HISTORY_MESSAGES)
      .map((t) => ({ role: t.role, content: t.content }));

    setTurns((prev) => [...prev, userTurn]);
    setDraft("");
    setPending(true);
    setError(null);

    try {
      const resp = await fetchJSON("/api/chat", ChatResponseSchema, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
      });

      setTurns((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          content: resp.reply,
          steps: resp.steps,
          finishReason: resp.finish_reason,
        },
      ]);
    } catch (err: unknown) {
      const detail = (err as { detail?: { error?: string; message?: string } })
        ?.detail;
      if (detail?.error === "llm_unavailable") {
        setError(
          "The chat agent is not configured — set AGNES_OPENAI_API_KEY and restart the backend.",
        );
      } else {
        setError(
          detail?.message ||
            (err as Error)?.message ||
            "The chat agent failed to respond. Please try again.",
        );
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 pb-4 pt-2">
      <header className="mb-3 flex items-center justify-between gap-3 px-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Agnes 2 Chat
          </h1>
          <p className="text-xs text-slate-500">
            Evidence-grounded assistant. Every claim is backed by a tool call
            (SQL, Phase 4/5/6.5/7 artifacts).
          </p>
        </div>
        {turns.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setTurns([]);
              setError(null);
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            New chat
          </button>
        )}
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="space-y-4">
          {turns.length === 0 && (
            <EmptyState onPick={(q) => setDraft(q)} />
          )}

          {turns.map((turn) => (
            <TurnBubble key={turn.id} turn={turn} />
          ))}

          {pending && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
              </span>
              Agnes 2 is calling tools…
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {error}
            </div>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="mt-3 rounded-xl border border-slate-200 bg-white p-2 shadow-sm"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask about substitutions, risks, BOMs, or savings…"
            className="flex-1 rounded-lg border border-transparent bg-slate-50 px-3 py-2 text-sm focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            disabled={pending}
          />
          <button
            type="submit"
            disabled={pending || !draft.trim()}
            className="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-700 hover:to-violet-700 disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-400"
          >
            Send
            <span aria-hidden>↵</span>
          </button>
        </div>
      </form>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="py-6 text-center">
      <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 text-lg font-bold text-white shadow-sm">
        A
      </div>
      <h2 className="mt-3 text-lg font-semibold text-slate-800">
        Ask Agnes 2 anything about your supply chain
      </h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">
        She can query SQL, inspect Phase artifacts, and chain tool calls. Try
        one of these to start:
      </p>
      <ul className="mx-auto mt-4 grid max-w-2xl gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <li key={s.q}>
            <button
              type="button"
              className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition ${s.tone}`}
              onClick={() => onPick(s.q)}
            >
              <span className="mt-0.5 font-mono text-base leading-none">
                {s.icon}
              </span>
              <span>{s.q}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TurnBubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
          isUser
            ? "bg-gradient-to-br from-slate-800 to-slate-900 text-white"
            : "border border-slate-200 bg-white text-slate-800"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap leading-relaxed">
            {turn.content}
          </div>
        ) : (
          <Markdown>{turn.content}</Markdown>
        )}

        {!isUser && turn.steps && turn.steps.length > 0 && (
          <details className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white text-xs">
            <summary className="cursor-pointer border-b border-slate-200 bg-slate-50/80 px-3 py-2 font-medium text-slate-700 hover:bg-slate-100">
              <span className="inline-flex items-center gap-2">
                <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-indigo-100 text-[10px] font-bold text-indigo-700">
                  {turn.steps.length}
                </span>
                Reasoning ·{" "}
                {turn.steps.length === 1 ? "1 tool call" : `${turn.steps.length} tool calls`}
              </span>
            </summary>
            <ol className="divide-y divide-slate-100">
              {turn.steps.map((step, i) => (
                <li
                  key={`${step.tool}-${i}`}
                  className={`px-3 py-2 ${
                    step.ok ? "" : "bg-rose-50/60"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${
                          step.ok ? "bg-emerald-500" : "bg-rose-500"
                        }`}
                      />
                      <span className="font-mono font-semibold text-slate-700">
                        {step.tool}
                      </span>
                    </span>
                    <span className="text-slate-400">
                      {step.duration_ms} ms
                    </span>
                  </div>
                  <div className="mt-0.5 text-slate-600">{step.label}</div>
                  {step.error && (
                    <div className="mt-1 rounded bg-rose-100/60 px-2 py-1 text-rose-700">
                      {step.error}
                    </div>
                  )}
                  {step.result_preview && (
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-2 text-[11px] text-slate-500">
                      {step.result_preview}
                    </pre>
                  )}
                </li>
              ))}
            </ol>
          </details>
        )}

        {!isUser && turn.finishReason === "max_iterations" && (
          <div className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
            Reached the tool-use budget for this turn.
          </div>
        )}

        {!isUser && turn.finishReason === "refused" && (
          <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
            Out of scope — Agnes 2 only answers supply chain and procurement questions.
          </div>
        )}
      </div>
    </div>
  );
}
