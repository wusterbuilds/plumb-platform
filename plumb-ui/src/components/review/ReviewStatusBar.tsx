"use client";

import { Progress } from "@/components/ui/progress";

interface ReviewStatusBarProps {
  current: number;
  total: number;
  resolved: number;
}

export function ReviewStatusBar({ current, total, resolved }: ReviewStatusBarProps) {
  const pct = total > 0 ? (resolved / total) * 100 : 0;

  return (
    <div className="border-t bg-muted/30 px-4 py-2 flex items-center gap-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">&uarr;&darr;</kbd>
        <span>navigate</span>
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Enter</kbd>
        <span>confirm</span>
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">O</kbd>
        <span>override</span>
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">S</kbd>
        <span>skip</span>
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Esc</kbd>
        <span>exit</span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <Progress value={pct} className="w-24 h-1.5" />
        <span>
          {current + 1} of {total}
        </span>
        <span className="text-green-600">{resolved} done</span>
      </div>
    </div>
  );
}
