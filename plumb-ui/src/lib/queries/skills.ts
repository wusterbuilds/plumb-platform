import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Skill, SkillVersion, SkillTestResult, KnowledgeEntry } from "../types";

// Skills
export function useSkills(status?: string) {
  return useQuery({
    queryKey: ["skills", status],
    queryFn: () => {
      const params = status ? `?status=${status}` : "";
      return api.get<Skill[]>(`/skills${params}`);
    },
  });
}

export function useSkill(skillId: string) {
  return useQuery({
    queryKey: ["skill", skillId],
    queryFn: () => api.get<Skill>(`/skills/${skillId}`),
    enabled: !!skillId,
  });
}

export function useCreateSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; skill_type: string; target_prompt: string }) =>
      api.post<{ id: string }>("/skills", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skills"] }),
  });
}

export function useSkillVersions(skillId: string) {
  return useQuery({
    queryKey: ["skill", skillId, "versions"],
    queryFn: () => api.get<SkillVersion[]>(`/skills/${skillId}/versions`),
    enabled: !!skillId,
  });
}

export function useCreateSkillVersion(skillId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { instructions: string; reference_examples?: unknown[]; validation_criteria?: unknown[] }) =>
      api.post<{ id: string }>(`/skills/${skillId}/versions`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skill", skillId] });
      qc.invalidateQueries({ queryKey: ["skill", skillId, "versions"] });
    },
  });
}

export function usePromoteSkillVersion(skillId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) =>
      api.post(`/skills/${skillId}/versions/${versionId}/promote`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["skill", skillId] });
      qc.invalidateQueries({ queryKey: ["skill", skillId, "versions"] });
    },
  });
}

export function useSkillTestResults(skillId: string) {
  return useQuery({
    queryKey: ["skill", skillId, "test-results"],
    queryFn: () => api.get<SkillTestResult[]>(`/skills/${skillId}/test-results`),
    enabled: !!skillId,
  });
}

// Knowledge
export function useKnowledge(entryType?: string, search?: string) {
  return useQuery({
    queryKey: ["knowledge", entryType, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (entryType) params.set("entry_type", entryType);
      if (search) params.set("search", search);
      const qs = params.toString();
      return api.get<KnowledgeEntry[]>(`/knowledge${qs ? `?${qs}` : ""}`);
    },
  });
}

export function useKnowledgeEntry(entryId: string) {
  return useQuery({
    queryKey: ["knowledge", entryId],
    queryFn: () => api.get<KnowledgeEntry>(`/knowledge/${entryId}`),
    enabled: !!entryId,
  });
}

export function useCreateKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { entry_type: string; title: string; content: string; tags?: string[] }) =>
      api.post<{ id: string }>("/knowledge", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}

export function useUpdateKnowledge(entryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { title?: string; content?: string; tags?: string[] }) =>
      api.put(`/knowledge/${entryId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge"] });
      qc.invalidateQueries({ queryKey: ["knowledge", entryId] });
    },
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => api.delete(`/knowledge/${entryId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] }),
  });
}
