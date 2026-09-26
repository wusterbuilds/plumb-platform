"use client";

import { cn } from "@/lib/utils";
import type { FlagColor } from "@/lib/types";

interface ConfidenceMeterProps {
  score: number | null;
  flag: FlagColor;
}

export function ConfidenceMeter({ score, flag }: ConfidenceMeterProps) {
  if (score == null) return <span className="text-xs text-muted-foreground">N/A</span>;

  const dots = 5;
  const filled = Math.round(score * dots);

  const dotColor = {
    red: "bg-red-500",
    yellow: "bg-amber-500",
    green: "bg-green-500",
  }[flag];

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex gap-0.5">
        {Array.from({ length: dots }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-2 w-2 rounded-full",
              i < filled ? dotColor : "bg-muted-foreground/20",
            )}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground">{(score * 100).toFixed(0)}%</span>
    </div>
  );
}
