import { useQuery, useMutation } from "@tanstack/react-query";
import { generate, getSessionStats } from "@/lib/api/sessions";

export function useSessionStats(sessionId: number) {
  return useQuery({
    queryKey: ["sessions", sessionId, "stats"],
    queryFn: () => getSessionStats(sessionId),
    enabled: !Number.isNaN(sessionId),
  });
}

export function useGenerate(sessionId: number) {
  return useMutation({
    mutationFn: () => generate(sessionId),
  });
}
