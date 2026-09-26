import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { EventListResponse } from "../types";

export function useEvents(dealId: string) {
  return useQuery({
    queryKey: ["events", dealId],
    queryFn: () => api.get<EventListResponse>(`/deals/${dealId}/events`),
    enabled: !!dealId,
  });
}
