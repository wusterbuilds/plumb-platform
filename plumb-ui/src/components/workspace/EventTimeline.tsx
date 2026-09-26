"use client";

import { useState } from "react";
import { useEvents } from "@/lib/queries/events";
import { timeAgo } from "@/lib/format";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { Event as DealEvent } from "@/lib/types";

function eventLabel(e: DealEvent): string {
  const labels: Record<string, string> = {
    deal_created: "Deal created",
    doc_uploaded: "Document uploaded",
    doc_classified: "Document classified",
    doc_parsed: "Document parsed",
    extraction_started: "Extraction started",
    extraction_completed: "Extraction completed",
    extraction_failed: "Extraction failed",
    field_reviewed: "Field reviewed",
    field_overridden: "Field overridden",
    cross_ref_resolved: "Cross-ref resolved",
    state_transition: "State transition",
    backward_transition: "Sent back",
    deal_updated: "Deal updated",
    checkpoint_released: "Checkpoint released",
    deal_on_hold: "Put on hold",
    deal_killed: "Deal killed",
  };
  return labels[e.event_type] || e.event_type.replace(/_/g, " ");
}

function eventDetail(e: DealEvent): string | null {
  if (!e.payload) return null;
  if (e.event_type === "doc_uploaded") return e.payload.filename as string;
  if (e.event_type === "field_overridden") return e.payload.field_name as string;
  if (e.event_type === "field_reviewed") return e.payload.field_name as string;
  if (e.event_type === "state_transition") return `${e.payload.from} -> ${e.payload.to}`;
  return null;
}

interface EventTimelineProps {
  dealId: string;
}

export function EventTimeline({ dealId }: EventTimelineProps) {
  const { data } = useEvents(dealId);
  const [expanded, setExpanded] = useState(false);
  const events = data?.events ?? [];

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        Events ({events.length})
      </button>

      {expanded && (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {[...events].reverse().map((evt) => {
            const detail = eventDetail(evt);
            return (
              <div key={evt.id} className="flex items-start gap-2 px-2 py-1 text-xs">
                <span className="text-muted-foreground whitespace-nowrap">
                  {timeAgo(evt.timestamp)}
                </span>
                <span className="text-foreground">
                  {eventLabel(evt)}
                  {detail && (
                    <span className="text-muted-foreground ml-1">({detail})</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
