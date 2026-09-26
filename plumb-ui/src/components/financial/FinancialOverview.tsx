"use client";

import { useFinancialModel, useExcelDownload } from "@/lib/queries/financial";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { SourcesUsesTable } from "./SourcesUsesTable";
import { BudgetDetailTable } from "./BudgetDetailTable";
import { UnitMixTable } from "./UnitMixTable";
import { ProFormaTable } from "./ProFormaTable";
import { ValuationSummary } from "./ValuationSummary";
import { SensitivityGrid } from "./SensitivityGrid";
import { AbatementTable } from "./AbatementTable";
import { AssumptionsEditor } from "./AssumptionsEditor";
import {
  formatCurrencyCompact,
  formatPercentPrecise,
  formatNumber,
} from "@/lib/format";
import { AlertCircle, Download, Loader2 } from "lucide-react";

interface FinancialOverviewProps {
  dealId: string;
}

export function FinancialOverview({ dealId }: FinancialOverviewProps) {
  const { data: model, isLoading, error } = useFinancialModel(dealId);
  const excel = useExcelDownload(dealId);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin mb-3" />
        <p className="text-sm">Loading financial model...</p>
      </div>
    );
  }

  if (error || !model) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <AlertCircle className="h-8 w-8 mb-3" />
        <p className="text-sm">
          {error ? "Failed to load financial model" : "No financial model available"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with key metrics + Excel download */}
      <div className="flex items-start justify-between">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              TDC
            </p>
            <p className="text-xl font-semibold font-mono tabular-nums">
              {formatCurrencyCompact(model.total_development_cost)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Loan
            </p>
            <p className="text-xl font-semibold font-mono tabular-nums">
              {formatCurrencyCompact(model.loan_amount)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              LTC
            </p>
            <p className="text-xl font-semibold font-mono tabular-nums">
              {formatPercentPrecise(model.ltc)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Units
            </p>
            <p className="text-xl font-semibold font-mono tabular-nums">
              {formatNumber(model.total_units)}
            </p>
          </div>
        </div>

        <Button variant="outline" size="sm" onClick={excel.download}>
          <Download className="h-3.5 w-3.5 mr-1.5" />
          Excel
        </Button>
      </div>

      {/* Errors */}
      {model.errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm font-medium text-red-800">Model Warnings</p>
          <ul className="mt-1 text-xs text-red-700 list-disc pl-4">
            {model.errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Assumptions */}
      <div className="border rounded-lg p-4">
        <h3 className="text-sm font-medium mb-3">Underwriting Assumptions</h3>
        <AssumptionsEditor dealId={dealId} current={model.assumptions} />
      </div>

      {/* Tabbed financial data */}
      <Tabs defaultValue="valuation">
        <TabsList variant="line">
          <TabsTrigger value="valuation">Valuation</TabsTrigger>
          <TabsTrigger value="sources_uses">Sources & Uses</TabsTrigger>
          <TabsTrigger value="budget">Budget Detail</TabsTrigger>
          <TabsTrigger value="unit_mix">Unit Mix</TabsTrigger>
          <TabsTrigger value="proforma">Pro Forma</TabsTrigger>
          <TabsTrigger value="sensitivity">Sensitivity</TabsTrigger>
          {model.abatement && (
            <TabsTrigger value="abatement">421(a)</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="valuation" className="mt-4">
          <ValuationSummary data={model.valuation} />
        </TabsContent>

        <TabsContent value="sources_uses" className="mt-4">
          <SourcesUsesTable data={model.sources_uses} />
        </TabsContent>

        <TabsContent value="budget" className="mt-4">
          <BudgetDetailTable data={model.budget_detail} />
        </TabsContent>

        <TabsContent value="unit_mix" className="mt-4">
          <UnitMixTable data={model.unit_mix} />
        </TabsContent>

        <TabsContent value="proforma" className="mt-4">
          <ProFormaTable data={model.proforma} />
        </TabsContent>

        <TabsContent value="sensitivity" className="mt-4">
          <SensitivityGrid data={model.sensitivity} />
        </TabsContent>

        {model.abatement && (
          <TabsContent value="abatement" className="mt-4">
            <AbatementTable data={model.abatement} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
