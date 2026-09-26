import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  AggregateVelocity,
  DealVelocity,
  AggregateQuality,
  FieldAccuracy,
  AggregateCost,
  DealCost,
  Alert,
  Bottleneck,
} from "../types";

// Velocity
export function useAggregateVelocity() {
  return useQuery({
    queryKey: ["metrics", "velocity"],
    queryFn: () => api.get<AggregateVelocity>("/metrics/velocity"),
  });
}

export function useDealVelocity(dealId: string) {
  return useQuery({
    queryKey: ["metrics", "velocity", dealId],
    queryFn: () => api.get<DealVelocity>(`/metrics/velocity/${dealId}`),
    enabled: !!dealId,
  });
}

export function useBottlenecks() {
  return useQuery({
    queryKey: ["metrics", "bottlenecks"],
    queryFn: () => api.get<{ bottlenecks: Bottleneck[] }>("/metrics/velocity/bottlenecks"),
  });
}

// Quality
export function useAggregateQuality() {
  return useQuery({
    queryKey: ["metrics", "quality"],
    queryFn: () => api.get<AggregateQuality>("/metrics/quality"),
  });
}

export function useFieldAccuracy() {
  return useQuery({
    queryKey: ["metrics", "quality", "fields"],
    queryFn: () => api.get<FieldAccuracy>("/metrics/quality/fields"),
  });
}

// Cost
export function useAggregateCost() {
  return useQuery({
    queryKey: ["metrics", "cost"],
    queryFn: () => api.get<AggregateCost>("/metrics/cost"),
  });
}

export function useDealCost(dealId: string) {
  return useQuery({
    queryKey: ["metrics", "cost", dealId],
    queryFn: () => api.get<DealCost>(`/metrics/cost/${dealId}`),
    enabled: !!dealId,
  });
}

// Alerts
export function useAlerts(dealId?: string) {
  return useQuery({
    queryKey: ["metrics", "alerts", dealId],
    queryFn: () => {
      const params = dealId ? `?deal_id=${dealId}` : "";
      return api.get<Alert[]>(`/metrics/alerts${params}`);
    },
    refetchInterval: 30000,
  });
}

export function useAcknowledgeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      api.post(`/metrics/alerts/${alertId}/acknowledge`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["metrics", "alerts"] }),
  });
}
