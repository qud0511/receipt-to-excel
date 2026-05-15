import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  analyzeTemplate,
  createTemplate,
  deleteTemplate,
  getTemplateGrid,
  patchTemplateMapping,
  patchTemplateMeta,
} from "@/lib/api/templates";
import type { MappingPatchRequest } from "@/lib/api/types";
import { QUERY_STALE } from "@/lib/query";

export function useTemplateGrid(templateId: number | null) {
  return useQuery({
    queryKey: ["templates", templateId, "grid"],
    queryFn: () => getTemplateGrid(templateId!),
    staleTime: QUERY_STALE.templates,
    enabled: templateId != null,
  });
}

export function useAnalyzeTemplate() {
  return useMutation({
    mutationFn: analyzeTemplate,
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function usePatchTemplateMeta() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => patchTemplateMeta(id, { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function usePatchMapping(templateId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MappingPatchRequest) => patchTemplateMapping(templateId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      qc.invalidateQueries({ queryKey: ["templates", templateId, "grid"] });
    },
  });
}
