import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  Deal,
  DealCreateRequest,
  DealListResponse,
  TransitionRequest,
} from "../types";

export function useDeals(statusFilter?: string) {
  return useQuery({
    queryKey: ["deals", statusFilter],
    queryFn: () => {
      const params = statusFilter ? `?status=${statusFilter}` : "";
      return api.get<DealListResponse>(`/deals${params}`);
    },
    refetchInterval: 5000, // Auto-refresh every 5s so email-created deals appear
  });
}

export function useDeal(dealId: string) {
  return useQuery({
    queryKey: ["deal", dealId],
    queryFn: () => api.get<Deal>(`/deals/${dealId}`),
    enabled: !!dealId,
    refetchInterval: 3000, // Auto-refresh so agent progress appears in real time
  });
}

export function useCreateDeal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: DealCreateRequest) => api.post<Deal>("/deals", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deals"] }),
  });
}

export function useTransitionDeal(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TransitionRequest) =>
      api.post<Deal>(`/deals/${dealId}/transition`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
      qc.invalidateQueries({ queryKey: ["deals"] });
    },
  });
}
