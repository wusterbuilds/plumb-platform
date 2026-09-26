"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  formatCurrencyCompact,
  formatPercentPrecise,
  formatPerUnit,
} from "@/lib/format";
import type { ValuationSummary as ValuationType } from "@/lib/types";

interface ValuationSummaryProps {
  data: ValuationType;
}

interface MetricCardProps {
  label: string;
  value: string;
}

function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-xs text-muted-foreground uppercase tracking-wider">
        {label}
      </p>
      <p className="text-lg font-semibold font-mono tabular-nums mt-1">
        {value}
      </p>
    </div>
  );
}

export function ValuationSummary({ data }: ValuationSummaryProps) {
  return (
    <div className="space-y-4">
      {/* Valuation */}
      <Card size="sm">
        <CardHeader>
          <CardTitle>Valuation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Total Asset Value"
              value={formatCurrencyCompact(data.total_asset_value)}
            />
            <MetricCard
              label="NOI (Stabilized)"
              value={formatCurrencyCompact(data.actual_noi)}
            />
            <MetricCard
              label="Cap Rate"
              value={formatPercentPrecise(data.cap_rate)}
            />
            <MetricCard
              label="Yield on Cost"
              value={formatPercentPrecise(data.yield_on_cost)}
            />
            <MetricCard
              label="Value (NOI / Cap)"
              value={formatCurrencyCompact(data.estimated_value_a)}
            />
            <MetricCard
              label="Abatement Value"
              value={formatCurrencyCompact(data.abatement_value_b)}
            />
            <MetricCard
              label="Value / Unit"
              value={formatPerUnit(data.value_per_unit)}
            />
            <MetricCard
              label="Value / GSF"
              value={formatPerUnit(data.value_per_gsf)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Debt Metrics */}
      <Card size="sm">
        <CardHeader>
          <CardTitle>Debt Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Stabilized LTV"
              value={formatPercentPrecise(data.stabilized_ltv)}
            />
            <MetricCard
              label="Debt Yield"
              value={formatPercentPrecise(data.debt_yield)}
            />
            <MetricCard
              label="Construction Loan"
              value={formatCurrencyCompact(data.construction_loan)}
            />
            <MetricCard
              label="Total Project Cap"
              value={formatCurrencyCompact(data.total_project_cap)}
            />
            <MetricCard
              label="Debt / Unit"
              value={formatPerUnit(data.debt_per_unit)}
            />
            <MetricCard
              label="Debt / GSF"
              value={formatPerUnit(data.debt_per_gsf)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
