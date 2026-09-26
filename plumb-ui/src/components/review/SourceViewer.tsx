"use client";

import { useDocumentDownloadUrl } from "@/lib/queries/documents";
import { FileSpreadsheet, Loader2 } from "lucide-react";

interface SourceViewerProps {
  dealId: string;
  docId: string | null;
  page: number | null;
  snippet: string | null;
}

export function SourceViewer({ dealId, docId, page, snippet }: SourceViewerProps) {
  const { data: download, isLoading } = useDocumentDownloadUrl(
    dealId,
    docId ?? "",
    true, // inline — render in iframe, don't trigger download
  );

  if (!docId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No source document
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!download?.download_url) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        Could not load document
      </div>
    );
  }

  const filename = download.filename ?? "";
  const isPdf = filename.toLowerCase().endsWith(".pdf");

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b text-xs text-muted-foreground">
        <span>{filename}{page != null ? ` — Page ${page}` : ""}</span>
      </div>

      {isPdf ? (
        <div className="flex-1 relative">
          <iframe
            src={`${download.download_url}${page ? `#page=${page}` : ""}`}
            className="w-full h-full border-0"
            title="Source document"
          />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center space-y-3">
            <FileSpreadsheet className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              {filename} (not previewable)
            </p>
          </div>
        </div>
      )}

      {snippet && (
        <div className="border-t p-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
            Extracted text
          </p>
          <p className="text-sm italic">{snippet}</p>
        </div>
      )}
    </div>
  );
}
