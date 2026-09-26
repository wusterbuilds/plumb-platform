import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  CrossReference,
  CrossReferenceListResponse,
  CrossRefResolution,
  ExtractionStatus,
  ExtractedValue,
  ExtractedValueListResponse,
  OverrideRequest,
} from "../types";

export function useExtractionStatus(dealId: string) {
  return useQuery({
    queryKey: ["extraction-status", dealId],
    queryFn: () => api.get<ExtractionStatus>(`/deals/${dealId}/extraction/status`),
    enabled: !!dealId,
  });
}

export function useExtractedValues(dealId: string, flag?: string) {
  return useQuery({
    queryKey: ["extracted-values", dealId, flag],
    queryFn: () => {
      const params = flag ? `?flag=${flag}` : "";
      return api.get<ExtractedValueListResponse>(`/deals/${dealId}/extraction/values${params}`);
    },
    enabled: !!dealId,
  });
}

export function useReviewValue(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (valueId: string) =>
      api.post<ExtractedValue>(`/deals/${dealId}/extraction/values/${valueId}/review`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["extracted-values", dealId] });
      qc.invalidateQueries({ queryKey: ["extraction-status", dealId] });
    },
  });
}

export function useOverrideValue(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ valueId, ...body }: OverrideRequest & { valueId: string }) =>
      api.put<ExtractedValue>(`/deals/${dealId}/extraction/values/${valueId}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["extracted-values", dealId] });
      qc.invalidateQueries({ queryKey: ["extraction-status", dealId] });
    },
  });
}

export function useCrossReferences(dealId: string) {
  return useQuery({
    queryKey: ["cross-references", dealId],
    queryFn: () =>
      api.get<CrossReferenceListResponse>(`/deals/${dealId}/extraction/cross-references`),
    enabled: !!dealId,
  });
}

export function useResolveCrossRef(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ xrefId, resolution }: { xrefId: string; resolution: CrossRefResolution }) =>
      api.post<CrossReference>(
        `/deals/${dealId}/extraction/cross-references/${xrefId}/resolve`,
        { resolution },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cross-references", dealId] });
      qc.invalidateQueries({ queryKey: ["extraction-status", dealId] });
    },
  });
}

export function useStartExtraction(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/deals/${dealId}/extraction/start`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["extraction-status", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}
