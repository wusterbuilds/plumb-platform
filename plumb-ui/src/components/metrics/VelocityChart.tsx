"use client";

import { useAggregateVelocity } from "@/lib/queries/metrics";
import { Card } from "@/components/ui/card";

function formatDuration(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

const STAGE_LABELS: Record<string, string> = {
  classifying: "Classification",
  extracting: "Extraction",
  extraction_review: "Human Review",
  market_enrichment: "Market Intel",
  model_building: "Financial Model",
  om_drafting: "OM Drafting",
  om_review: "OM Review",
};

export function VelocityChart() {
  const { data, isLoading } = useAggregateVelocity();

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">Stage Velocity</h3>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !data?.stages?.length ? (
        <p className="text-sm text-muted-foreground">No velocity data yet</p>
      ) : (
        <div className="space-y-2">
          {data.stages.map((s) => {
            const maxDuration = Math.max(...data.stages.map((x) => x.avg_duration_seconds));
            const pct = maxDuration > 0 ? (s.avg_duration_seconds / maxDuration) * 100 : 0;
            return (
              <div key={s.stage_name} className="flex items-center gap-2 text-sm">
                <span className="w-28 text-muted-foreground truncate">
                  {STAGE_LABELS[s.stage_name] || s.stage_name}
                </span>
                <div className="flex-1 h-5 bg-muted rounded overflow-hidden">
                  <div
                    className="h-full bg-primary/60 rounded"
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
                <span className="w-14 text-right font-mono text-xs">
                  {formatDuration(s.avg_duration_seconds)}
                </span>
                <span className="w-8 text-right text-muted-foreground text-xs">
                  ({s.count})
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
