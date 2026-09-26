"use client";

import { cn } from "@/lib/utils";
import { fieldLabel } from "@/lib/field-labels";
import type { FlagColor } from "@/lib/types";
import { Check, ArrowRight } from "lucide-react";

interface FlagQueueItemProps {
  fieldName: string;
  value: string | null;
  flag: FlagColor;
  isActive: boolean;
  isResolved: boolean;
  onClick: () => void;
}

export function FlagQueueItem({
  fieldName,
  value,
  flag,
  isActive,
  isResolved,
  onClick,
}: FlagQueueItemProps) {
  const dotColor = {
    red: "bg-red-500",
    yellow: "bg-amber-500",
    green: "bg-green-500",
  }[flag];

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-left transition-colors",
        isActive && "bg-primary/10",
        isResolved && "opacity-50",
        !isActive && !isResolved && "hover:bg-muted/50",
      )}
    >
      {isActive && <ArrowRight className="h-3 w-3 text-primary shrink-0" />}
      {!isActive && isResolved && <Check className="h-3 w-3 text-green-600 shrink-0" />}
      {!isActive && !isResolved && (
        <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} />
      )}
      <span className={cn("truncate flex-1", isActive && "font-medium")}>
        {fieldLabel(fieldName)}
      </span>
    </button>
  );
}
