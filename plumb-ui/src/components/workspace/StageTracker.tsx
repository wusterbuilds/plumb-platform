"use client";

import { cn } from "@/lib/utils";
import { dealStatusLabel, type StatusCategory, statusCategory } from "@/lib/format";
import type { DealStatus } from "@/lib/types";
import { Check } from "lucide-react";

const PIPELINE_STAGES: DealStatus[] = [
  "docs_received",
  "classifying",
  "extracting",
  "extraction_review",
  "market_enrichment",
  "model_building",
  "om_drafting",
  "om_review",
  "reworking",
];

const SHORT_LABELS: Record<string, string> = {
  docs_received: "Docs",
  classifying: "Classify",
  extracting: "Extract",
  extraction_review: "Review",
  model_building: "Model",
  market_enrichment: "Market",
  om_drafting: "OM Draft",
  om_review: "OM Review",
  reworking: "Reworking",
};

interface StageTrackerProps {
  currentStatus: DealStatus;
}

export function StageTracker({ currentStatus }: StageTrackerProps) {
  const currentIdx = PIPELINE_STAGES.indexOf(currentStatus);

  return (
    <div className="space-y-1">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
        Stage
      </h3>
      {PIPELINE_STAGES.map((stage, i) => {
        const isPast = currentIdx > i;
        const isCurrent = currentIdx === i;
        const isFuture = currentIdx < i;
        // Special statuses (failed, on_hold, dead) highlight the last known pipeline stage
        const isSpecialStatus = currentIdx === -1;

        return (
          <div
            key={stage}
            className={cn(
              "flex items-center gap-2 px-2 py-1 rounded text-sm",
              isCurrent && "bg-primary/10 text-primary font-medium",
              isPast && "text-muted-foreground",
              isFuture && "text-muted-foreground/50",
              isSpecialStatus && "text-muted-foreground/50",
            )}
          >
            <span className="w-4 h-4 flex items-center justify-center">
              {isPast ? (
                <Check className="h-3.5 w-3.5 text-green-600" />
              ) : isCurrent ? (
                <span className="h-2 w-2 rounded-full bg-primary" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
              )}
            </span>
            {SHORT_LABELS[stage] || dealStatusLabel(stage)}
          </div>
        );
      })}

      {/* Show special status if applicable */}
      {(currentStatus === "on_hold" ||
        currentStatus === "dead" ||
        currentStatus === "extraction_failed" ||
        currentStatus === "model_error") && (
        <div className="mt-2 px-2 py-1 rounded bg-destructive/10 text-destructive text-sm font-medium">
          {dealStatusLabel(currentStatus)}
        </div>
      )}
    </div>
  );
}
