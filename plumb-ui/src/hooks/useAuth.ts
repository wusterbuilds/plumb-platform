"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, setToken, clearToken, isAuthenticated } from "@/lib/api";
import type { Token, User } from "@/lib/types";

export function useUser() {
  return useQuery({
    queryKey: ["user"],
    queryFn: () => api.get<User>("/auth/me"),
    enabled: isAuthenticated(),
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (creds: { email: string; password: string }) =>
      api.post<Token>("/auth/login", creds),
    onSuccess: (data) => {
      setToken(data.access_token);
      qc.invalidateQueries({ queryKey: ["user"] });
      router.push("/");
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return () => {
    clearToken();
    qc.clear();
    router.push("/login");
  };
}
