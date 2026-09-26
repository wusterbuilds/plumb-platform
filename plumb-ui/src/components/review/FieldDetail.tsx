"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { OverrideForm } from "./OverrideForm";
import { fieldLabel } from "@/lib/field-labels";
import type { ExtractedValue } from "@/lib/types";
import { cn } from "@/lib/utils";

interface FieldDetailProps {
  field: ExtractedValue;
  allValues: ExtractedValue[];
  onConfirm: () => void;
  onOverride: (value: string, reason: string) => void;
  onSkip: () => void;
  isConfirming: boolean;
  isOverriding: boolean;
}

export function FieldDetail({
  field,
  allValues,
  onConfirm,
  onOverride,
  onSkip,
  isConfirming,
  isOverriding,
}: FieldDetailProps) {
  const [overrideMode, setOverrideMode] = useState(false);

  // Find corroborating values from other docs
  const corroborations = allValues.filter(
    (v) =>
      v.field_name === field.field_name &&
      v.id !== field.id &&
      v.source_doc_id !== field.source_doc_id,
  );

  const flagBadge = {
    red: "bg-red-100 text-red-800 border-red-200",
    yellow: "bg-amber-100 text-amber-800 border-amber-200",
    green: "bg-green-100 text-green-800 border-green-200",
  }[field.flag];

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">{fieldLabel(field.field_name)}</h3>

      {/* Extracted value */}
      <div className="bg-muted/50 rounded-lg p-4">
        <div className="text-2xl font-semibold">
          {field.override_value ?? field.value ?? "--"}
        </div>
        <div className="flex items-center gap-3 mt-2">
          <ConfidenceMeter score={field.confidence_score} flag={field.flag} />
          <Badge variant="outline" className={cn("text-xs", flagBadge)}>
            {field.flag}
          </Badge>
        </div>
      </div>

      {/* Source attribution */}
      <div>
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
          Source
        </h4>
        <p className="text-sm">
          {field.source_page != null
            ? `Page ${field.source_page}`
            : "Unknown page"}
        </p>
      </div>

      {/* Source snippet */}
      {field.source_text_snippet && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
            Source Text
          </h4>
          <blockquote className="text-sm border-l-2 border-muted-foreground/30 pl-3 italic text-muted-foreground">
            {field.source_text_snippet}
          </blockquote>
        </div>
      )}

      {/* Corroboration */}
      {corroborations.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
            Also found in
          </h4>
          <div className="space-y-1">
            {corroborations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "text-sm flex items-center gap-2",
                  c.value !== field.value && "text-amber-700",
                )}
              >
                <span>Page {c.source_page ?? "?"}</span>
                <span className="font-medium">({c.value})</span>
                {c.value !== field.value && (
                  <Badge variant="outline" className="text-[10px] text-amber-700 border-amber-200">
                    Mismatch
                  </Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      {!overrideMode ? (
        <div className="space-y-2 pt-2">
          <Button
            className="w-full"
            onClick={onConfirm}
            disabled={isConfirming}
          >
            Confirm (Enter)
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={() => setOverrideMode(true)}
          >
            Override (O)
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={onSkip}
          >
            Skip (S)
          </Button>
        </div>
      ) : (
        <OverrideForm
          currentValue={field.value}
          onSubmit={(value, reason) => {
            onOverride(value, reason);
            setOverrideMode(false);
          }}
          onCancel={() => setOverrideMode(false)}
          isPending={isOverriding}
        />
      )}
    </div>
  );
}
