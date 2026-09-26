"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { FlagQueueItem } from "./FlagQueueItem";
import type { ExtractedValue, CrossReference } from "@/lib/types";
import { fieldLabel } from "@/lib/field-labels";

export interface QueueItem {
  type: "field" | "crossref";
  id: string;
  fieldName: string;
  flag: "red" | "yellow" | "green";
  isResolved: boolean;
  value: string | null;
}

interface FlagQueueProps {
  items: QueueItem[];
  activeIndex: number;
  onSelect: (index: number) => void;
}

export function FlagQueue({ items, activeIndex, onSelect }: FlagQueueProps) {
  const redItems = items.filter((i) => i.flag === "red" && !i.isResolved);
  const yellowItems = items.filter((i) => i.flag === "yellow" && !i.isResolved);
  const crossRefItems = items.filter((i) => i.type === "crossref" && !i.isResolved);
  const resolvedItems = items.filter((i) => i.isResolved);

  const redCount = redItems.length;
  const yellowCount = yellowItems.length;
  const resolvedCount = resolvedItems.length;

  return (
    <ScrollArea className="h-full">
      <div className="p-3 space-y-1">
        {/* Red flags */}
        {redCount > 0 && (
          <>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 py-1">
              Red ({redCount})
            </h4>
            {items.map((item, idx) => {
              if (item.flag !== "red" || item.isResolved || item.type === "crossref")
                return null;
              return (
                <FlagQueueItem
                  key={item.id}
                  fieldName={item.fieldName}
                  value={item.value}
                  flag={item.flag}
                  isActive={idx === activeIndex}
                  isResolved={item.isResolved}
                  onClick={() => onSelect(idx)}
                />
              );
            })}
          </>
        )}

        {/* Yellow flags */}
        {yellowCount > 0 && (
          <>
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 py-1 mt-2">
              Yellow ({yellowCount})
            </h4>
            {items.map((item, idx) => {
              if (item.flag !== "yellow" || item.isResolved || item.type === "crossref")
                return null;
              return (
                <FlagQueueItem
                  key={item.id}
                  fieldName={item.fieldName}
                  value={item.value}
                  flag={item.flag}
                  isActive={idx === activeIndex}
                  isResolved={item.isResolved}
                  onClick={() => onSelect(idx)}
                />
              );
            })}
          </>
        )}

        {/* Cross-references */}
        {crossRefItems.length > 0 && (
          <>
            <Separator className="my-2" />
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 py-1">
              Cross-refs ({crossRefItems.length})
            </h4>
            {items.map((item, idx) => {
              if (item.type !== "crossref" || item.isResolved) return null;
              return (
                <FlagQueueItem
                  key={item.id}
                  fieldName={item.fieldName}
                  value={item.value}
                  flag="yellow"
                  isActive={idx === activeIndex}
                  isResolved={item.isResolved}
                  onClick={() => onSelect(idx)}
                />
              );
            })}
          </>
        )}

        {/* Resolved */}
        {resolvedCount > 0 && (
          <>
            <Separator className="my-2" />
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 py-1">
              Done ({resolvedCount})
            </h4>
            {items.map((item, idx) => {
              if (!item.isResolved) return null;
              return (
                <FlagQueueItem
                  key={item.id}
                  fieldName={item.fieldName}
                  value={item.value}
                  flag="green"
                  isActive={idx === activeIndex}
                  isResolved={true}
                  onClick={() => onSelect(idx)}
                />
              );
            })}
          </>
        )}
      </div>
    </ScrollArea>
  );
}
