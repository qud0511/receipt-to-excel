import { useQuery } from "@tanstack/react-query";
import { listTemplates } from "@/lib/api/templates";
import { QUERY_STALE } from "@/lib/query";

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: listTemplates,
    staleTime: QUERY_STALE.templates,
  });
}
