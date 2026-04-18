import type { z } from "zod";
import * as S from "./schema";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function fetchJSON<T extends z.ZodTypeAny>(
  path: string,
  schema: T,
  init?: RequestInit,
): Promise<z.infer<T>> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    const maybe = body as { detail?: { error?: string; message?: string } } | null;
    const message = maybe?.detail?.message ?? maybe?.detail?.error ?? res.statusText;
    throw new ApiError(res.status, body, message ?? `HTTP ${res.status}`);
  }
  return schema.parse(body);
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then((r) => r.json()),
  summary: () => fetchJSON("/api/summary", S.Summary),
  dashboard: () => fetchJSON("/api/dashboard", S.DashboardBundle),
  supplyNetwork: () => fetchJSON("/api/supply-network", S.SupplyNetworkBundle),
  registry: (params: {
    limit?: number;
    offset?: number;
    q?: string;
    family?: string;
    role?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    if (params.offset !== undefined) q.set("offset", String(params.offset));
    if (params.q) q.set("q", params.q);
    if (params.family) q.set("family", params.family);
    if (params.role) q.set("role", params.role);
    const qs = q.toString();
    return fetchJSON(`/api/registry${qs ? `?${qs}` : ""}`, S.RegistryPage);
  },
  candidates: () => fetchJSON("/api/candidates", S.SubstituteCandidateReport),
  evidence: () => fetchJSON("/api/evidence", S.EvidenceReport),
  evidencePair: (sourceKey: string, candidateKey: string) =>
    fetchJSON(
      `/api/evidence/${encodeURIComponent(sourceKey)}/${encodeURIComponent(candidateKey)}`,
      S.SubstituteEvidence,
    ),
  assessments: () => fetchJSON("/api/assessments", S.AssessmentReport),
  recommendations: () => fetchJSON("/api/recommendations", S.RecommendationReport),
  opportunities: () =>
    fetchJSON("/api/opportunities", S.RecommendationReport.shape.opportunities),
  opportunity: (sourceKey: string) =>
    fetchJSON(
      `/api/opportunities/${encodeURIComponent(sourceKey)}`,
      S.OpportunityDetail,
    ),
  runsList: async (): Promise<S.RunMeta[]> => {
    const res = await fetch(`${BASE}/api/runs`, { cache: "no-store" });
    if (!res.ok) throw new ApiError(res.status, await res.text(), res.statusText);
    const body = await res.json();
    return S.RunMeta.array().parse(body.runs ?? []);
  },
  runSnapshot: (runId: string) =>
    fetchJSON(`/api/runs/${encodeURIComponent(runId)}`, S.RunSnapshot),
  startPhase: async <B extends Record<string, unknown>>(
    phase: "phase4" | "phase5" | "phase6" | "phase7",
    body: B,
  ) => {
    const res = await fetch(`${BASE}/api/runs/${phase}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new ApiError(
        res.status,
        json,
        (json?.detail?.message as string) || res.statusText,
      );
    }
    return json as { run_id: string; phase: string; status: string; args: string[] };
  },
  cancelRun: async (runId: string) => {
    const res = await fetch(
      `${BASE}/api/runs/${encodeURIComponent(runId)}/cancel`,
      { method: "POST", cache: "no-store" },
    );
    if (!res.ok) throw new ApiError(res.status, await res.text(), res.statusText);
    return res.json();
  },
  sseUrl: (runId: string) =>
    `${BASE}/api/runs/${encodeURIComponent(runId)}/events`,
};

export const API_BASE = BASE;
