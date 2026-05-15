/**
 * 백엔드 schemas/*.py 와 1:1 매핑 TypeScript types.
 * 변경 시 backend schema + 본 파일 동시 갱신 (CLAUDE.md §"스키마 진화 PR 6요소").
 */

import type { Confidence } from "@/components/ConfidenceBadge";
import type { SessionStatusKey, VerifyFilter } from "@/lib/constants";

// ─── Common ──────────────────────────────────────────────────────────────────

export interface AppError {
  detail: string;
  code?: string;
  failed_tx_ids?: number[];
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export interface SessionCreatedResponse {
  session_id: number;
  status: "parsing";
}

export interface SessionSummary {
  session_id: number;
  year_month: string;
  status: SessionStatusKey;
  submitted_at: string | null;
  created_at: string;
  transaction_count: number;
  total_amount: number;
}

export interface TransactionView {
  id: number;
  가맹점명: string;
  거래일: string;
  거래시각: string | null;
  금액: number;
  업종: string | null;
  카드사: string;
  카드번호_마스킹: string | null;
  parser_used: string;
  field_confidence: Record<string, Confidence>;
  confidence_score: number;
  vendor: string | null;
  project: string | null;
  purpose: string | null;
  headcount: number | null;
  attendees: string[];
}

export interface TransactionListResponse {
  transactions: TransactionView[];
  counts: Record<VerifyFilter, number>;
}

export interface TransactionPatchRequest {
  vendor?: string | null;
  project?: string | null;
  purpose?: string | null;
  headcount?: number | null;
  attendees?: string[] | null;
  note?: string | null;
}

export interface BulkTagRequest {
  transaction_ids: number[];
  patch: TransactionPatchRequest;
}

export interface BulkTagResponse {
  updated_count: number;
}

export interface PreviewXlsxResponse {
  sheets: Record<string, Array<Array<string | number | null>>>;
}

export interface GenerateResponse {
  artifacts: Array<{ kind: ArtifactKind; url: string }>;
}

export type ArtifactKind = "xlsx" | "merged_pdf" | "layout_pdf" | "zip";

export interface SessionStats {
  session_id: number;
  processing_time_s: number;
  baseline_s: number;
  time_saved_s: number;
  transaction_count: number;
}

// ─── Templates ───────────────────────────────────────────────────────────────

export interface TemplateSummary {
  id: number;
  name: string;
  is_default: boolean;
  mapping_status: "mapped" | "needs_mapping";
  created_at: string;
  updated_at: string;
}

export interface SheetConfigView {
  sheet_name: string;
  sheet_kind: string | null;
  mode: "field" | "category" | "hybrid";
  analyzable: boolean;
  date_col: string | null;
  merchant_col: string | null;
  project_col: string | null;
  total_col: string | null;
  note_col: string | null;
  category_cols: Record<string, string>;
  formula_cols: string[];
  data_start_row: number;
  data_end_row: number;
  sum_row: number | null;
  header_row: number;
}

export interface AnalyzedTemplateResponse {
  sheets: Record<string, SheetConfigView>;
  mapping_status: "mapped" | "needs_mapping";
}

export interface TemplateCreatedResponse {
  template_id: number;
  name: string;
  mapping_status: "mapped" | "needs_mapping";
}

export interface GridCell {
  row: number;
  col: number;
  value: string | number | null;
  is_formula: boolean;
}

export interface GridSheetView {
  sheet_name: string;
  cells: GridCell[];
  max_row: number;
  max_col: number;
}

export interface GridResponse {
  sheets: Record<string, GridSheetView>;
}

export interface CellPatchItem {
  sheet: string;
  row: number;
  col: number;
  value: string | number | null;
}

export interface CellsPatchRequest {
  cells: CellPatchItem[];
}

export interface MappingPatchRequest {
  sheet: string;
  column_map: Partial<{
    date_col: string | null;
    merchant_col: string | null;
    project_col: string | null;
    total_col: string | null;
    note_col: string | null;
  }>;
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface RecentExpenseReport {
  session_id: number;
  year_month: string;
  template_name: string | null;
  receipt_count: number;
  total_amount: number;
  status: SessionStatusKey;
  is_submitted: boolean;
  updated_at: string;
}

export interface ThisMonthMetric {
  total_amount: number;
  transaction_count: number;
  pending_count: number;
  prev_month_diff_pct: number;
}

export interface ThisYearMetric {
  completed_count: number;
  time_saved_hours: number;
}

export interface DashboardSummaryResponse {
  user_name: string;
  this_month: ThisMonthMetric;
  this_year: ThisYearMetric;
  recent_expense_reports: RecentExpenseReport[];
}

// ─── Autocomplete ────────────────────────────────────────────────────────────

export interface VendorView {
  id: number;
  name: string;
  last_used_at: string | null;
  usage_count: number;
}

export interface ProjectView {
  id: number;
  vendor_id: number;
  name: string;
  last_used_at: string | null;
  usage_count: number;
}

export interface TeamMemberView {
  id: number;
  name: string;
}

export interface TeamGroupView {
  id: number;
  name: string;
  members: TeamMemberView[];
}

export interface AttendeeView {
  name: string;
  team: string;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface AuthConfig {
  require_auth: boolean;
  tenant_id: string | null;
  client_id: string | null;
}

export interface UserInfo {
  oid: string;
  name: string;
  email: string;
}

// ─── SSE ─────────────────────────────────────────────────────────────────────

export type SSEStage =
  | "uploaded"
  | "ocr"
  | "llm"
  | "rule_based"
  | "resolved"
  | "vendor_failed"
  | "done"
  | "error";

export interface SSEMessage {
  stage: SSEStage;
  file_idx: number;
  total: number;
  filename: string;
  msg: string;
  tx_id: number | null;
}
