"use client";

/**
 * /voicechat — Agnes 2 voice interface.
 *
 * Flow:
 * 1. User clicks the rotating star → mic permission → recording starts.
 * 2. Client-side VAD (RMS energy + silence timer) auto-stops after ~900 ms
 *    of quiet.
 * 3. The blob is POSTed to /api/voice/respond which runs: STT →
 *    answer agent (with tools) → humanizer. The JSON reply has transcript
 *    + answer_raw + answer_spoken.
 * 4. We immediately POST answer_spoken to /api/voice/tts which streams
 *    audio/mpeg back. The response body is collected into a Blob and
 *    played via an HTMLAudioElement.
 * 5. The turn is saved to a compact left-hand history sidebar.
 *
 * Clicking the star mid-recording stops capture early. Clicking mid-reply
 * cancels playback and lets the user start a new question.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RotatingStar, type StarState } from "@/components/RotatingStar";
import { fetchJSON } from "@/lib/api";
import {
  VoiceConfigSchema,
  VoiceRespondResponseSchema,
  type VoiceRespondResponse,
} from "@/lib/schemas/voice";

type Turn = {
  id: string;
  t: number;
  transcript: string;
  english_transcript: string;
  detected_language: string;
  detected_language_name: string;
  answer_spoken: string;
  answer_spoken_en: string;
  answer_language: string;
  answer_raw: string;
  total_ms: number;
};

function languageFlag(code: string): string {
  const c = (code || "").slice(0, 2).toLowerCase();
  const map: Record<string, string> = {
    en: "🇬🇧",
    fr: "🇫🇷",
    de: "🇩🇪",
    es: "🇪🇸",
    it: "🇮🇹",
    pt: "🇵🇹",
    nl: "🇳🇱",
    pl: "🇵🇱",
    ru: "🇷🇺",
    tr: "🇹🇷",
    ar: "🇸🇦",
    hi: "🇮🇳",
    ja: "🇯🇵",
    ko: "🇰🇷",
    zh: "🇨🇳",
    sv: "🇸🇪",
    no: "🇳🇴",
    da: "🇩🇰",
    fi: "🇫🇮",
    el: "🇬🇷",
    he: "🇮🇱",
    uk: "🇺🇦",
    cs: "🇨🇿",
    ro: "🇷🇴",
    hu: "🇭🇺",
    id: "🇮🇩",
    ms: "🇲🇾",
    vi: "🇻🇳",
    th: "🇹🇭",
    ta: "🇮🇳",
  };
  return map[c] || "🌐";
}

function isEnglishCode(code: string): boolean {
  return (code || "").toLowerCase().startsWith("en");
}

const HISTORY_KEY = "agnes2-voice-history";
// Cap the local transcript so localStorage stays well under 5MB even with
// multi-sentence answers; at ~2KB per turn, 200 turns is ~400KB.
const HISTORY_MAX = 200;

function loadHistory(): Turn[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.slice(0, HISTORY_MAX);
  } catch {
    return [];
  }
}

function saveHistory(turns: Turn[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify(turns.slice(0, HISTORY_MAX)),
    );
  } catch {
    /* ignore quota errors */
  }
}

function formatTime(ts: number) {
  const d = new Date(ts);
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

type PhaseLog = {
  label: string;
  ms: number;
};

type TurnCardProps = {
  transcript: string;
  english_transcript: string;
  detected_language: string;
  detected_language_name: string;
  answer_spoken: string;
  answer_spoken_en: string;
  answer_language: string;
  isLive?: boolean;
  phaseChips?: PhaseLog[];
};

function TurnCard(props: TurnCardProps) {
  const userNonEnglish =
    !!props.detected_language &&
    !isEnglishCode(props.detected_language) &&
    !!props.english_transcript &&
    props.english_transcript !== props.transcript;
  const replyNonEnglish =
    !!props.answer_language &&
    !isEnglishCode(props.answer_language) &&
    !!props.answer_spoken_en &&
    props.answer_spoken_en !== props.answer_spoken;
  return (
    <div className="space-y-2">
      <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 text-sm shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            You said
          </div>
          {props.detected_language && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
              {languageFlag(props.detected_language)}{" "}
              {props.detected_language_name ||
                props.detected_language.toUpperCase()}
            </span>
          )}
        </div>
        <div className="mt-1 text-slate-700">{props.transcript}</div>
        {userNonEnglish && (
          <div className="mt-2 border-t border-slate-200/60 pt-2 text-xs italic text-slate-500">
            <span className="mr-1 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest text-indigo-600">
              EN
            </span>
            {props.english_transcript}
          </div>
        )}
      </div>
      <div className="rounded-2xl border border-indigo-200/70 bg-gradient-to-br from-indigo-50 via-white to-fuchsia-50 p-4 text-sm shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-indigo-500">
            Agnes 2 said
          </div>
          {props.answer_language && (
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-indigo-500 shadow-sm">
              {languageFlag(props.answer_language)}{" "}
              {props.answer_language.toUpperCase()}
            </span>
          )}
        </div>
        <div className="mt-1 text-slate-800">{props.answer_spoken}</div>
        {replyNonEnglish && (
          <details className="mt-2 border-t border-indigo-200/50 pt-2 text-xs text-slate-500">
            <summary className="cursor-pointer select-none font-medium text-indigo-500">
              Show English version
            </summary>
            <div className="mt-1 italic">{props.answer_spoken_en}</div>
          </details>
        )}
        {props.isLive && props.phaseChips && props.phaseChips.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-widest text-slate-400">
            {props.phaseChips.map((p) => (
              <span
                key={p.label}
                className="rounded-full bg-white/70 px-2 py-0.5 shadow-sm"
              >
                {p.label} {p.ms}ms
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function VoiceChatPage() {
  const [state, setState] = useState<StarState>("idle");
  const [message, setMessage] = useState<string>(
    "Tap the star and ask Agnes 2 anything.",
  );
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Turn[]>([]);
  const [current, setCurrent] = useState<VoiceRespondResponse | null>(null);
  const [phases, setPhases] = useState<PhaseLog[]>([]);
  const [voiceReady, setVoiceReady] = useState<boolean | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadRafRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const speakingRef = useRef<boolean>(false);
  const chunksRef = useRef<Blob[]>([]);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const cancelledRef = useRef<boolean>(false);
  const startedAtRef = useRef<number>(0);
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setHistory(loadHistory());
    fetchJSON("/api/voice/config", VoiceConfigSchema)
      .then((cfg) => setVoiceReady(cfg.ready))
      .catch(() => setVoiceReady(false));
  }, []);

  // Keep the scrollable transcript pinned to the latest turn.
  useEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [history, current, state]);

  const cleanupCapture = useCallback(() => {
    if (vadRafRef.current != null) {
      cancelAnimationFrame(vadRafRef.current);
      vadRafRef.current = null;
    }
    if (silenceTimerRef.current != null) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        /* noop */
      }
    }
    mediaRecorderRef.current = null;
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      try {
        audioCtxRef.current.close();
      } catch {
        /* noop */
      }
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
  }, []);

  const abortPlayback = useCallback(() => {
    if (audioElRef.current) {
      audioElRef.current.pause();
      audioElRef.current.src = "";
      audioElRef.current = null;
    }
  }, []);

  const addPhase = useCallback((label: string, ms: number) => {
    setPhases((p) => [...p, { label, ms }]);
  }, []);

  const processBlob = useCallback(
    async (blob: Blob) => {
      setState("thinking");
      setMessage("Transcribing and thinking…");

      try {
        const uploadedAt = performance.now();
        const fd = new FormData();
        fd.append("audio", blob, "speech.webm");
        // Language intentionally omitted — Scribe auto-detects and the
        // backend routes non-English through the translator agent.

        const res = await fetch("/api/voice/respond", {
          method: "POST",
          body: fd,
          cache: "no-store",
        });

        if (cancelledRef.current) return;

        const text = await res.text();
        if (!res.ok) {
          let detail: unknown = text;
          try {
            detail = JSON.parse(text);
          } catch {
            /* keep text */
          }
          throw new Error(
            typeof detail === "object" && detail && "detail" in detail
              ? JSON.stringify((detail as Record<string, unknown>).detail)
              : text || `HTTP ${res.status}`,
          );
        }

        const json = JSON.parse(text);
        const parsed = VoiceRespondResponseSchema.safeParse(json);
        if (!parsed.success) {
          throw new Error("Invalid response from /api/voice/respond");
        }
        const reply = parsed.data;
        const serverMs = reply.timings.total_ms;
        addPhase("STT", reply.timings.stt_ms);
        if (reply.timings.translate_ms > 0) {
          addPhase("Translate", reply.timings.translate_ms);
        }
        addPhase("Answer", reply.timings.answer_ms);
        addPhase("Humanize", reply.timings.humanize_ms);
        if (reply.timings.backtranslate_ms > 0) {
          addPhase("Back-translate", reply.timings.backtranslate_ms);
        }

        setCurrent(reply);
        setMessage("Speaking…");
        setState("speaking");

        // Kick off TTS fetch immediately.
        const ttsStart = performance.now();
        const ttsRes = await fetch("/api/voice/tts", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            text: reply.answer_spoken,
            voice_id: reply.voice_id,
          }),
          cache: "no-store",
        });
        if (!ttsRes.ok) {
          throw new Error(`TTS failed: HTTP ${ttsRes.status}`);
        }
        const audioBlob = await ttsRes.blob();
        if (cancelledRef.current) return;
        const url = URL.createObjectURL(audioBlob);
        addPhase("TTS", Math.round(performance.now() - ttsStart));

        const audio = new Audio(url);
        audioElRef.current = audio;
        audio.onended = () => {
          URL.revokeObjectURL(url);
          if (audioElRef.current === audio) audioElRef.current = null;
          setState("idle");
          setMessage("Tap the star and ask Agnes 2 anything.");
        };
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          setState("idle");
          setMessage("Audio playback failed.");
        };
        try {
          await audio.play();
        } catch (playErr) {
          console.warn("autoplay blocked", playErr);
          setMessage(
            "Autoplay blocked by browser — click the star to hear the reply.",
          );
        }

        const turn: Turn = {
          id:
            typeof crypto !== "undefined" && "randomUUID" in crypto
              ? crypto.randomUUID()
              : `t_${Date.now()}`,
          t: Date.now(),
          transcript: reply.transcript,
          english_transcript: reply.english_transcript,
          detected_language: reply.detected_language,
          detected_language_name: reply.detected_language_name,
          answer_spoken: reply.answer_spoken,
          answer_spoken_en: reply.answer_spoken_en,
          answer_language: reply.answer_language,
          answer_raw: reply.answer_raw,
          total_ms: Math.round(performance.now() - uploadedAt),
        };
        setHistory((prev) => {
          const next = [turn, ...prev].slice(0, HISTORY_MAX);
          saveHistory(next);
          return next;
        });

        void serverMs;
      } catch (err) {
        console.error(err);
        setError(err instanceof Error ? err.message : String(err));
        setState("error");
        setMessage("Something went wrong — tap to retry.");
      }
    },
    [addPhase],
  );

  const stopRecording = useCallback(() => {
    if (!mediaRecorderRef.current) return;
    try {
      if (mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    } catch {
      /* ignore */
    }
  }, []);

  const startVAD = useCallback(() => {
    const ctx = audioCtxRef.current;
    const analyser = analyserRef.current;
    if (!ctx || !analyser) return;
    const buf = new Float32Array(analyser.fftSize);

    // thresholds
    const START_RMS = 0.025; // must cross once to count as "user has spoken"
    const STOP_RMS = 0.012;
    const SILENCE_MS = 900;
    const MAX_DURATION_MS = 20_000;

    const loop = () => {
      if (!mediaRecorderRef.current) return;
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);

      if (!speakingRef.current) {
        if (rms > START_RMS) speakingRef.current = true;
      } else if (rms < STOP_RMS) {
        if (silenceTimerRef.current == null) {
          silenceTimerRef.current = window.setTimeout(() => {
            silenceTimerRef.current = null;
            stopRecording();
          }, SILENCE_MS);
        }
      } else if (silenceTimerRef.current != null) {
        window.clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }

      if (performance.now() - startedAtRef.current > MAX_DURATION_MS) {
        stopRecording();
        return;
      }
      vadRafRef.current = requestAnimationFrame(loop);
    };
    vadRafRef.current = requestAnimationFrame(loop);
  }, [stopRecording]);

  const startRecording = useCallback(async () => {
    setError(null);
    setPhases([]);
    setCurrent(null);
    cancelledRef.current = false;
    speakingRef.current = false;
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      const mime =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : "";
      const recorder = new MediaRecorder(
        stream,
        mime ? { mimeType: mime } : undefined,
      );
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        cleanupCapture();
        if (blob.size < 1200) {
          setState("idle");
          setMessage("I didn't catch that — try again a little louder.");
          return;
        }
        if (!cancelledRef.current) {
          void processBlob(blob);
        }
      };

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      analyserRef.current = analyser;

      startedAtRef.current = performance.now();
      recorder.start(250);
      setState("listening");
      setMessage("Listening… speak naturally.");
      startVAD();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : String(err));
      setState("error");
      setMessage(
        "Couldn't access the microphone — check browser permissions.",
      );
      cleanupCapture();
    }
  }, [cleanupCapture, processBlob, startVAD]);

  const handleStarClick = useCallback(() => {
    if (state === "idle" || state === "error") {
      void startRecording();
      return;
    }
    if (state === "listening") {
      stopRecording();
      return;
    }
    if (state === "speaking") {
      cancelledRef.current = true;
      abortPlayback();
      setState("idle");
      setMessage("Tap the star and ask Agnes 2 anything.");
      return;
    }
    // thinking: let the user cancel the in-flight reply
    if (state === "thinking") {
      cancelledRef.current = true;
      setState("idle");
      setMessage("Cancelled. Tap the star to try again.");
    }
  }, [abortPlayback, startRecording, state, stopRecording]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      cleanupCapture();
      abortPlayback();
    };
  }, [abortPlayback, cleanupCapture]);

  const latencyBadge = useMemo(() => {
    if (phases.length === 0) return null;
    const total = phases.reduce((s, p) => s + p.ms, 0);
    return `${(total / 1000).toFixed(2)}s`;
  }, [phases]);

  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-6 px-4 py-6 lg:px-6">
        {/* Sidebar */}
        <aside className="hidden w-72 shrink-0 flex-col gap-3 lg:flex">
          <div className="rounded-2xl border border-slate-200/70 bg-white/80 p-4 shadow-sm backdrop-blur">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                History
              </h2>
              {history.length > 0 && (
                <button
                  type="button"
                  className="text-[11px] font-medium text-slate-400 hover:text-rose-500"
                  onClick={() => {
                    setHistory([]);
                    saveHistory([]);
                  }}
                >
                  Clear
                </button>
              )}
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
              Last {HISTORY_MAX} voice turns, stored locally.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto rounded-2xl border border-slate-200/70 bg-white/60 p-2 shadow-sm backdrop-blur">
            {history.length === 0 ? (
              <div className="flex h-full items-center justify-center px-4 py-10 text-center text-xs text-slate-400">
                No voice turns yet — tap the star to get started.
              </div>
            ) : (
              <ul className="space-y-1.5">
                {history.map((h) => (
                  <li
                    key={h.id}
                    className="group rounded-xl border border-transparent bg-white/80 px-3 py-2 shadow-sm transition hover:border-indigo-200 hover:shadow-md"
                  >
                    <div className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-widest text-slate-400">
                      <span className="flex items-center gap-1">
                        {h.detected_language && (
                          <span title={h.detected_language_name || h.detected_language}>
                            {languageFlag(h.detected_language)}
                          </span>
                        )}
                        <span>{formatTime(h.t)}</span>
                      </span>
                      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold text-slate-500">
                        {(h.total_ms / 1000).toFixed(1)}s
                      </span>
                    </div>
                    <div className="mt-1 line-clamp-2 text-[12px] font-medium text-slate-700">
                      {h.transcript}
                    </div>
                    {!isEnglishCode(h.detected_language) &&
                      h.english_transcript &&
                      h.english_transcript !== h.transcript && (
                        <div className="mt-0.5 line-clamp-2 text-[11px] italic text-slate-400">
                          → {h.english_transcript}
                        </div>
                      )}
                    <div className="mt-1 line-clamp-2 text-[11px] text-slate-500">
                      {h.answer_spoken}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {/* Main canvas */}
        <section className="relative flex flex-1 flex-col overflow-hidden rounded-3xl border border-slate-200/70 bg-gradient-to-b from-white via-indigo-50/40 to-white shadow-sm backdrop-blur">
          <header className="flex items-center justify-between gap-3 border-b border-slate-200/60 px-6 py-4">
            <div>
              <h1 className="text-lg font-semibold text-slate-900">
                Agnes 2 — voice
              </h1>
              <p className="text-xs text-slate-500">
                Charlotte · multilingual · under three-second target
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              {current &&
                current.detected_language &&
                !isEnglishCode(current.detected_language) && (
                  <span className="rounded-full bg-fuchsia-50 px-2 py-0.5 font-medium text-fuchsia-600">
                    {languageFlag(current.detected_language)}{" "}
                    {current.detected_language_name || current.detected_language}
                    {" → EN"}
                  </span>
                )}
              {voiceReady === false && (
                <span className="rounded-full bg-rose-50 px-2 py-0.5 font-medium text-rose-600">
                  ElevenLabs key missing
                </span>
              )}
              {voiceReady === true && (
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-600">
                  Voice ready
                </span>
              )}
              {latencyBadge && (
                <span className="rounded-full bg-indigo-50 px-2 py-0.5 font-medium text-indigo-600">
                  {latencyBadge}
                </span>
              )}
            </div>
          </header>

          <div className="relative flex flex-1 flex-col items-center overflow-hidden px-6 pt-8">
            <RotatingStar state={state} onClick={handleStarClick} />

            <div className="mt-8 max-w-xl text-center text-sm text-slate-600">
              <p className="font-medium text-slate-700">{message}</p>
              {error && (
                <p className="mt-2 text-xs text-rose-500">{error}</p>
              )}
            </div>

            <div
              ref={transcriptRef}
              className="mt-6 w-full max-w-2xl flex-1 overflow-y-auto scroll-smooth pb-10 pr-1"
            >
              <div className="space-y-3">
                {history.length === 0 && !current && (
                  <div className="pt-10 text-center text-xs text-slate-400">
                    Your conversation will appear here. Tap the star to start.
                  </div>
                )}

                {history
                  .slice()
                  .reverse()
                  .map((h) => (
                    <TurnCard
                      key={h.id}
                      transcript={h.transcript}
                      english_transcript={h.english_transcript}
                      detected_language={h.detected_language}
                      detected_language_name={h.detected_language_name}
                      answer_spoken={h.answer_spoken}
                      answer_spoken_en={h.answer_spoken_en}
                      answer_language={h.answer_language}
                    />
                  ))}

                {current &&
                  (() => {
                    const latest = history[0];
                    const alreadyPersisted =
                      !!latest &&
                      latest.transcript === current.transcript &&
                      latest.answer_raw === current.answer_raw;
                    if (alreadyPersisted) return null;
                    return (
                      <TurnCard
                        key="live"
                        transcript={current.transcript}
                        english_transcript={current.english_transcript}
                        detected_language={current.detected_language}
                        detected_language_name={current.detected_language_name}
                        answer_spoken={current.answer_spoken}
                        answer_spoken_en={current.answer_spoken_en}
                        answer_language={current.answer_language}
                        isLive
                        phaseChips={phases}
                      />
                    );
                  })()}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
