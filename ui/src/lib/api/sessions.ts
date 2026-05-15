import { apiFetch, downloadUrl } from "./client";
import type {
  ArtifactKind,
  BulkTagRequest,
  BulkTagResponse,
  GenerateResponse,
  PreviewXlsxResponse,
  SessionCreatedResponse,
  SessionStats,
  TransactionListResponse,
  TransactionPatchRequest,
  TransactionView,
} from "./types";
import type { VerifyFilter } from "@/lib/constants";

export interface CreateSessionInput {
  receipts: File[];
  card_statements: File[];
  year_month: string;
  template_id: number;
}

export function createSession(input: CreateSessionInput): Promise<SessionCreatedResponse> {
  const fd = new FormData();
  for (const f of input.receipts) fd.append("receipts", f, f.name);
  for (const f of input.card_statements) fd.append("card_statements", f, f.name);
  fd.append("year_month", input.year_month);
  fd.append("template_id", String(input.template_id));
  return apiFetch<SessionCreatedResponse>("/sessions", { method: "POST", formData: fd });
}

export function getTransactions(
  sessionId: number,
  status: VerifyFilter = "all",
): Promise<TransactionListResponse> {
  return apiFetch<TransactionListResponse>(`/sessions/${sessionId}/transactions?status=${status}`);
}

export function patchTransaction(
  sessionId: number,
  txId: number,
  patch: TransactionPatchRequest,
): Promise<{ updated: TransactionView }> {
  return apiFetch(`/sessions/${sessionId}/transactions/${txId}`, { method: "PATCH", body: patch });
}

export function bulkTag(sessionId: number, payload: BulkTagRequest): Promise<BulkTagResponse> {
  return apiFetch(`/sessions/${sessionId}/transactions/bulk-tag`, { method: "POST", body: payload });
}

export function receiptUrl(sessionId: number, txId: number): string {
  return downloadUrl(`/sessions/${sessionId}/transactions/${txId}/receipt`);
}

export function getPreviewXlsx(sessionId: number): Promise<PreviewXlsxResponse> {
  return apiFetch(`/sessions/${sessionId}/preview-xlsx`);
}

export function generate(sessionId: number): Promise<GenerateResponse> {
  return apiFetch(`/sessions/${sessionId}/generate`, { method: "POST" });
}

export function downloadArtifactUrl(sessionId: number, kind: ArtifactKind): string {
  return downloadUrl(`/sessions/${sessionId}/download/${kind}`);
}

export function getSessionStats(sessionId: number): Promise<SessionStats> {
  return apiFetch(`/sessions/${sessionId}/stats`);
}
