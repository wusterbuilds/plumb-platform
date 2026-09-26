import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  OMStatusResponse,
  OMVersionListResponse,
  OMGenerateResponse,
  OMNarrativeUpdate,
} from "../types";

export function useOmStatus(dealId: string) {
  return useQuery({
    queryKey: ["om-status", dealId],
    queryFn: () => api.get<OMStatusResponse>(`/deals/${dealId}/om/status`),
    enabled: !!dealId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.status === "generating" ? 3000 : false;
    },
  });
}

export function useOmVersions(dealId: string) {
  return useQuery({
    queryKey: ["om-versions", dealId],
    queryFn: () =>
      api.get<OMVersionListResponse>(`/deals/${dealId}/om/versions`),
    enabled: !!dealId,
  });
}

export function useGenerateOm(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (regenerateNarratives: boolean = true) =>
      api.post<OMGenerateResponse>(`/deals/${dealId}/om/generate`, {
        regenerate_narratives: regenerateNarratives,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["om-status", dealId] });
      qc.invalidateQueries({ queryKey: ["om-versions", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}

export function useUpdateNarratives(dealId: string, versionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (narratives: OMNarrativeUpdate) =>
      api.put<OMGenerateResponse>(
        `/deals/${dealId}/om/versions/${versionId}/narratives`,
        narratives,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["om-status", dealId] });
      qc.invalidateQueries({ queryKey: ["om-versions", dealId] });
    },
  });
}

/** Constructs the download URL for a specific OM version PDF */
export function useOmDownloadUrl(dealId: string, versionId: string) {
  return {
    download: () => {
      const token = localStorage.getItem("plumb_token");
      const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/deals/${dealId}/om/versions/${versionId}/download`;
      fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.blob())
        .then((blob) => {
          const href = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = href;
          a.download = `om_${dealId.slice(0, 8)}_v${versionId.slice(0, 8)}.pdf`;
          a.click();
          URL.revokeObjectURL(href);
        });
    },
  };
}
