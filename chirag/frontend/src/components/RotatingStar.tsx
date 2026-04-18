"use client";

/**
 * RotatingStar: a 5-point SVG star that spins slowly on the Y-axis.
 *
 * We stack three copies with slight z-translate + scale offsets to give a
 * layered, 3D-ish look without pulling in a WebGL library. A radial gradient
 * fill reacts to the component state so the star doubles as a status
 * indicator:
 *
 * - idle      → indigo / violet (slow 12s spin)
 * - listening → rose / red (faster 4s spin, outer pulse)
 * - thinking  → amber (medium spin, shimmer)
 * - speaking  → emerald (slow, steady)
 * - error     → slate
 */

export type StarState = "idle" | "listening" | "thinking" | "speaking" | "error";

const STATE_STYLE: Record<
  StarState,
  {
    core: string;
    accent: string;
    halo: string;
    shadow: string;
    label: string;
    duration: string;
    pulse: boolean;
  }
> = {
  idle: {
    core: "#a5b4fc",
    accent: "#8b5cf6",
    halo: "rgba(139,92,246,0.35)",
    shadow: "rgba(99,102,241,0.45)",
    label: "Idle",
    duration: "14s",
    pulse: false,
  },
  listening: {
    core: "#fecaca",
    accent: "#ef4444",
    halo: "rgba(244,63,94,0.45)",
    shadow: "rgba(244,63,94,0.65)",
    label: "Listening",
    duration: "5s",
    pulse: true,
  },
  thinking: {
    core: "#fde68a",
    accent: "#f59e0b",
    halo: "rgba(245,158,11,0.45)",
    shadow: "rgba(245,158,11,0.55)",
    label: "Thinking",
    duration: "6s",
    pulse: false,
  },
  speaking: {
    core: "#bbf7d0",
    accent: "#10b981",
    halo: "rgba(16,185,129,0.45)",
    shadow: "rgba(16,185,129,0.55)",
    label: "Speaking",
    duration: "10s",
    pulse: true,
  },
  error: {
    core: "#cbd5e1",
    accent: "#64748b",
    halo: "rgba(100,116,139,0.35)",
    shadow: "rgba(71,85,105,0.45)",
    label: "Error",
    duration: "20s",
    pulse: false,
  },
};

function StarShape({
  core,
  accent,
  id,
}: {
  core: string;
  accent: string;
  id: string;
}) {
  return (
    <svg viewBox="-60 -60 120 120" className="h-full w-full">
      <defs>
        <radialGradient id={`grad-${id}`} cx="45%" cy="40%" r="70%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="35%" stopColor={core} stopOpacity="0.95" />
          <stop offset="100%" stopColor={accent} stopOpacity="1" />
        </radialGradient>
        <linearGradient
          id={`edge-${id}`}
          x1="0%"
          y1="0%"
          x2="100%"
          y2="100%"
        >
          <stop offset="0%" stopColor="rgba(255,255,255,0.75)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
      </defs>
      {/* Five-point star polygon */}
      <polygon
        points="0,-55 14,-18 53,-17 22,7 33,44 0,22 -33,44 -22,7 -53,-17 -14,-18"
        fill={`url(#grad-${id})`}
        stroke={`url(#edge-${id})`}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RotatingStar({
  state,
  onClick,
  size = 280,
}: {
  state: StarState;
  onClick?: () => void;
  size?: number;
}) {
  const s = STATE_STYLE[state];
  const clickable = typeof onClick === "function";
  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: size, height: size }}
    >
      {/* ambient halo */}
      <div
        className={`absolute inset-0 rounded-full blur-3xl transition-colors duration-500 ${
          s.pulse ? "agnes-star-pulse" : ""
        }`}
        style={{ background: s.halo }}
      />

      <button
        type="button"
        onClick={onClick}
        aria-label={clickable ? `Star (${s.label}) — click to toggle` : s.label}
        disabled={!clickable}
        className={`relative h-full w-full rounded-full outline-none focus-visible:ring-4 focus-visible:ring-indigo-400/60 ${
          clickable ? "cursor-pointer" : "cursor-default"
        }`}
        style={{
          perspective: "1200px",
        }}
      >
        {/* back plate (thin, counter-rotating) */}
        <div
          className="agnes-star-spin-reverse absolute inset-0 opacity-40"
          style={{
            transformStyle: "preserve-3d",
            transform: "translateZ(-40px) scale(0.95)",
            animationDuration: s.duration,
            filter: `drop-shadow(0 0 24px ${s.shadow})`,
          }}
        >
          <StarShape core={s.core} accent={s.accent} id="back" />
        </div>

        {/* mid layer */}
        <div
          className="agnes-star-spin absolute inset-0 opacity-75"
          style={{
            transformStyle: "preserve-3d",
            transform: "translateZ(-10px) scale(0.98)",
            animationDuration: s.duration,
            filter: `drop-shadow(0 0 20px ${s.shadow})`,
          }}
        >
          <StarShape core={s.core} accent={s.accent} id="mid" />
        </div>

        {/* front */}
        <div
          className="agnes-star-spin absolute inset-0"
          style={{
            transformStyle: "preserve-3d",
            animationDuration: s.duration,
            filter: `drop-shadow(0 8px 28px ${s.shadow})`,
          }}
        >
          <StarShape core={s.core} accent={s.accent} id="front" />
        </div>

        {/* glossy center dot to sell the 3D */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-80 blur-sm"
          style={{
            background:
              "radial-gradient(circle, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0) 70%)",
          }}
        />
      </button>

      {/* state label under the star */}
      <span
        className="pointer-events-none absolute -bottom-8 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500"
      >
        {s.label}
      </span>
    </div>
  );
}
