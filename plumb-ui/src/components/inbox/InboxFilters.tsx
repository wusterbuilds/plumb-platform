"use client";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { StatusCategory } from "@/lib/format";
import { Search } from "lucide-react";

type FilterTab = "all" | StatusCategory;

const TABS: { value: FilterTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "needs_review", label: "Needs Review" },
  { value: "processing", label: "Processing" },
  { value: "complete", label: "Complete" },
];

interface InboxFiltersProps {
  activeTab: FilterTab;
  onTabChange: (tab: FilterTab) => void;
  search: string;
  onSearchChange: (s: string) => void;
  counts: Record<FilterTab, number>;
}

export function InboxFilters({
  activeTab,
  onTabChange,
  search,
  onSearchChange,
  counts,
}: InboxFiltersProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => onTabChange(tab.value)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              activeTab === tab.value
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            {tab.label}
            {counts[tab.value] > 0 && (
              <span className="ml-1.5 text-xs opacity-70">{counts[tab.value]}</span>
            )}
          </button>
        ))}
      </div>

      <div className="relative w-64">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search deals..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 h-9"
        />
      </div>
    </div>
  );
}

export type { FilterTab };
