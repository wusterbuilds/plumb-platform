"use client";

import type { ValidationFlag } from "@/lib/types";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";

interface ValidationFlagsProps {
  flags: ValidationFlag[];
  overallAssessment?: string | null;
  summary?: string | null;
}

const severityConfig = {
  critical: {
    icon: <AlertCircle className="h-4 w-4 text-red-500" />,
    bg: "bg-red-50 border-red-200",
    badge: "bg-red-100 text-red-700",
    label: "Critical",
  },
  warning: {
    icon: <AlertTriangle className="h-4 w-4 text-amber-500" />,
    bg: "bg-amber-50 border-amber-200",
    badge: "bg-amber-100 text-amber-700",
    label: "Warning",
  },
  info: {
    icon: <Info className="h-4 w-4 text-blue-500" />,
    bg: "bg-blue-50 border-blue-200",
    badge: "bg-blue-100 text-blue-700",
    label: "Info",
  },
};

const assessmentLabels: Record<string, { label: string; color: string }> = {
  consistent: { label: "Consistent", color: "text-green-700 bg-green-100" },
  minor_discrepancies: { label: "Minor Discrepancies", color: "text-amber-700 bg-amber-100" },
  material_concerns: { label: "Material Concerns", color: "text-orange-700 bg-orange-100" },
  significant_red_flags: { label: "Red Flags", color: "text-red-700 bg-red-100" },
};

export function ValidationFlags({ flags, overallAssessment, summary }: ValidationFlagsProps) {
  if (!flags || flags.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        No validation flags generated yet.
      </div>
    );
  }

  const critical = flags.filter((f) => f.severity === "critical");
  const warnings = flags.filter((f) => f.severity === "warning");
  const infos = flags.filter((f) => f.severity === "info");

  return (
    <div className="space-y-4">
      {overallAssessment && (
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Assessment:</span>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${assessmentLabels[overallAssessment]?.color ?? "bg-zinc-100 text-zinc-700"}`}
          >
            {assessmentLabels[overallAssessment]?.label ?? overallAssessment}
          </span>
        </div>
      )}

      {summary && (
        <p className="text-sm text-muted-foreground">{summary}</p>
      )}

      <div className="space-y-2">
        {[...critical, ...warnings, ...infos].map((flag, i) => {
          const cfg = severityConfig[flag.severity];
          return (
            <div key={i} className={`rounded-lg border p-3 ${cfg.bg}`}>
              <div className="flex items-start gap-2">
                <div className="mt-0.5">{cfg.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium">{flag.field}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${cfg.badge}`}>
                      {cfg.label}
                    </span>
                  </div>
                  {(flag.borrower_value || flag.market_value) && (
                    <div className="text-xs space-x-3 mb-1 opacity-80">
                      {flag.borrower_value && <span>Borrower: {flag.borrower_value}</span>}
                      {flag.market_value && <span>Market: {flag.market_value}</span>}
                    </div>
                  )}
                  <p className="text-sm">{flag.explanation}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
