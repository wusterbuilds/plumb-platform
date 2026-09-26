"use client";

import { useState } from "react";
import { formatCurrencyCompact, formatPercentPrecise } from "@/lib/format";
import type { SensitivityMatrix, SensitivityCell } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SensitivityGridProps {
  data: SensitivityMatrix;
}

function ltvColor(ltv: number): string {
  if (ltv < 0.65) return "bg-green-100 dark:bg-green-950/40";
  if (ltv < 0.75) return "bg-yellow-100 dark:bg-yellow-950/40";
  return "bg-red-100 dark:bg-red-950/40";
}

export function SensitivityGrid({ data }: SensitivityGridProps) {
  const { cap_rates, rent_growth_rates, cells, base_row, base_col } = data;
  const [hovered, setHovered] = useState<SensitivityCell | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded bg-green-100 border" />
            LTV &lt; 65%
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded bg-yellow-100 border" />
            65–75%
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded bg-red-100 border" />
            &gt; 75%
          </span>
        </div>

        {/* Hover detail */}
        {hovered && (
          <div className="text-xs text-muted-foreground flex gap-3 font-mono tabular-nums">
            <span>Value: {formatCurrencyCompact(hovered.asset_value)}</span>
            <span>LTV: {formatPercentPrecise(hovered.ltv)}</span>
            <span>Debt Yield: {formatPercentPrecise(hovered.debt_yield)}</span>
          </div>
        )}
      </div>

      <div className="overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1.5 text-left text-muted-foreground font-medium">
                Rent Growth ↓ / Cap Rate →
              </th>
              {cap_rates.map((cr, ci) => (
                <th
                  key={ci}
                  className={cn(
                    "px-2 py-1.5 text-center font-mono tabular-nums font-medium",
                    ci === base_col && "text-foreground font-bold",
                    ci !== base_col && "text-muted-foreground",
                  )}
                >
                  {formatPercentPrecise(cr)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rent_growth_rates.map((rg, ri) => (
              <tr key={ri}>
                <td
                  className={cn(
                    "px-2 py-1.5 font-mono tabular-nums",
                    ri === base_row
                      ? "font-bold text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {rg >= 0 ? "+" : ""}
                  {formatPercentPrecise(rg)}
                </td>
                {cells[ri]?.map((cell, ci) => {
                  const isBase = ri === base_row && ci === base_col;
                  return (
                    <td
                      key={ci}
                      className={cn(
                        "px-2 py-1.5 text-center font-mono tabular-nums cursor-default transition-colors",
                        ltvColor(cell.ltv),
                        isBase && "ring-2 ring-foreground/40 font-bold rounded",
                      )}
                      onMouseEnter={() => setHovered(cell)}
                      onMouseLeave={() => setHovered(null)}
                    >
                      {formatCurrencyCompact(cell.asset_value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
