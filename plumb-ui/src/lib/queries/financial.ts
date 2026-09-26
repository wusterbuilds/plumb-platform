import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  FinancialModel,
  CalculateResponse,
  AssumptionsUpdate,
} from "../types";

export function useFinancialModel(dealId: string) {
  return useQuery({
    queryKey: ["financial-model", dealId],
    queryFn: () => api.get<FinancialModel>(`/deals/${dealId}/financial/model`),
    enabled: !!dealId,
    retry: false,
  });
}

export function useCalculateModel(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assumptions?: Record<string, number>) =>
      api.post<CalculateResponse>(`/deals/${dealId}/financial/calculate`, {
        assumptions,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["financial-model", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}

export function useUpdateAssumptions(dealId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assumptions: AssumptionsUpdate) =>
      api.put<CalculateResponse>(
        `/deals/${dealId}/financial/assumptions`,
        assumptions,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["financial-model", dealId] });
      qc.invalidateQueries({ queryKey: ["deal", dealId] });
    },
  });
}

/** Triggers a file download for the Excel workbook */
export function useExcelDownload(dealId: string) {
  return {
    download: () => {
      const token = localStorage.getItem("plumb_token");
      const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/deals/${dealId}/financial/excel`;
      const a = document.createElement("a");
      // Use fetch to get the blob with auth header
      fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.blob())
        .then((blob) => {
          const href = URL.createObjectURL(blob);
          a.href = href;
          a.download = `financial_model_${dealId.slice(0, 8)}.xlsx`;
          a.click();
          URL.revokeObjectURL(href);
        });
    },
  };
}
