"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  Boxes,
  Building2,
  Factory,
  GitMerge,
  Link2,
  PackageSearch,
  Truck,
} from "lucide-react";
import { DataTable, type ColumnDef } from "@/components/data-table";
import { FilterBar } from "@/components/filter-bar";
import { HorizontalBars } from "@/components/horizontal-bars";
import { SupplierBadge } from "@/components/supplier-badge";
import { useFilterState } from "@/lib/useFilterState";
import { cn, prettyKey } from "@/lib/utils";
import type {
  CompanyNode,
  CompanySupplierEdge,
  ProductNode,
  ProductRawEdge,
  SupplierNode,
  SupplierProductEdge,
  SupplierRawEdge,
  SupplyNetworkBundle,
} from "@/lib/schema";

type TabKey =
  | "suppliers"
  | "procurers"
  | "products"
  | "company-supplier"
  | "supplier-product"
  | "product-raw"
  | "supplier-raw";

type TabDef = {
  key: TabKey;
  label: string;
  icon: React.ReactNode;
};

const TABS: TabDef[] = [
  { key: "suppliers", label: "Suppliers", icon: <Truck className="h-4 w-4" /> },
  {
    key: "procurers",
    label: "Procurers",
    icon: <Building2 className="h-4 w-4" />,
  },
  { key: "products", label: "Products", icon: <Boxes className="h-4 w-4" /> },
  {
    key: "company-supplier",
    label: "Procurer ↔ Supplier",
    icon: <GitMerge className="h-4 w-4" />,
  },
  {
    key: "supplier-product",
    label: "Supplier ↔ Product",
    icon: <Link2 className="h-4 w-4" />,
  },
  {
    key: "product-raw",
    label: "Product ↔ Raw",
    icon: <Factory className="h-4 w-4" />,
  },
  {
    key: "supplier-raw",
    label: "Supplier ↔ Raw",
    icon: <PackageSearch className="h-4 w-4" />,
  },
];

export function SupplyNetworkSection({ bundle }: { bundle: SupplyNetworkBundle }) {
  const { filters, update, toggleInList, reset } = useFilterState({
    tab: "suppliers",
  });
  const activeTab = (filters.tab as TabKey) ?? "suppliers";

  const soleSourceSet = useMemo(
    () => new Set(bundle.aggregates.sole_source_raw_ids),
    [bundle.aggregates.sole_source_raw_ids],
  );

  const selectedCompanies = useMemo(
    () => new Set(filters.companyIds.map(String)),
    [filters.companyIds],
  );
  const selectedSuppliers = useMemo(
    () => new Set(filters.supplierIds.map(String)),
    [filters.supplierIds],
  );
  const selectedFamilies = useMemo(
    () => new Set(filters.families),
    [filters.families],
  );
  const searchLower = filters.search.trim().toLowerCase();

  const companyOptions = useMemo(
    () =>
      bundle.companies
        .slice()
        .sort((a, b) => b.supplier_count - a.supplier_count)
        .slice(0, 40)
        .map((c) => ({
          value: String(c.id),
          label: c.name,
          count: c.supplier_count,
        })),
    [bundle.companies],
  );

  const supplierOptions = useMemo(
    () =>
      bundle.suppliers
        .slice()
        .sort((a, b) => b.product_count - a.product_count)
        .slice(0, 40)
        .map((s) => ({
          value: String(s.id),
          label: s.name,
          count: s.product_count,
        })),
    [bundle.suppliers],
  );

  const familyOptions = useMemo(() => {
    const counter = new Map<string, number>();
    for (const p of bundle.products) {
      if (p.ingredient_family) {
        counter.set(
          p.ingredient_family,
          (counter.get(p.ingredient_family) ?? 0) + 1,
        );
      }
    }
    return Array.from(counter.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([v, c]) => ({ value: v, label: v, count: c }));
  }, [bundle.products]);

  /* filtered datasets */

  const suppliers = useMemo(() => {
    return bundle.suppliers.filter((s) => {
      if (selectedSuppliers.size > 0 && !selectedSuppliers.has(String(s.id))) {
        return false;
      }
      if (selectedFamilies.size > 0) {
        const hit = s.top_families.some((f) => selectedFamilies.has(f));
        if (!hit) return false;
      }
      if (searchLower && !s.name.toLowerCase().includes(searchLower)) {
        return false;
      }
      return true;
    });
  }, [bundle.suppliers, selectedSuppliers, selectedFamilies, searchLower]);

  const procurers = useMemo(() => {
    return bundle.companies.filter((c) => {
      if (selectedCompanies.size > 0 && !selectedCompanies.has(String(c.id))) {
        return false;
      }
      if (searchLower && !c.name.toLowerCase().includes(searchLower)) {
        return false;
      }
      return true;
    });
  }, [bundle.companies, selectedCompanies, searchLower]);

  const products = useMemo(() => {
    return bundle.products.filter((p) => {
      if (filters.productType !== "both" && p.type !== filters.productType) {
        return false;
      }
      if (
        selectedCompanies.size > 0 &&
        !selectedCompanies.has(String(p.company_id))
      ) {
        return false;
      }
      if (
        selectedFamilies.size > 0 &&
        (!p.ingredient_family || !selectedFamilies.has(p.ingredient_family))
      ) {
        return false;
      }
      if (searchLower) {
        const hay = `${p.sku} ${p.normalized_name ?? ""} ${p.canonical_key ?? ""}`.toLowerCase();
        if (!hay.includes(searchLower)) return false;
      }
      return true;
    });
  }, [
    bundle.products,
    filters.productType,
    selectedCompanies,
    selectedFamilies,
    searchLower,
  ]);

  const companySupplierEdges = useMemo(() => {
    return bundle.company_supplier_edges.filter((e) => {
      if (
        selectedCompanies.size > 0 &&
        !selectedCompanies.has(String(e.company_id))
      ) {
        return false;
      }
      if (
        selectedSuppliers.size > 0 &&
        !selectedSuppliers.has(String(e.supplier_id))
      ) {
        return false;
      }
      if (searchLower) {
        const hay = `${e.company_name} ${e.supplier_name}`.toLowerCase();
        if (!hay.includes(searchLower)) return false;
      }
      return true;
    });
  }, [
    bundle.company_supplier_edges,
    selectedCompanies,
    selectedSuppliers,
    searchLower,
  ]);

  const supplierProductEdges = useMemo(() => {
    return bundle.supplier_product_edges.filter((e) => {
      if (
        selectedCompanies.size > 0 &&
        !selectedCompanies.has(String(e.company_id))
      ) {
        return false;
      }
      if (
        selectedSuppliers.size > 0 &&
        !selectedSuppliers.has(String(e.supplier_id))
      ) {
        return false;
      }
      if (
        selectedFamilies.size > 0 &&
        (!e.ingredient_family || !selectedFamilies.has(e.ingredient_family))
      ) {
        return false;
      }
      if (searchLower) {
        const hay = `${e.supplier_name} ${e.company_name} ${e.product_sku} ${e.canonical_key ?? ""}`.toLowerCase();
        if (!hay.includes(searchLower)) return false;
      }
      return true;
    });
  }, [
    bundle.supplier_product_edges,
    selectedCompanies,
    selectedSuppliers,
    selectedFamilies,
    searchLower,
  ]);

  const productRawEdges = useMemo(() => {
    return bundle.product_raw_edges.filter((e) => {
      if (
        selectedCompanies.size > 0 &&
        !selectedCompanies.has(String(e.company_id))
      ) {
        return false;
      }
      if (
        selectedFamilies.size > 0 &&
        (!e.ingredient_family || !selectedFamilies.has(e.ingredient_family))
      ) {
        return false;
      }
      if (searchLower) {
        const hay = `${e.finished_sku} ${e.raw_sku} ${e.company_name} ${e.canonical_key ?? ""}`.toLowerCase();
        if (!hay.includes(searchLower)) return false;
      }
      return true;
    });
  }, [
    bundle.product_raw_edges,
    selectedCompanies,
    selectedFamilies,
    searchLower,
  ]);

  const supplierRawEdges = useMemo(() => {
    return bundle.supplier_raw_edges.filter((e) => {
      if (
        selectedSuppliers.size > 0 &&
        !selectedSuppliers.has(String(e.supplier_id))
      ) {
        return false;
      }
      if (
        selectedFamilies.size > 0 &&
        (!e.ingredient_family || !selectedFamilies.has(e.ingredient_family))
      ) {
        return false;
      }
      if (searchLower) {
        const hay = `${e.supplier_name} ${e.raw_sku} ${e.canonical_key}`.toLowerCase();
        if (!hay.includes(searchLower)) return false;
      }
      return true;
    });
  }, [
    bundle.supplier_raw_edges,
    selectedSuppliers,
    selectedFamilies,
    searchLower,
  ]);

  /* popularity bar rows */

  const topSuppliersByProducts = useMemo(
    () =>
      bundle.suppliers
        .slice()
        .sort((a, b) => b.product_count - a.product_count)
        .slice(0, 10)
        .map((s) => ({
          key: String(s.id),
          label: s.name,
          value: s.product_count,
        })),
    [bundle.suppliers],
  );

  const topSuppliersByCompanies = useMemo(
    () =>
      bundle.suppliers
        .slice()
        .sort((a, b) => b.company_count - a.company_count)
        .slice(0, 10)
        .map((s) => ({
          key: String(s.id),
          label: s.name,
          value: s.company_count,
        })),
    [bundle.suppliers],
  );

  const soleSourceCount = bundle.aggregates.sole_source_raw_ids.length;

  /* column definitions per tab */

  const supplierColumns: ColumnDef<SupplierNode>[] = [
    {
      key: "name",
      header: "Supplier",
      sortBy: (r) => r.name,
      cell: (r) => (
        <div className="flex flex-col gap-1">
          <span className="font-medium">{r.name}</span>
          <div className="flex flex-wrap gap-1">
            {r.top_families.slice(0, 3).map((f) => (
              <span key={f} className="chip text-[10px]">
                {prettyKey(f)}
              </span>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: "product_count",
      header: "Products",
      sortBy: (r) => r.product_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.product_count}</span>,
    },
    {
      key: "canonical_key_count",
      header: "Canonical keys",
      sortBy: (r) => r.canonical_key_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.canonical_key_count}</span>,
    },
    {
      key: "company_count",
      header: "Procurers",
      sortBy: (r) => r.company_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.company_count}</span>,
    },
    {
      key: "sole_source_count",
      header: "Sole-source",
      sortBy: (r) => r.sole_source_count,
      align: "right",
      cell: (r) =>
        r.sole_source_count > 0 ? (
          <span className="chip border-warn/40 bg-warn/10 text-warn">
            <AlertTriangle className="h-3 w-3" />
            {r.sole_source_count}
          </span>
        ) : (
          <span className="font-mono text-fg-muted">0</span>
        ),
    },
  ];

  const procurerColumns: ColumnDef<CompanyNode>[] = [
    {
      key: "name",
      header: "Procurer",
      sortBy: (r) => r.name,
      cell: (r) => <span className="font-medium">{r.name}</span>,
    },
    {
      key: "finished_good_count",
      header: "Finished goods",
      sortBy: (r) => r.finished_good_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.finished_good_count}</span>,
    },
    {
      key: "raw_material_count",
      header: "Raw materials",
      sortBy: (r) => r.raw_material_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.raw_material_count}</span>,
    },
    {
      key: "supplier_count",
      header: "Suppliers",
      sortBy: (r) => r.supplier_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.supplier_count}</span>,
    },
  ];

  const productColumns: ColumnDef<ProductNode>[] = [
    {
      key: "sku",
      header: "Product",
      sortBy: (r) => r.normalized_name ?? r.sku,
      cell: (r) => (
        <div className="flex flex-col">
          <span className="font-medium">
            {r.normalized_name ?? r.sku}
          </span>
          <span className="text-[11px] text-fg-muted">
            {r.sku}
            {r.canonical_key ? (
              <>
                {" · "}
                <span className="font-mono text-accent/80">
                  {r.canonical_key}
                </span>
              </>
            ) : null}
          </span>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      sortBy: (r) => r.type,
      cell: (r) => (
        <span
          className={cn(
            "chip",
            r.type === "finished-good"
              ? "border-accent/40 bg-accent/10 text-accent"
              : "border-good/40 bg-good/10 text-good",
          )}
        >
          {r.type === "finished-good" ? "finished" : "raw"}
        </span>
      ),
    },
    {
      key: "company",
      header: "Owned by",
      sortBy: (r) => r.company_name,
      cell: (r) => <span>{r.company_name}</span>,
    },
    {
      key: "family",
      header: "Family / role",
      sortBy: (r) => r.ingredient_family ?? "",
      cell: (r) =>
        r.ingredient_family || r.functional_role ? (
          <div className="flex flex-wrap gap-1">
            {r.ingredient_family ? (
              <span className="chip">{prettyKey(r.ingredient_family)}</span>
            ) : null}
            {r.functional_role ? (
              <span className="chip border-accent/40 bg-accent/10 text-accent">
                {prettyKey(r.functional_role)}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-fg-muted">—</span>
        ),
    },
    {
      key: "supplier_count",
      header: "Suppliers",
      sortBy: (r) => r.supplier_count ?? -1,
      align: "right",
      cell: (r) =>
        r.type === "raw-material" ? (
          <span className="font-mono">{r.supplier_count ?? 0}</span>
        ) : (
          <span className="font-mono text-fg-muted">—</span>
        ),
    },
    {
      key: "bom_count",
      header: "BOM edges",
      sortBy: (r) => r.bom_count ?? -1,
      align: "right",
      cell: (r) =>
        r.type === "finished-good" ? (
          <span className="font-mono">{r.bom_count ?? 0}</span>
        ) : (
          <span className="font-mono text-fg-muted">—</span>
        ),
    },
  ];

  const companySupplierColumns: ColumnDef<CompanySupplierEdge>[] = [
    {
      key: "company",
      header: "Procurer",
      sortBy: (r) => r.company_name,
      cell: (r) => <span className="font-medium">{r.company_name}</span>,
    },
    {
      key: "supplier",
      header: "Supplier",
      sortBy: (r) => r.supplier_name,
      cell: (r) => <SupplierBadge name={r.supplier_name} />,
    },
    {
      key: "shared_raw_count",
      header: "Shared raw materials",
      sortBy: (r) => r.shared_raw_count,
      align: "right",
      cell: (r) => <span className="font-mono">{r.shared_raw_count}</span>,
    },
    {
      key: "canonical_keys",
      header: "Canonical keys (sample)",
      cell: (r) => (
        <div className="flex flex-wrap gap-1">
          {r.canonical_keys.length === 0 ? (
            <span className="text-[11px] text-fg-muted">—</span>
          ) : (
            r.canonical_keys.slice(0, 4).map((k) => (
              <span key={k} className="chip font-mono text-[10px]">
                {k}
              </span>
            ))
          )}
          {r.canonical_keys.length > 4 ? (
            <span className="chip text-[10px]">
              +{r.canonical_keys.length - 4}
            </span>
          ) : null}
        </div>
      ),
    },
  ];

  const supplierProductColumns: ColumnDef<SupplierProductEdge>[] = [
    {
      key: "supplier",
      header: "Supplier",
      sortBy: (r) => r.supplier_name,
      cell: (r) => (
        <SupplierBadge
          name={r.supplier_name}
          soleSource={soleSourceSet.has(r.product_id)}
        />
      ),
    },
    {
      key: "product",
      header: "Product (SKU)",
      sortBy: (r) => r.product_sku,
      cell: (r) => (
        <div className="flex flex-col">
          <span className="font-mono text-[12px]">{r.product_sku}</span>
          {r.canonical_key ? (
            <span className="font-mono text-[10px] text-accent/80">
              {r.canonical_key}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      key: "company",
      header: "Procurer",
      sortBy: (r) => r.company_name,
      cell: (r) => <span>{r.company_name}</span>,
    },
    {
      key: "family",
      header: "Family / role",
      sortBy: (r) => r.ingredient_family ?? "",
      cell: (r) =>
        r.ingredient_family || r.functional_role ? (
          <div className="flex flex-wrap gap-1">
            {r.ingredient_family ? (
              <span className="chip">{prettyKey(r.ingredient_family)}</span>
            ) : null}
            {r.functional_role ? (
              <span className="chip border-accent/40 bg-accent/10 text-accent">
                {prettyKey(r.functional_role)}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-fg-muted">—</span>
        ),
    },
  ];

  const productRawColumns: ColumnDef<ProductRawEdge>[] = [
    {
      key: "finished",
      header: "Finished product",
      sortBy: (r) => r.finished_sku,
      cell: (r) => (
        <div className="flex flex-col">
          <span className="font-mono text-[12px]">{r.finished_sku}</span>
          <span className="text-[11px] text-fg-muted">{r.company_name}</span>
        </div>
      ),
    },
    {
      key: "raw",
      header: "Raw material",
      sortBy: (r) => r.raw_sku,
      cell: (r) => (
        <div className="flex flex-col">
          <span className="font-mono text-[12px]">{r.raw_sku}</span>
          {r.canonical_key ? (
            <span className="font-mono text-[10px] text-accent/80">
              {r.canonical_key}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      key: "family",
      header: "Family",
      sortBy: (r) => r.ingredient_family ?? "",
      cell: (r) =>
        r.ingredient_family ? (
          <span className="chip">{prettyKey(r.ingredient_family)}</span>
        ) : (
          <span className="text-fg-muted">—</span>
        ),
    },
  ];

  const supplierRawColumns: ColumnDef<SupplierRawEdge>[] = [
    {
      key: "supplier",
      header: "Supplier",
      sortBy: (r) => r.supplier_name,
      cell: (r) => (
        <SupplierBadge
          name={r.supplier_name}
          soleSource={soleSourceSet.has(r.raw_product_id)}
        />
      ),
    },
    {
      key: "raw_sku",
      header: "Raw SKU",
      sortBy: (r) => r.raw_sku,
      cell: (r) => (
        <span className="font-mono text-[12px]">{r.raw_sku}</span>
      ),
    },
    {
      key: "canonical_key",
      header: "Canonical key",
      sortBy: (r) => r.canonical_key,
      cell: (r) => (
        <span className="font-mono text-[11px] text-accent/80">
          {r.canonical_key}
        </span>
      ),
    },
    {
      key: "family",
      header: "Family / role",
      sortBy: (r) => r.ingredient_family ?? "",
      cell: (r) =>
        r.ingredient_family || r.functional_role ? (
          <div className="flex flex-wrap gap-1">
            {r.ingredient_family ? (
              <span className="chip">{prettyKey(r.ingredient_family)}</span>
            ) : null}
            {r.functional_role ? (
              <span className="chip border-accent/40 bg-accent/10 text-accent">
                {prettyKey(r.functional_role)}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-fg-muted">—</span>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* Popularity + risk banner */}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr,1fr,auto]">
        <HorizontalBars
          title="Top suppliers by product count"
          tone="accent"
          rows={topSuppliersByProducts}
        />
        <HorizontalBars
          title="Top suppliers by procurer reach"
          tone="good"
          rows={topSuppliersByCompanies}
        />
        <div
          className={cn(
            "card flex min-w-[12rem] flex-col justify-center gap-1 px-4 py-4",
            soleSourceCount > 0
              ? "border-warn/40 bg-warn/5"
              : "border-good/40 bg-good/5",
          )}
        >
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-fg-muted">
            <AlertTriangle
              className={cn(
                "h-3.5 w-3.5",
                soleSourceCount > 0 ? "text-warn" : "text-good",
              )}
            />
            Sole-source risk
          </div>
          <div className="text-3xl font-semibold text-fg">{soleSourceCount}</div>
          <div className="text-xs text-fg-muted">
            raw materials served by a single supplier
          </div>
        </div>
      </div>

      <FilterBar
        search={filters.search}
        onSearchChange={(v) => update({ search: v })}
        companyOptions={companyOptions}
        selectedCompanies={selectedCompanies}
        onToggleCompany={(v) => toggleInList("companyIds", Number(v))}
        supplierOptions={supplierOptions}
        selectedSuppliers={selectedSuppliers}
        onToggleSupplier={(v) => toggleInList("supplierIds", Number(v))}
        familyOptions={familyOptions}
        selectedFamilies={selectedFamilies}
        onToggleFamily={(v) => toggleInList("families", v)}
        onReset={reset}
      />

      <div className="flex flex-wrap items-center gap-1.5 border-b border-border pb-2">
        {TABS.map((t) => {
          const active = t.key === activeTab;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => update({ tab: t.key })}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "bg-accent/15 text-accent"
                  : "text-fg-muted hover:bg-bg-muted hover:text-fg",
              )}
            >
              {t.icon}
              {t.label}
            </button>
          );
        })}
        {activeTab === "products" ? (
          <div className="ml-auto inline-flex items-center gap-1 text-[11px]">
            <span className="text-fg-muted">type:</span>
            {(["both", "finished-good", "raw-material"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => update({ productType: v })}
                className={cn(
                  "chip",
                  filters.productType === v
                    ? "border-accent/60 bg-accent/15 text-accent"
                    : "",
                )}
              >
                {v === "both" ? "all" : v === "finished-good" ? "finished" : "raw"}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {activeTab === "suppliers" ? (
        <DataTable
          columns={supplierColumns}
          rows={suppliers}
          initialSort={{ key: "product_count", dir: "desc" }}
          rowKey={(r) => `sup-${r.id}`}
          onRowClick={(r) => toggleInList("supplierIds", r.id)}
        />
      ) : null}

      {activeTab === "procurers" ? (
        <DataTable
          columns={procurerColumns}
          rows={procurers}
          initialSort={{ key: "supplier_count", dir: "desc" }}
          rowKey={(r) => `co-${r.id}`}
          onRowClick={(r) => toggleInList("companyIds", r.id)}
        />
      ) : null}

      {activeTab === "products" ? (
        <DataTable
          columns={productColumns}
          rows={products}
          initialSort={{ key: "sku", dir: "asc" }}
          rowKey={(r) => `p-${r.id}`}
        />
      ) : null}

      {activeTab === "company-supplier" ? (
        <DataTable
          columns={companySupplierColumns}
          rows={companySupplierEdges}
          initialSort={{ key: "shared_raw_count", dir: "desc" }}
          rowKey={(r) => `cs-${r.company_id}-${r.supplier_id}`}
        />
      ) : null}

      {activeTab === "supplier-product" ? (
        <DataTable
          columns={supplierProductColumns}
          rows={supplierProductEdges}
          initialSort={{ key: "supplier", dir: "asc" }}
          rowKey={(r) => `sp-${r.supplier_id}-${r.product_id}`}
        />
      ) : null}

      {activeTab === "product-raw" ? (
        <DataTable
          columns={productRawColumns}
          rows={productRawEdges}
          initialSort={{ key: "finished", dir: "asc" }}
          rowKey={(r) => `pr-${r.finished_product_id}-${r.raw_product_id}`}
        />
      ) : null}

      {activeTab === "supplier-raw" ? (
        <DataTable
          columns={supplierRawColumns}
          rows={supplierRawEdges}
          initialSort={{ key: "canonical_key", dir: "asc" }}
          rowKey={(r) => `sr-${r.supplier_id}-${r.raw_product_id}`}
        />
      ) : null}
    </div>
  );
}
