"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardBundle } from "@/lib/schema";

export const DASHBOARD_QUERY_KEY = ["dashboard"] as const;

/**
 * One-shot fetch that powers the dashboard. On success, sibling query caches
 * are seeded so that sub-pages (opportunities list, opportunity detail,
 * recommendations, assessments, evidence, candidates) render instantly
 * without additional HTTP.
 */
export function useDashboard() {
  const qc = useQueryClient();
  const query = useQuery<DashboardBundle>({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: api.dashboard,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const b = query.data;
    if (!b) return;

    qc.setQueryData(["summary"], b.summary);

    if (b.recommendations) {
      qc.setQueryData(["recommendations"], b.recommendations);
      qc.setQueryData(["opportunities"], b.recommendations.opportunities);
    }
    if (b.assessments) qc.setQueryData(["assessments"], b.assessments);
    if (b.evidence) qc.setQueryData(["evidence"], b.evidence);
    if (b.candidates) qc.setQueryData(["candidates"], b.candidates);
    if (b.registry) qc.setQueryData(["registry-bundle"], b.registry);
    if (b.supply_network) qc.setQueryData(["supply-network"], b.supply_network);

    for (const d of b.opportunity_details) {
      qc.setQueryData(["opportunity", d.opportunity.source_key], d);
    }
  }, [qc, query.data]);

  return query;
}
