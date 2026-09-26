"use client";

import { useBottlenecks } from "@/lib/queries/metrics";
import { Card } from "@/components/ui/card";

export function BottleneckView() {
  const { data, isLoading } = useBottlenecks();

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">Current Bottlenecks</h3>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !data?.bottlenecks?.length ? (
        <p className="text-sm text-muted-foreground">No deals currently waiting</p>
      ) : (
        <div className="space-y-2">
          {data.bottlenecks.map((b) => (
            <div key={b.stage_name} className="flex items-center justify-between text-sm">
              <span>{b.stage_name}</span>
              <span className="font-mono font-medium">
                {b.waiting_count} deal{b.waiting_count !== 1 ? "s" : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
