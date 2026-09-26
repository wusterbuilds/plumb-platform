"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { Deal } from "@/lib/types";
import {
  dealStatusLabel,
  dealTypeLabel,
  formatCurrency,
  statusCategory,
  timeAgo,
} from "@/lib/format";
import { cn } from "@/lib/utils";

function statusBadgeColor(status: Deal["status"]) {
  const cat = statusCategory(status);
  switch (cat) {
    case "needs_review":
      return "bg-red-100 text-red-800 border-red-200";
    case "processing":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "complete":
      return "bg-green-100 text-green-800 border-green-200";
    case "error":
      return "bg-red-100 text-red-800 border-red-200";
    case "inactive":
      return "bg-gray-100 text-gray-600 border-gray-200";
  }
}

function statusDot(status: Deal["status"]) {
  const cat = statusCategory(status);
  switch (cat) {
    case "needs_review":
      return "bg-red-500";
    case "processing":
      return "bg-amber-500";
    case "complete":
      return "bg-green-500";
    case "error":
      return "bg-red-500";
    case "inactive":
      return "bg-gray-400";
  }
}

interface DealCardProps {
  deal: Deal;
}

export function DealCard({ deal }: DealCardProps) {
  const capitalAsk = deal.typed_extension?.loan_amount_requested as number | undefined;

  return (
    <Link href={`/deals/${deal.id}`} className="block">
      <div className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <span className={cn("h-2.5 w-2.5 rounded-full", statusDot(deal.status))} />
            <h3 className="font-medium">
              {deal.property_name || deal.property_address || "Untitled Deal"}
            </h3>
          </div>
          <Badge variant="outline" className={cn("text-xs", statusBadgeColor(deal.status))}>
            {dealStatusLabel(deal.status)}
          </Badge>
        </div>

        <div className="mt-1.5 ml-5 flex items-center gap-2 text-sm text-muted-foreground">
          {deal.property_address && (
            <span>{deal.property_address}</span>
          )}
        </div>

        <div className="mt-2 ml-5 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{dealTypeLabel(deal.deal_type)}</span>
          {capitalAsk != null && (
            <>
              <span className="text-border">|</span>
              <span>{formatCurrency(capitalAsk)}</span>
            </>
          )}
          <span className="ml-auto">{timeAgo(deal.updated_at)}</span>
        </div>
      </div>
    </Link>
  );
}
