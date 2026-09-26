"use client";

import { useDocuments } from "@/lib/queries/documents";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Document } from "@/lib/types";
import { FileText, FileSpreadsheet, File } from "lucide-react";

function docIcon(mime: string) {
  if (mime.includes("pdf")) return FileText;
  if (mime.includes("sheet") || mime.includes("excel")) return FileSpreadsheet;
  return File;
}

function statusBadge(status: Document["status"]) {
  switch (status) {
    case "extracted":
      return <Badge variant="outline" className="text-[10px] bg-green-50 text-green-700 border-green-200">Extracted</Badge>;
    case "failed":
      return <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700 border-red-200">Failed</Badge>;
    case "parsing":
    case "extracting":
      return <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700 border-amber-200">Processing</Badge>;
    default:
      return <Badge variant="outline" className="text-[10px]">{status}</Badge>;
  }
}

interface DocumentListProps {
  dealId: string;
  selectedDocId?: string;
  onSelectDoc?: (docId: string) => void;
}

export function DocumentList({ dealId, selectedDocId, onSelectDoc }: DocumentListProps) {
  const { data, isLoading } = useDocuments(dealId);
  const docs = data?.documents ?? [];

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-8 bg-muted rounded animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
        Documents ({docs.length})
      </h3>
      {docs.map((doc) => {
        const Icon = docIcon(doc.mime_type);
        return (
          <button
            key={doc.id}
            onClick={() => onSelectDoc?.(doc.id)}
            className={cn(
              "flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-left hover:bg-muted/50 transition-colors",
              selectedDocId === doc.id && "bg-muted",
            )}
          >
            <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="truncate flex-1">{doc.filename}</span>
            {statusBadge(doc.status)}
          </button>
        );
      })}
      {docs.length === 0 && (
        <p className="text-sm text-muted-foreground px-2">No documents uploaded.</p>
      )}
    </div>
  );
}
