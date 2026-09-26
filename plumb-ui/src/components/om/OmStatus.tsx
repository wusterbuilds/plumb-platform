"use client";

import { useOmStatus, useOmVersions, useGenerateOm } from "@/lib/queries/om";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/format";
import { FileText, Loader2, RefreshCw } from "lucide-react";

interface OmStatusProps {
  dealId: string;
  onSelectVersion?: (versionId: string) => void;
}

export function OmStatus({ dealId, onSelectVersion }: OmStatusProps) {
  const { data: status } = useOmStatus(dealId);
  const { data: versions } = useOmVersions(dealId);
  const generate = useGenerateOm(dealId);

  const isGenerating = status?.status === "generating";
  const isReady = status?.status === "ready";

  return (
    <div className="space-y-4">
      {/* Status + Generate button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Offering Memorandum</span>
          {isGenerating && (
            <Badge variant="outline" className="text-xs">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Generating...
            </Badge>
          )}
          {isReady && (
            <Badge variant="outline" className="text-xs text-green-700">
              Ready
            </Badge>
          )}
          {status?.status === "idle" && (
            <Badge variant="outline" className="text-xs text-muted-foreground">
              Not generated
            </Badge>
          )}
        </div>

        <Button
          size="sm"
          variant={isReady ? "outline" : "default"}
          onClick={() => generate.mutate(true)}
          disabled={generate.isPending || isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
              Generating...
            </>
          ) : isReady ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Regenerate
            </>
          ) : (
            "Generate OM"
          )}
        </Button>
      </div>

      {/* Version history */}
      {versions && versions.versions.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Versions
          </p>
          {versions.versions.map((v) => (
            <div
              key={v.id}
              className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
              onClick={() => onSelectVersion?.(v.id)}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  v{v.version_number}
                </span>
                <Badge
                  variant="outline"
                  className={
                    v.status === "ready"
                      ? "text-green-700"
                      : v.status === "generating"
                        ? "text-amber-700"
                        : "text-muted-foreground"
                  }
                >
                  {v.status}
                </Badge>
              </div>
              <div className="text-xs text-muted-foreground">
                {v.generated_at ? formatDate(v.generated_at) : "—"}
                {v.page_count && ` · ${v.page_count} pages`}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
