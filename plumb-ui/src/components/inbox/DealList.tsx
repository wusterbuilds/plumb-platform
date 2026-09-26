"use client";

import { useState, useMemo } from "react";
import { useDeals } from "@/lib/queries/deals";
import { statusCategory, type StatusCategory } from "@/lib/format";
import { DealCard } from "./DealCard";
import { InboxFilters, type FilterTab } from "./InboxFilters";

export function DealList() {
  const { data, isLoading } = useDeals();
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");

  const deals = data?.deals ?? [];

  const counts = useMemo(() => {
    const c: Record<FilterTab, number> = {
      all: deals.length,
      needs_review: 0,
      processing: 0,
      complete: 0,
      error: 0,
      inactive: 0,
    };
    for (const d of deals) {
      const cat = statusCategory(d.status);
      c[cat]++;
    }
    return c;
  }, [deals]);

  const filtered = useMemo(() => {
    let list = deals;

    if (activeTab !== "all") {
      list = list.filter((d) => statusCategory(d.status) === activeTab);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (d) =>
          d.property_name?.toLowerCase().includes(q) ||
          d.property_address?.toLowerCase().includes(q),
      );
    }

    return list;
  }, [deals, activeTab, search]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-4 animate-pulse">
            <div className="h-5 bg-muted rounded w-48" />
            <div className="h-4 bg-muted rounded w-64 mt-2" />
            <div className="h-3 bg-muted rounded w-32 mt-2" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <InboxFilters
        activeTab={activeTab}
        onTabChange={setActiveTab}
        search={search}
        onSearchChange={setSearch}
        counts={counts}
      />

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          {deals.length === 0
            ? "No deals yet. Create your first deal to get started."
            : "No deals match your filters."}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((deal) => (
            <DealCard key={deal.id} deal={deal} />
          ))}
        </div>
      )}
    </div>
  );
}
