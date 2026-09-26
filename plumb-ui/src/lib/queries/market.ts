import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import type {
  MarketStatus,
  MarketContext,
  MarketDataListResponse,
  ImportResponse,
} from "../types";

export function useMarketStatus(dealId: string) {
  return useQuery({
    queryKey: ["market-status", dealId],
    queryFn: () => api.get<MarketStatus>(`/deals/${dealId}/market/status`),
    enabled: !!dealId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 5000;
      const allDone = Object.values(data.fetchers).every(
        (f) => f.status !== "pending" && f.status !== "running",
      );
      return allDone ? false : 3000;
    },
  });
}

export function useMarketContext(dealId: string) {
  return useQuery({
    queryKey: ["market-context", dealId],
    queryFn: async () => {
      try {
        return await api.get<MarketContext>(`/deals/${dealId}/market/context`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null;
        }
        throw err;
      }
    },
    enabled: !!dealId,
    refetchInterval: (query) => (query.state.data ? false : 5000),
  });
}

export function useMarketData(dealId: string) {
  return useQuery({
    queryKey: ["market-data", dealId],
    queryFn: () =>
      api.get<MarketDataListResponse>(`/deals/${dealId}/market/data`),
    enabled: !!dealId,
  });
}

export function useMarketValidation(dealId: string) {
  return useQuery({
    queryKey: ["market-validation", dealId],
    queryFn: () =>
      api.get<{ flags: unknown[]; overall_assessment: string | null; summary: string | null }>(
        `/deals/${dealId}/market/validation`,
      ),
    enabled: !!dealId,
    retry: false,
  });
}

export function useImportMarketData(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      api.upload<ImportResponse>(`/deals/${dealId}/market/import`, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["market-data", dealId] });
      qc.invalidateQueries({ queryKey: ["market-status", dealId] });
      qc.invalidateQueries({ queryKey: ["market-context", dealId] });
    },
  });
}

export function useEnrichDeal(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<{ status: string; task_id: string }>(
        `/deals/${dealId}/market/enrich`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["market-status", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}
