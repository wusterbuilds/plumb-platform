"use client";

import { useAggregateCost } from "@/lib/queries/metrics";
import { Card } from "@/components/ui/card";

export function CostBreakdown() {
  const { data, isLoading } = useAggregateCost();

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">AI Cost</h3>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !data ? (
        <p className="text-sm text-muted-foreground">No cost data yet</p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Total Cost</p>
              <p className="text-xl font-mono font-semibold">${data.total_cost_usd.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Calls</p>
              <p className="text-xl font-mono font-semibold">{data.total_calls}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">Input Tokens</p>
              <p className="font-mono">{(data.total_input_tokens / 1000).toFixed(0)}K</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Output Tokens</p>
              <p className="font-mono">{(data.total_output_tokens / 1000).toFixed(0)}K</p>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
