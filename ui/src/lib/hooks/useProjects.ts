import { useQuery } from "@tanstack/react-query";
import { getProjects } from "@/lib/api/autocomplete";
import { QUERY_STALE } from "@/lib/query";

export function useProjects(vendorId: number | null, limit = 8) {
  return useQuery({
    queryKey: ["autocomplete", "projects", vendorId, limit],
    queryFn: () => getProjects(vendorId!, limit),
    staleTime: QUERY_STALE.autocomplete,
    enabled: vendorId != null && vendorId > 0,
  });
}
