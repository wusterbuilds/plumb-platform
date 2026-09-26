import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Lender, LenderSummary, LenderMatch } from "../types";

export function useLenders(search?: string) {
  return useQuery({
    queryKey: ["lenders", search],
    queryFn: () => {
      const params = search ? `?search=${encodeURIComponent(search)}` : "";
      return api.get<LenderSummary[]>(`/lenders${params}`);
    },
  });
}

export function useLender(lenderId: string) {
  return useQuery({
    queryKey: ["lender", lenderId],
    queryFn: () => api.get<Lender>(`/lenders/${lenderId}`),
    enabled: !!lenderId,
  });
}

export function useCreateLender() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; lender_type: string; notes?: string }) =>
      api.post<{ id: string }>("/lenders", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lenders"] }),
  });
}

export function useUpdateLender(lenderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.put(`/lenders/${lenderId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lenders"] });
      qc.invalidateQueries({ queryKey: ["lender", lenderId] });
    },
  });
}

export function useLogAppetite(lenderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      appetite_signal: string;
      property_types?: string[];
      geographies?: string[];
      deal_size_min?: number;
      deal_size_max?: number;
      ltc_max?: number;
      rate_indication?: string;
      source_detail?: string;
    }) => api.post(`/lenders/${lenderId}/appetite`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lender", lenderId] }),
  });
}

export function useLogTransaction(lenderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post(`/lenders/${lenderId}/transactions`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lender", lenderId] }),
  });
}

export function useLenderMatch(dealId: string, params?: {
  property_type?: string;
  geography?: string;
  deal_size?: number;
  ltc_requested?: number;
}) {
  return useQuery({
    queryKey: ["lender-match", dealId, params],
    queryFn: () => {
      const qs = new URLSearchParams();
      if (params?.property_type) qs.set("property_type", params.property_type);
      if (params?.geography) qs.set("geography", params.geography);
      if (params?.deal_size) qs.set("deal_size", String(params.deal_size));
      if (params?.ltc_requested) qs.set("ltc_requested", String(params.ltc_requested));
      const qsStr = qs.toString();
      return api.get<LenderMatch[]>(`/deals/${dealId}/lender-match${qsStr ? `?${qsStr}` : ""}`);
    },
    enabled: !!dealId,
  });
}

export function useDistributeDeal(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { lender_id: string; approach_angle?: string }) =>
      api.post(`/deals/${dealId}/distribute`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["distributions", dealId] }),
  });
}

export function useDistributions(dealId: string) {
  return useQuery({
    queryKey: ["distributions", dealId],
    queryFn: () => api.get<unknown[]>(`/deals/${dealId}/distributions`),
    enabled: !!dealId,
  });
}

export function useRecordResponse(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      deal_distribution_id: string;
      response_type: string;
      terms_offered?: Record<string, unknown>;
      pass_reason?: string;
      notes?: string;
    }) => api.post(`/deals/${dealId}/responses`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["distributions", dealId] }),
  });
}

export function useCloseDeal(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      winning_lender_id: string;
      final_terms?: Record<string, unknown>;
      total_turnaround_days?: number;
      notes?: string;
    }) => api.post(`/deals/${dealId}/close`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
      qc.invalidateQueries({ queryKey: ["distributions", dealId] });
    },
  });
}
