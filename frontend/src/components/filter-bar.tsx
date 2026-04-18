"use client";

import { Search, X } from "lucide-react";
import { cn, prettyKey } from "@/lib/utils";

export type FilterOption = {
  value: string;
  label: string;
  count?: number;
};

function MultiSelectChips({
  label,
  options,
  selected,
  onToggle,
  prettify = false,
}: {
  label: string;
  options: FilterOption[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  prettify?: boolean;
}) {
  if (options.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <div className="text-[11px] uppercase tracking-wide text-fg-muted">
        {label}
        {selected.size > 0 ? (
          <span className="ml-2 text-accent">{selected.size} selected</span>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1">
        {options.map((opt) => {
          const active = selected.has(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggle(opt.value)}
              className={cn(
                "chip transition-colors",
                active
                  ? "border-accent/60 bg-accent/15 text-accent"
                  : "hover:border-accent/40",
              )}
              title={opt.label}
            >
              <span className="max-w-[12rem] truncate">
                {prettify ? prettyKey(opt.label) : opt.label}
              </span>
              {typeof opt.count === "number" ? (
                <span className="text-[10px] text-fg-muted">{opt.count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function FilterBar({
  search,
  onSearchChange,
  companyOptions,
  selectedCompanies,
  onToggleCompany,
  supplierOptions,
  selectedSuppliers,
  onToggleSupplier,
  familyOptions,
  selectedFamilies,
  onToggleFamily,
  onReset,
}: {
  search: string;
  onSearchChange: (v: string) => void;
  companyOptions: FilterOption[];
  selectedCompanies: Set<string>;
  onToggleCompany: (value: string) => void;
  supplierOptions: FilterOption[];
  selectedSuppliers: Set<string>;
  onToggleSupplier: (value: string) => void;
  familyOptions: FilterOption[];
  selectedFamilies: Set<string>;
  onToggleFamily: (value: string) => void;
  onReset: () => void;
}) {
  const anyActive =
    search ||
    selectedCompanies.size > 0 ||
    selectedSuppliers.size > 0 ||
    selectedFamilies.size > 0;
  return (
    <div className="card flex flex-col gap-3 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
          <input
            className="input pl-8"
            placeholder="Search name, SKU, canonical key…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        {anyActive ? (
          <button
            type="button"
            className="btn-ghost"
            onClick={onReset}
            title="Clear all filters"
          >
            <X className="h-4 w-4" /> Clear filters
          </button>
        ) : null}
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <MultiSelectChips
          label="Procurer"
          options={companyOptions}
          selected={selectedCompanies}
          onToggle={onToggleCompany}
        />
        <MultiSelectChips
          label="Supplier"
          options={supplierOptions}
          selected={selectedSuppliers}
          onToggle={onToggleSupplier}
        />
        <MultiSelectChips
          label="Ingredient family"
          options={familyOptions}
          selected={selectedFamilies}
          onToggle={onToggleFamily}
          prettify
        />
      </div>
    </div>
  );
}
