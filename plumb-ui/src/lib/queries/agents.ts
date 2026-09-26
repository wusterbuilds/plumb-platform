import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { FeatureFlag, AgentRun, AgentTool } from "../types";

export function useFeatureFlags() {
  return useQuery({
    queryKey: ["agent", "flags"],
    queryFn: () => api.get<FeatureFlag[]>("/agent/flags"),
  });
}

export function useSetFlag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      flag_name: string;
      enabled: boolean;
      enabled_deal_types?: string[];
      enabled_deal_ids?: string[];
    }) => api.post("/agent/flags", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent", "flags"] }),
  });
}

export function useAgentTools() {
  return useQuery({
    queryKey: ["agent", "tools"],
    queryFn: () => api.get<AgentTool[]>("/agent/tools"),
  });
}

export function useAgentRuns(dealId?: string, agentName?: string) {
  return useQuery({
    queryKey: ["agent", "runs", dealId, agentName],
    queryFn: () => {
      const params = new URLSearchParams();
      if (dealId) params.set("deal_id", dealId);
      if (agentName) params.set("agent_name", agentName);
      const qs = params.toString();
      return api.get<AgentRun[]>(`/agent/runs${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useAgentRun(runId: string) {
  return useQuery({
    queryKey: ["agent", "run", runId],
    queryFn: () => api.get<AgentRun>(`/agent/runs/${runId}`),
    enabled: !!runId,
  });
}

export function useRunAgentPipeline(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post(`/agent/run/${dealId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent", "runs", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}

export function useAgentRunsPolling(dealId: string, enabled = false) {
  return useQuery({
    queryKey: ["agent", "runs", dealId],
    queryFn: () => api.get<AgentRun[]>(`/agent/runs?deal_id=${dealId}`),
    enabled,
    refetchInterval: enabled ? 3000 : false,
  });
}
