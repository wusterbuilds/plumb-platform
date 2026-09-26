"use client";

import { useRef } from "react";
import {
  useMarketStatus,
  useMarketContext,
  useMarketData,
  useImportMarketData,
  useEnrichDeal,
} from "@/lib/queries/market";
import { MarketDataCard } from "./MarketDataCard";
import { ValidationFlags } from "./ValidationFlags";
import { Button } from "@/components/ui/button";
import type { Deal, MarketContext, ValidationFlag } from "@/lib/types";
import {
  Upload,
  RefreshCw,
  Building2,
  FileText,
  Shield,
  Newspaper,
  MapPin,
  UserCheck,
} from "lucide-react";

interface MarketSummaryProps {
  deal: Deal;
}

const FETCHER_META: Record<string, { title: string; fullName: string; icon: React.ReactNode }> = {
  zola: { title: "ZoLa / PLUTO", fullName: "NYC Zoning & Land Use", icon: <MapPin className="h-4 w-4" /> },
  acris: { title: "ACRIS", fullName: "NYC Property Records", icon: <Building2 className="h-4 w-4" /> },
  dob: { title: "DOB", fullName: "NYC Dept of Buildings", icon: <FileText className="h-4 w-4" /> },
  news: { title: "News", fullName: "CRE Trade Press (Brave Search)", icon: <Newspaper className="h-4 w-4" /> },
  ag_refb: { title: "AG REFB", fullName: "NY AG Offering Plans", icon: <Shield className="h-4 w-4" /> },
};

export function MarketSummary({ deal }: MarketSummaryProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: status } = useMarketStatus(deal.id);
  const { data: context } = useMarketContext(deal.id);
  const { data: marketData } = useMarketData(deal.id);
  const importMutation = useImportMarketData(deal.id);
  const enrichMutation = useEnrichDeal(deal.id);

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      importMutation.mutate(file);
      e.target.value = "";
    }
  };

  const validationFlags = (context?.validation_flags ?? []) as ValidationFlag[];
  const sponsorPortfolio = context?.sponsor_portfolio as Record<string, unknown> | null;

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">Market Intelligence</h2>
          <p className="text-sm text-muted-foreground">
            {status?.total_records ?? 0} data sources collected
          </p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".csv,.xlsx,.xls"
            onChange={handleImport}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={importMutation.isPending}
          >
            <Upload className="h-4 w-4 mr-1" />
            {importMutation.isPending ? "Importing..." : "Import Data"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => enrichMutation.mutate()}
            disabled={enrichMutation.isPending}
          >
            <RefreshCw className={`h-4 w-4 mr-1 ${enrichMutation.isPending ? "animate-spin" : ""}`} />
            {enrichMutation.isPending ? "Running..." : "Re-run"}
          </Button>
        </div>
      </div>

      {/* Import result toast */}
      {importMutation.isSuccess && importMutation.data && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          Imported {importMutation.data.records_imported} records via {importMutation.data.importer}.
          {importMutation.data.warnings.length > 0 && (
            <span className="text-amber-700 ml-2">
              ({importMutation.data.warnings.length} warnings)
            </span>
          )}
        </div>
      )}

      {/* Fetcher Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {Object.entries(FETCHER_META).map(([key, meta]) => {
          const fetcher = status?.fetchers?.[key];
          const fetcherStatus = fetcher?.status ?? "pending";
          return (
            <MarketDataCard
              key={key}
              title={meta.title}
              source={meta.fullName}
              status={fetcherStatus}
              sourceUrl={fetcher?.source_url}
              confidence={fetcher?.confidence}
            >
              {fetcherStatus === "success" && (
                <ZoningSummary
                  source={key}
                  context={context}
                  records={marketData?.records}
                />
              )}
            </MarketDataCard>
          );
        })}
      </div>

      {/* Sponsor Portfolio */}
      {sponsorPortfolio && (
        <div className="rounded-lg border p-4">
          <div className="flex items-center gap-2 mb-3">
            <UserCheck className="h-4 w-4 text-indigo-600" />
            <h3 className="text-sm font-medium">Sponsor Portfolio</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground text-xs">Verified Projects</p>
              <p className="font-medium">{(sponsorPortfolio.verified_projects as unknown[])?.length ?? 0}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Unverified Claims</p>
              <p className="font-medium">{(sponsorPortfolio.unverified_claims as unknown[])?.length ?? 0}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Violation History</p>
              <p className="font-medium">
                {String((sponsorPortfolio.violation_history as Record<string, unknown>)?.total_violations ?? "N/A")}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">AG Filings</p>
              <p className="font-medium">{(sponsorPortfolio.offering_plan_history as unknown[])?.length ?? 0}</p>
            </div>
          </div>
          {((sponsorPortfolio.litigation_flags as unknown[])?.length ?? 0) > 0 && (
            <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {(sponsorPortfolio.litigation_flags as string[]).map((flag, i) => (
                <p key={i}>{flag}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Validation Flags */}
      <div className="rounded-lg border p-4">
        <h3 className="text-sm font-medium mb-3">Borrower Assumption Validation</h3>
        <ValidationFlags
          flags={validationFlags}
          overallAssessment={context?.overall_assessment}
          summary={context?.validation_summary}
        />
      </div>

      {/* Market Data Details */}
      {marketData && marketData.records.length > 0 && (
        <div className="rounded-lg border p-4">
          <h3 className="text-sm font-medium mb-3">
            All Market Data Records ({marketData.total})
          </h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {marketData.records.map((rec) => (
              <div
                key={rec.id}
                className="flex items-center justify-between py-2 px-3 rounded bg-muted/30 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                    {rec.data_source}
                  </span>
                  <span>{rec.data_type}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {rec.confidence_score != null && (
                    <span>{(rec.confidence_score * 100).toFixed(0)}%</span>
                  )}
                  {rec.source_url && (
                    <a
                      href={rec.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-foreground underline"
                    >
                      source
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ZoningSummary({
  source,
  context,
  records,
}: {
  source: string;
  context: MarketContext | Record<string, unknown> | undefined | null;
  records: Array<{ data_source: string; data: Record<string, unknown> | null }> | undefined;
}) {
  if (!context && !records) return null;

  if (source === "zola") {
    const zoning = (context as Record<string, unknown> | undefined)?.zoning as Record<string, unknown> | undefined;
    if (zoning && zoning.status !== "unavailable") {
      const district = zoning.zoning_district ? String(zoning.zoning_district) : null;
      const far = zoning.residential_far ? String(zoning.residential_far) : null;
      const lotSf = zoning.lot_area_sf ? Number(zoning.lot_area_sf) : null;
      return (
        <div className="space-y-1 text-xs">
          {district && <p>Zone: {district}</p>}
          {far && <p>FAR: {far}</p>}
          {lotSf != null && <p>Lot: {lotSf.toLocaleString()} SF</p>}
        </div>
      );
    }
  }

  if (source === "acris") {
    const history = (context as Record<string, unknown> | undefined)?.property_history as Record<string, unknown> | undefined;
    if (history && history.status !== "unavailable") {
      const owner = history.current_owner ? String(history.current_owner) : null;
      const price = history.purchase_price ? String(history.purchase_price) : null;
      return (
        <div className="space-y-1 text-xs">
          {owner && <p>Owner: {owner}</p>}
          {price && <p>Purchase: {price}</p>}
        </div>
      );
    }
  }

  if (source === "dob") {
    const permits = context?.permits as Record<string, unknown> | undefined;
    if (permits && permits.status !== "unavailable") {
      const flags = permits.material_flags as string[] | undefined;
      return (
        <div className="space-y-1 text-xs">
          {flags && flags.length > 0 ? (
            <p className="text-red-600">{flags.length} material flag(s)</p>
          ) : (
            <p className="text-green-600">No material issues</p>
          )}
        </div>
      );
    }
  }

  if (source === "news") {
    const news = context?.news as unknown[];
    if (news && news.length > 0) {
      return <p className="text-xs">{news.length} article(s) found</p>;
    }
  }

  if (source === "ag_refb") {
    const plan = context?.offering_plan as Record<string, unknown> | undefined;
    if (plan && plan.status !== "unavailable" && plan.status !== "manual_verification_needed") {
      return <p className="text-xs">Offering plan data available</p>;
    }
    if (plan?.status === "manual_verification_needed") {
      return (
        <a
          href={String(plan.search_url ?? "")}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 underline"
        >
          Verify manually
        </a>
      );
    }
  }

  return null;
}
