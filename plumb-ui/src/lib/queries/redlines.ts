import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  OMApproveResponse,
  OMNarrativeSnapshot,
  Redline,
  RedlineCreate,
  RedlineListResponse,
  RerunWithFeedbackResponse,
} from "../types";

export function useRedlines(dealId: string, versionId?: string | null) {
  return useQuery({
    queryKey: ["redlines", dealId, versionId ?? null],
    queryFn: () => {
      const qs = versionId
        ? `?version_id=${encodeURIComponent(versionId)}`
        : "";
      return api.get<RedlineListResponse>(
        `/deals/${dealId}/redlines${qs}`,
      );
    },
    enabled: !!dealId,
  });
}

export function useCreateRedline(dealId: string, versionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: RedlineCreate) =>
      api.post<Redline>(
        `/deals/${dealId}/om/versions/${versionId}/redlines`,
        payload,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["redlines", dealId] });
      qc.invalidateQueries({ queryKey: ["om-narratives", dealId, versionId] });
    },
  });
}

export function useOmNarratives(dealId: string, versionId: string | null) {
  return useQuery({
    queryKey: ["om-narratives", dealId, versionId],
    queryFn: () =>
      api.get<OMNarrativeSnapshot>(
        `/deals/${dealId}/om/versions/${versionId}/narratives`,
      ),
    enabled: !!dealId && !!versionId,
  });
}

export function useRerunWithFeedback(dealId: string, versionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<RerunWithFeedbackResponse>(
        `/deals/${dealId}/om/versions/${versionId}/rerun-with-feedback`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["om-status", dealId] });
      qc.invalidateQueries({ queryKey: ["om-versions", dealId] });
      qc.invalidateQueries({ queryKey: ["redlines", dealId] });
    },
  });
}

export function useApproveOmVersion(dealId: string, versionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<OMApproveResponse>(
        `/deals/${dealId}/om/versions/${versionId}/approve`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["om-status", dealId] });
      qc.invalidateQueries({ queryKey: ["om-versions", dealId] });
      qc.invalidateQueries({ queryKey: ["om-narratives", dealId, versionId] });
    },
  });
}
