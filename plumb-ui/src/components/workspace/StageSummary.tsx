"use client";

import Link from "next/link";
import { useExtractionStatus, useCrossReferences, useStartExtraction } from "@/lib/queries/extraction";
import { useRunAgentPipeline } from "@/lib/queries/agents";
import { dealStatusLabel, statusCategory } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { MarketSummary } from "./MarketSummary";
import { FinancialOverview } from "@/components/financial/FinancialOverview";
import { OmPreview } from "@/components/om/OmPreview";
import { OmReviewWorkspace } from "@/components/om/OmReviewWorkspace";
import { AgentRunStatus } from "./AgentRunStatus";
import type { Deal } from "@/lib/types";
import { AlertCircle, CheckCircle2, Loader2, Play, Bot } from "lucide-react";

interface StageSummaryProps {
  deal: Deal;
}

export function StageSummary({ deal }: StageSummaryProps) {
  const { data: extraction } = useExtractionStatus(deal.id);
  const { data: crossRefs } = useCrossReferences(deal.id);
  const startExtraction = useStartExtraction(deal.id);
  const runAgentPipeline = useRunAgentPipeline(deal.id);
  const cat = statusCategory(deal.status);
  const isProcessing = cat === "processing";

  const redCount = extraction?.fields_by_flag?.red ?? 0;
  const yellowCount = extraction?.fields_by_flag?.yellow ?? 0;
  const greenCount = extraction?.fields_by_flag?.green ?? 0;
  const totalFlags = redCount + yellowCount;

  const unresolvedXrefs =
    crossRefs?.cross_references?.filter(
      (x) => x.result === "mismatch" && !x.resolution,
    ).length ?? 0;

  // Extraction Review stage
  if (deal.status === "extraction_review") {
    return (
      <div className="space-y-6">
        <div className="bg-muted/50 rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">
            {totalFlags > 0
              ? `${totalFlags} fields need your review`
              : "All fields reviewed"}
          </h2>

          <div className="space-y-2 text-sm">
            {redCount > 0 && (
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                <span>
                  {redCount} red flag{redCount !== 1 ? "s" : ""} (missing or low confidence)
                </span>
              </div>
            )}
            {yellowCount > 0 && (
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                <span>
                  {yellowCount} yellow flag{yellowCount !== 1 ? "s" : ""} (moderate confidence)
                </span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
              <span>{greenCount} green fields (auto-confirmed)</span>
            </div>
          </div>

          {totalFlags > 0 && (
            <Link href={`/deals/${deal.id}/review`}>
              <Button className="mt-4">Start Extraction Review</Button>
            </Link>
          )}
        </div>

        {unresolvedXrefs > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-amber-800">
              {unresolvedXrefs} cross-reference failure{unresolvedXrefs !== 1 ? "s" : ""}
            </h3>
            <div className="mt-2 space-y-1 text-sm text-amber-700">
              {crossRefs?.cross_references
                ?.filter((x) => x.result === "mismatch" && !x.resolution)
                .map((x) => (
                  <div key={x.id}>
                    {x.field_a}: {x.field_a_value} != {x.field_b_value} (delta: {x.delta})
                  </div>
                ))}
            </div>
          </div>
        )}

        <AgentRunStatus dealId={deal.id} />
      </div>
    );
  }

  // Market enrichment — show market summary only
  if (deal.status === "market_enrichment") {
    return <MarketSummary deal={deal} />;
  }

  // Model building — show financial model (loading/calculating state)
  if (deal.status === "model_building") {
    return (
      <div className="space-y-6">
        <FinancialOverview dealId={deal.id} />
      </div>
    );
  }

  // OM Drafting — show OM generation status + financial model below
  if (deal.status === "om_drafting") {
    return (
      <div className="space-y-8">
        <OmReviewWorkspace dealId={deal.id} />
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Financial Model
          </h3>
          <FinancialOverview dealId={deal.id} />
        </div>
      </div>
    );
  }

  // OM Review — full review workspace with redline capture
  if (deal.status === "om_review") {
    return (
      <div className="space-y-8">
        <OmReviewWorkspace dealId={deal.id} />
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Financial Model
          </h3>
          <FinancialOverview dealId={deal.id} />
        </div>
      </div>
    );
  }

  // Reworking — agent is processing a follow-up request
  if (deal.status === "reworking") {
    return (
      <div className="space-y-8">
        <div className="flex flex-col items-center justify-center py-12 space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <h2 className="text-lg font-semibold">Agent is reworking the deal</h2>
          <p className="text-sm text-muted-foreground text-center max-w-md">
            A follow-up request was received. The agent is updating the analysis,
            financial model, and deliverables based on the new feedback.
          </p>
          <AgentRunStatus dealId={deal.id} agentName="followup_agent" />
        </div>
        <div className="border-t pt-6">
          <OmPreview dealId={deal.id} />
        </div>
      </div>
    );
  }

  // Post-OM stages (lender outreach, tracking, term sheet, closed)
  if (
    deal.status === "lender_outreach" ||
    deal.status === "tracking" ||
    deal.status === "term_sheet_received" ||
    deal.status === "closed"
  ) {
    return (
      <div className="space-y-8">
        <OmReviewWorkspace dealId={deal.id} />
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            Financial Model
          </h3>
          <FinancialOverview dealId={deal.id} />
        </div>
      </div>
    );
  }

  // Docs received — ready to start extraction
  if (deal.status === "docs_received") {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-lg font-medium mb-2">Documents Ready</p>
        <p className="text-sm text-muted-foreground mb-6">
          Start the agent pipeline to classify, extract, underwrite, and draft the OM.
        </p>
        <div className="flex gap-3">
          <Button
            onClick={() => startExtraction.mutate()}
            disabled={startExtraction.isPending || runAgentPipeline.isPending}
            variant="outline"
          >
            {startExtraction.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            Legacy Pipeline
          </Button>
          <Button
            onClick={() => runAgentPipeline.mutate()}
            disabled={runAgentPipeline.isPending || startExtraction.isPending}
          >
            {runAgentPipeline.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Bot className="h-4 w-4 mr-2" />
            )}
            {runAgentPipeline.isPending ? "Starting Agents..." : "Run Agent Pipeline"}
          </Button>
        </div>
        <AgentRunStatus dealId={deal.id} polling={runAgentPipeline.isPending} />
      </div>
    );
  }

  // Processing stages — show agent run status with live polling
  if (cat === "processing") {
    return (
      <div className="space-y-6">
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin mb-3" />
          <p className="text-lg font-medium">{dealStatusLabel(deal.status)}</p>
          <p className="text-sm mt-1">Agents are working on this deal...</p>
        </div>
        <AgentRunStatus dealId={deal.id} polling />
      </div>
    );
  }

  // Error states
  if (cat === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-destructive">
        <AlertCircle className="h-8 w-8 mb-3" />
        <p className="text-lg font-medium">{dealStatusLabel(deal.status)}</p>
        <p className="text-sm mt-1 text-muted-foreground">Check the event log for details.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-lg font-medium">{dealStatusLabel(deal.status)}</p>
    </div>
  );
}
