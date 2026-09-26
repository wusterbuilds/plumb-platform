"use client";

import { useAggregateQuality, useFieldAccuracy } from "@/lib/queries/metrics";
import { Card } from "@/components/ui/card";

export function QualityTable() {
  const { data: quality } = useAggregateQuality();
  const { data: fields, isLoading } = useFieldAccuracy();

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">Extraction Quality</h3>

      {quality && (
        <div className="flex gap-6 mb-4 text-sm">
          <div>
            <span className="text-muted-foreground">Override Rate: </span>
            <span className="font-mono font-medium">
              {(quality.override_rate * 100).toFixed(1)}%
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Fields: </span>
            <span className="font-mono">{quality.overridden_fields}/{quality.total_fields}</span>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !fields?.fields?.length ? (
        <p className="text-sm text-muted-foreground">No field data yet</p>
      ) : (
        <div className="space-y-1 max-h-64 overflow-y-auto">
          {fields.fields.slice(0, 15).map((f) => (
            <div key={f.field_name} className="flex items-center gap-2 text-xs">
              <span className="flex-1 truncate">{f.field_name}</span>
              <span className="font-mono w-16 text-right">
                {(f.override_rate * 100).toFixed(0)}%
              </span>
              <span className="text-muted-foreground w-12 text-right">
                {f.overridden}/{f.total}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
