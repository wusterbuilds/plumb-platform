"use client";

import { use } from "react";
import Link from "next/link";
import { useDeal } from "@/lib/queries/deals";
import { dealStatusLabel, dealTypeLabel, formatCurrency } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { StageTracker } from "@/components/workspace/StageTracker";
import { DocumentList } from "@/components/workspace/DocumentList";
import { EventTimeline } from "@/components/workspace/EventTimeline";
import { StageSummary } from "@/components/workspace/StageSummary";
import { StageControls } from "@/components/workspace/StageControls";
import { ArrowLeft } from "lucide-react";

export default function DealWorkspacePage({
  params,
}: {
  params: Promise<{ dealId: string }>;
}) {
  const { dealId } = use(params);
  const { data: deal, isLoading } = useDeal(dealId);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Loading deal...
      </div>
    );
  }

  if (!deal) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Deal not found
      </div>
    );
  }

  const capitalAsk = deal.typed_extension?.loan_amount_requested as number | undefined;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold">
                {deal.property_name || deal.property_address || "Untitled Deal"}
              </h1>
              <Badge variant="outline" className="text-xs">
                {dealStatusLabel(deal.status)}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {deal.property_address && <span>{deal.property_address}</span>}
              <span>{dealTypeLabel(deal.deal_type)}</span>
              {capitalAsk != null && <span>{formatCurrency(capitalAsk)}</span>}
            </div>
          </div>
        </div>
      </header>

      {/* Body: sidebar + center */}
      <div className="flex flex-1">
        {/* Left sidebar */}
        <aside className="w-56 border-r p-4 flex flex-col gap-4 shrink-0">
          <StageTracker currentStatus={deal.status} />

          <Separator />

          <DocumentList dealId={deal.id} />

          <Separator />

          <EventTimeline dealId={deal.id} />

          <div className="mt-auto">
            <Separator className="mb-4" />
            <StageControls deal={deal} />
          </div>
        </aside>

        {/* Center content */}
        <main className="flex-1 p-6">
          <StageSummary deal={deal} />
        </main>
      </div>
    </div>
  );
}
