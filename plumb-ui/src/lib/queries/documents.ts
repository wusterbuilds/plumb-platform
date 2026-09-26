import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Document, DocumentListResponse } from "../types";

export function useDocuments(dealId: string) {
  return useQuery({
    queryKey: ["documents", dealId],
    queryFn: () => api.get<DocumentListResponse>(`/deals/${dealId}/documents`),
    enabled: !!dealId,
  });
}

export function useUploadDocument(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      api.upload<Document>(`/deals/${dealId}/documents`, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", dealId] }),
  });
}

export function useDocumentDownloadUrl(dealId: string, docId: string, inline = false) {
  return useQuery({
    queryKey: ["document-download", dealId, docId, inline],
    queryFn: () =>
      api.get<{ download_url: string; filename?: string; mime_type?: string }>(`/deals/${dealId}/documents/${docId}/download?inline=${inline}`),
    enabled: !!dealId && !!docId,
    staleTime: 5 * 60 * 1000, // presigned URLs valid for a while
  });
}
