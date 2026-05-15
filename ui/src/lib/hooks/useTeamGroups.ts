import { useQuery } from "@tanstack/react-query";
import { getTeamGroups } from "@/lib/api/autocomplete";
import { QUERY_STALE } from "@/lib/query";

export function useTeamGroups() {
  return useQuery({
    queryKey: ["autocomplete", "team-groups"],
    queryFn: getTeamGroups,
    staleTime: QUERY_STALE.autocomplete,
  });
}
