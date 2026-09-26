"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUpdateAssumptions } from "@/lib/queries/financial";
import type { ModelAssumptions, AssumptionsUpdate } from "@/lib/types";
import { Loader2 } from "lucide-react";

interface AssumptionsEditorProps {
  dealId: string;
  current: ModelAssumptions;
}

const FIELDS: { key: keyof ModelAssumptions; label: string }[] = [
  { key: "cap_rate", label: "Cap Rate" },
  { key: "vacancy_fm", label: "Vacancy (FM)" },
  { key: "vacancy_affordable", label: "Vacancy (Affordable)" },
  { key: "vacancy_retail", label: "Vacancy (Retail)" },
  { key: "mgmt_fee_pct", label: "Management Fee" },
  { key: "assessment_growth", label: "Assessment Growth" },
  { key: "tax_rate_growth", label: "Tax Rate Growth" },
  { key: "discount_rate", label: "Discount Rate" },
];

export function AssumptionsEditor({ dealId, current }: AssumptionsEditorProps) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of FIELDS) {
      init[f.key] = (current[f.key] * 100).toFixed(2);
    }
    return init;
  });

  const updateAssumptions = useUpdateAssumptions(dealId);

  const handleSave = () => {
    const update: AssumptionsUpdate = {};
    for (const f of FIELDS) {
      const parsed = parseFloat(values[f.key]);
      if (!isNaN(parsed) && parsed / 100 !== current[f.key]) {
        (update as Record<string, number>)[f.key] = parsed / 100;
      }
    }
    if (Object.keys(update).length > 0) {
      updateAssumptions.mutate(update);
    }
  };

  const hasChanges = FIELDS.some((f) => {
    const parsed = parseFloat(values[f.key]);
    return !isNaN(parsed) && Math.abs(parsed / 100 - current[f.key]) > 0.00001;
  });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="text-xs text-muted-foreground uppercase tracking-wider">
              {f.label}
            </label>
            <div className="relative mt-1">
              <Input
                type="number"
                step="0.01"
                value={values[f.key]}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [f.key]: e.target.value }))
                }
                className="pr-6 font-mono tabular-nums text-sm"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                %
              </span>
            </div>
          </div>
        ))}
      </div>

      <Button
        onClick={handleSave}
        disabled={!hasChanges || updateAssumptions.isPending}
        size="sm"
      >
        {updateAssumptions.isPending ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
            Recalculating...
          </>
        ) : (
          "Recalculate Model"
        )}
      </Button>
    </div>
  );
}
