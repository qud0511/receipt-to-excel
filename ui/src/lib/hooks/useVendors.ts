import { useQuery } from "@tanstack/react-query";
import { getVendors } from "@/lib/api/autocomplete";
import { QUERY_STALE } from "@/lib/query";

export function useVendors(q: string, limit = 8) {
  return useQuery({
    queryKey: ["autocomplete", "vendors", q, limit],
    queryFn: () => getVendors(q, limit),
    staleTime: QUERY_STALE.autocomplete,
  });
}
