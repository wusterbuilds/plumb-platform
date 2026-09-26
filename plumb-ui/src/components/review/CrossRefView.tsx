"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fieldLabel } from "@/lib/field-labels";
import type { CrossReference, CrossRefResolution } from "@/lib/types";

interface CrossRefViewProps {
  crossRef: CrossReference;
  onResolve: (resolution: CrossRefResolution) => void;
  isPending: boolean;
}

export function CrossRefView({ crossRef, onResolve, isPending }: CrossRefViewProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Cross-Reference: {crossRef.rule_name}</h3>

      <div className="grid grid-cols-2 gap-4">
        {/* Field A */}
        <div className="bg-muted/50 rounded-lg p-4">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {fieldLabel(crossRef.field_a)}
          </h4>
          <div className="text-xl font-semibold">{crossRef.field_a_value ?? "--"}</div>
        </div>

        {/* Field B */}
        <div className="bg-muted/50 rounded-lg p-4">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {fieldLabel(crossRef.field_b)}
          </h4>
          <div className="text-xl font-semibold">{crossRef.field_b_value ?? "--"}</div>
        </div>
      </div>

      {/* Delta info */}
      <div className="flex items-center gap-3 text-sm">
        <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
          {crossRef.result}
        </Badge>
        {crossRef.delta && <span className="text-muted-foreground">Delta: {crossRef.delta}</span>}
        {crossRef.tolerance_applied && (
          <span className="text-muted-foreground">
            Tolerance: {crossRef.tolerance_applied}
          </span>
        )}
      </div>

      {/* Resolution buttons */}
      {!crossRef.resolution && (
        <div className="space-y-2 pt-2">
          <Button
            className="w-full"
            onClick={() => onResolve("field_a_correct")}
            disabled={isPending}
          >
            {fieldLabel(crossRef.field_a)} is correct
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => onResolve("field_b_correct")}
            disabled={isPending}
          >
            {fieldLabel(crossRef.field_b)} is correct
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => onResolve("both_wrong")}
            disabled={isPending}
          >
            Both wrong (override both)
          </Button>
        </div>
      )}

      {crossRef.resolution && (
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          Resolved: {crossRef.resolution.replace(/_/g, " ")}
        </Badge>
      )}
    </div>
  );
}
