"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateNarratives } from "@/lib/queries/om";
import type { OMNarrativeUpdate } from "@/lib/types";
import { Loader2, Save } from "lucide-react";

interface NarrativeEditorProps {
  dealId: string;
  versionId: string;
  initialNarratives?: {
    transaction_overview?: string[];
    investment_highlights?: Record<string, string>[];
    market_narrative?: Record<string, string>[];
    sponsor_bios?: Record<string, string[]>;
  };
}

export function NarrativeEditor({
  dealId,
  versionId,
  initialNarratives,
}: NarrativeEditorProps) {
  const [overview, setOverview] = useState(
    initialNarratives?.transaction_overview?.join("\n\n") ?? "",
  );
  const [highlights, setHighlights] = useState(
    initialNarratives?.investment_highlights
      ?.map((h) => `${h.header}\n${h.body}`)
      .join("\n\n") ?? "",
  );
  const [market, setMarket] = useState(
    initialNarratives?.market_narrative
      ?.map((m) => `${m.header}\n${m.body}`)
      .join("\n\n") ?? "",
  );
  const [sponsors, setSponsors] = useState(
    initialNarratives?.sponsor_bios
      ? Object.entries(initialNarratives.sponsor_bios)
          .map(([name, paragraphs]) => `${name}\n${paragraphs.join("\n")}`)
          .join("\n\n---\n\n")
      : "",
  );

  const updateNarratives = useUpdateNarratives(dealId, versionId);

  const handleSave = () => {
    const update: OMNarrativeUpdate = {
      transaction_overview: overview
        .split("\n\n")
        .filter((p) => p.trim()),
    };
    updateNarratives.mutate(update);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">OM Narratives</h3>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={updateNarratives.isPending}
        >
          {updateNarratives.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Saving...
            </>
          ) : (
            <>
              <Save className="h-3.5 w-3.5 mr-1.5" />
              Save & Re-render
            </>
          )}
        </Button>
      </div>

      <div className="space-y-3">
        <div>
          <label className="text-xs text-muted-foreground uppercase tracking-wider">
            Transaction Overview
          </label>
          <Textarea
            value={overview}
            onChange={(e) => setOverview(e.target.value)}
            rows={6}
            className="mt-1 font-mono text-xs"
            placeholder="Transaction overview paragraphs (separated by blank lines)..."
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground uppercase tracking-wider">
            Investment Highlights
          </label>
          <Textarea
            value={highlights}
            onChange={(e) => setHighlights(e.target.value)}
            rows={6}
            className="mt-1 font-mono text-xs"
            placeholder="Header + body pairs (separated by blank lines)..."
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground uppercase tracking-wider">
            Market Narrative
          </label>
          <Textarea
            value={market}
            onChange={(e) => setMarket(e.target.value)}
            rows={6}
            className="mt-1 font-mono text-xs"
            placeholder="Market narrative sections..."
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground uppercase tracking-wider">
            Sponsor Bios
          </label>
          <Textarea
            value={sponsors}
            onChange={(e) => setSponsors(e.target.value)}
            rows={6}
            className="mt-1 font-mono text-xs"
            placeholder="Sponsor name followed by bio paragraphs. Separate sponsors with ---"
          />
        </div>
      </div>
    </div>
  );
}
