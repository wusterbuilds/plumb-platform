"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import {
  useApproveOmVersion,
  useRedlines,
  useRerunWithFeedback,
} from "@/lib/queries/redlines";
import { useOmStatus } from "@/lib/queries/om";
import { formatDate } from "@/lib/format";
import type { Redline, RedlineSeverity } from "@/lib/types";

interface RedlinePanelProps {
  dealId: string;
  versionId: string;
}

const SEVERITY_BADGE: Record<RedlineSeverity, string> = {
  minor: "text-muted-foreground",
  moderate: "text-amber-700",
  material: "text-red-700",
};

const CATEGORY_LABEL: Record<string, string> = {
  factual_error: "Factual",
  tone: "Tone",
  omission: "Omission",
  aggressive_assumption: "Aggressive",
  compliance: "Compliance",
  positioning: "Positioning",
};

export function RedlinePanel({ dealId, versionId }: RedlinePanelProps) {
  const { data, isLoading } = useRedlines(dealId, versionId);
  const omStatus = useOmStatus(dealId);
  const rerun = useRerunWithFeedback(dealId, versionId);
  const approve = useApproveOmVersion(dealId, versionId);

  // Hold on to the rerun response so the panel can echo "applied N lesson(s)"
  // even after react-query has invalidated and the mutation result resets.
  const [lastApplied, setLastApplied] = useState<string[] | null>(null);

  const redlines = data?.redlines ?? [];
  const generating = omStatus.data?.status === "generating";

  return (
    <div className="flex flex-col h-full border rounded-lg bg-background">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Expert feedback</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Captured for v{omStatus.data?.latest_version?.version_number ?? "?"}
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          {redlines.length} redline{redlines.length === 1 ? "" : "s"}
        </Badge>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Loading...
            </div>
          ) : redlines.length === 0 ? (
            <div className="rounded-md border border-dashed py-8 px-4 text-center text-xs text-muted-foreground">
              No redlines yet. Hover any section in the Edit tab and click{" "}
              <span className="font-medium">Suggest correction</span> to capture
              your first one.
            </div>
          ) : (
            redlines.map((r) => <RedlineRow key={r.id} redline={r} />)
          )}
        </div>
      </ScrollArea>

      <div className="border-t p-3 space-y-2">
        {lastApplied && lastApplied.length > 0 && (
          <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-900">
            <div className="flex items-center gap-1.5 font-medium mb-1">
              <Sparkles className="h-3 w-3" />
              {lastApplied.length} lesson{lastApplied.length === 1 ? "" : "s"} applied
            </div>
            <ul className="list-disc pl-4 space-y-0.5">
              {lastApplied.slice(0, 3).map((l, i) => (
                <li key={i} className="line-clamp-2">
                  {l}
                </li>
              ))}
              {lastApplied.length > 3 && (
                <li className="text-emerald-700/70">
                  + {lastApplied.length - 3} more
                </li>
              )}
            </ul>
          </div>
        )}

        <Button
          className="w-full"
          onClick={() =>
            rerun.mutate(undefined, {
              onSuccess: (response) =>
                setLastApplied(response.lessons_applied),
            })
          }
          disabled={rerun.isPending || generating || redlines.length === 0}
        >
          {rerun.isPending || generating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              {generating ? "Regenerating..." : "Sending..."}
            </>
          ) : (
            <>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Re-run with feedback
            </>
          )}
        </Button>

        <Button
          className="w-full"
          variant="outline"
          onClick={() => approve.mutate()}
          disabled={approve.isPending || generating}
        >
          {approve.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Approving...
            </>
          ) : (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
              Approve as-is
            </>
          )}
        </Button>

        {rerun.isError && (
          <p className="text-xs text-destructive">
            {(rerun.error as Error)?.message}
          </p>
        )}
      </div>
    </div>
  );
}

function RedlineRow({ redline }: { redline: Redline }) {
  const [expanded, setExpanded] = useState(false);
  const cat = redline.correction_category
    ? CATEGORY_LABEL[redline.correction_category] ?? redline.correction_category
    : "—";

  return (
    <div className="rounded-md border px-3 py-2 text-xs space-y-1.5 bg-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className="text-[10px]">
            {redline.section_key.replace(/_/g, " ")}
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {cat}
          </Badge>
          <span
            className={`text-[10px] font-medium ${
              SEVERITY_BADGE[redline.severity] ?? ""
            }`}
          >
            {redline.severity}
          </span>
        </div>
        <span className="text-muted-foreground text-[10px]">
          {formatDate(redline.created_at)}
        </span>
      </div>

      {redline.rationale && (
        <p className="text-foreground/80 leading-relaxed">
          {redline.rationale}
        </p>
      )}

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
      >
        {expanded ? "Hide diff" : "Show diff"}
      </button>

      {expanded && (
        <div className="space-y-1 mt-1">
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-wider">
              From
            </p>
            <p className="text-foreground/70 line-through text-[11px] leading-relaxed">
              {redline.original_text}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-wider">
              To
            </p>
            <p className="text-foreground text-[11px] leading-relaxed">
              {redline.edited_text}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
