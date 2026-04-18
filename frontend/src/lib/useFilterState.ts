"use client";

import { useCallback, useState } from "react";

export type SupplyFilters = {
  tab: string;
  search: string;
  companyIds: number[];
  supplierIds: number[];
  families: string[];
  productType: "both" | "finished-good" | "raw-material";
};

export const DEFAULT_FILTERS: SupplyFilters = {
  tab: "suppliers",
  search: "",
  companyIds: [],
  supplierIds: [],
  families: [],
  productType: "both",
};

export function useFilterState(initial: Partial<SupplyFilters> = {}) {
  const [filters, setFilters] = useState<SupplyFilters>({
    ...DEFAULT_FILTERS,
    ...initial,
  });

  const update = useCallback((patch: Partial<SupplyFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  }, []);

  const toggleInList = useCallback(
    <K extends "companyIds" | "supplierIds" | "families">(
      key: K,
      value: SupplyFilters[K][number],
    ) => {
      setFilters((prev) => {
        const list = prev[key] as Array<typeof value>;
        const exists = list.includes(value);
        const next = exists ? list.filter((v) => v !== value) : [...list, value];
        return { ...prev, [key]: next } as SupplyFilters;
      });
    },
    [],
  );

  const reset = useCallback(() => setFilters(DEFAULT_FILTERS), []);

  return { filters, update, toggleInList, reset };
}
