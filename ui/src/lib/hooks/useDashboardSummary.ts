import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary } from "@/lib/api/dashboard";
import { QUERY_STALE } from "@/lib/query";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    staleTime: QUERY_STALE.dashboard,
  });
}
