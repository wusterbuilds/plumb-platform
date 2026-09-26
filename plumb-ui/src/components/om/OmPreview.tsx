"use client";

import { useState } from "react";
import { useOmStatus, useOmVersions } from "@/lib/queries/om";
import { useOmDownloadUrl } from "@/lib/queries/om";
import { OmStatus } from "./OmStatus";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Download, Loader2 } from "lucide-react";

interface OmPreviewProps {
  dealId: string;
  /** When false, suppress the embedded OmStatus header — useful when the
   * caller (e.g. OmReviewWorkspace) renders status above its own tab bar. */
  showStatus?: boolean;
}

export function OmPreview({ dealId, showStatus = true }: OmPreviewProps) {
  const { data: status } = useOmStatus(dealId);
  const { data: versions } = useOmVersions(dealId);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(
    null,
  );

  // Default to latest ready version
  const latestReady = versions?.versions.find((v) => v.status === "ready");
  const activeVersionId = selectedVersionId ?? latestReady?.id;
  const activeVersion = versions?.versions.find(
    (v) => v.id === activeVersionId,
  );

  const download = useOmDownloadUrl(dealId, activeVersionId ?? "");

  // Build the PDF URL for iframe
  const pdfUrl = activeVersionId
    ? `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/deals/${dealId}/om/versions/${activeVersionId}/download`
    : null;

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("plumb_token")
      : null;

  return (
    <div className="space-y-4">
      {showStatus && (
        <OmStatus dealId={dealId} onSelectVersion={setSelectedVersionId} />
      )}

      {/* PDF Preview */}
      {activeVersionId && activeVersion?.status === "ready" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Viewing v{activeVersion.version_number}
              {activeVersion.page_count &&
                ` · ${activeVersion.page_count} pages`}
            </p>
            <Button variant="outline" size="sm" onClick={download.download}>
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Download PDF
            </Button>
          </div>

          <div className="border rounded-lg overflow-hidden bg-muted/30">
            {pdfUrl && token ? (
              <iframe
                src={`${pdfUrl}?token=${encodeURIComponent(token)}`}
                className="w-full h-[700px]"
                title="OM Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-[700px] text-muted-foreground">
                <p className="text-sm">Unable to load preview</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Generating state */}
      {status?.status === "generating" && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin mb-3" />
          <p className="text-sm">Generating Offering Memorandum...</p>
          <p className="text-xs mt-1">This may take a minute</p>
        </div>
      )}
    </div>
  );
}
