import { apiFetch, downloadUrl } from "./client";
import type {
  AnalyzedTemplateResponse,
  CellsPatchRequest,
  GridResponse,
  MappingPatchRequest,
  TemplateCreatedResponse,
  TemplateSummary,
} from "./types";

export function listTemplates(): Promise<TemplateSummary[]> {
  return apiFetch("/templates");
}

export function analyzeTemplate(file: File): Promise<AnalyzedTemplateResponse> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  return apiFetch("/templates/analyze", { method: "POST", formData: fd });
}

export function createTemplate(input: { file: File; name: string }): Promise<TemplateCreatedResponse> {
  const fd = new FormData();
  fd.append("file", input.file, input.file.name);
  fd.append("name", input.name);
  return apiFetch("/templates", { method: "POST", formData: fd });
}

export function getTemplateGrid(templateId: number): Promise<GridResponse> {
  return apiFetch(`/templates/${templateId}/grid`);
}

export function patchTemplateCells(templateId: number, payload: CellsPatchRequest): Promise<void> {
  return apiFetch(`/templates/${templateId}/cells`, { method: "PATCH", body: payload });
}

export function patchTemplateMapping(templateId: number, payload: MappingPatchRequest): Promise<void> {
  return apiFetch(`/templates/${templateId}/mapping`, { method: "PATCH", body: payload });
}

export function patchTemplateMeta(templateId: number, payload: { name?: string }): Promise<void> {
  return apiFetch(`/templates/${templateId}`, { method: "PATCH", body: payload });
}

export function deleteTemplate(templateId: number): Promise<void> {
  return apiFetch(`/templates/${templateId}`, { method: "DELETE" });
}

export function templateRawUrl(templateId: number): string {
  return downloadUrl(`/templates/${templateId}/raw`);
}
