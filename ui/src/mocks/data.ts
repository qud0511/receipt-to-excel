/** dev MSW 용 mock 데이터 — 5 화면 풀 시나리오. */
import type {
  AttendeeView,
  DashboardSummaryResponse,
  GenerateResponse,
  GridResponse,
  ProjectView,
  SessionStats,
  TeamGroupView,
  TemplateSummary,
  TransactionListResponse,
  TransactionView,
  VendorView,
} from "@/lib/api/types";

export const MOCK_USER = { name: "홍길동", email: "honggildong@example.com" };

export const MOCK_TEMPLATES: TemplateSummary[] = [
  {
    id: 1,
    name: "A사 파견용 양식",
    is_default: true,
    mapping_status: "mapped",
    created_at: "2026-05-01T00:00:00",
    updated_at: "2026-05-12T00:00:00",
  },
  {
    id: 2,
    name: "코스콤 외주 양식",
    is_default: false,
    mapping_status: "needs_mapping",
    created_at: "2026-04-15T00:00:00",
    updated_at: "2026-04-15T00:00:00",
  },
];

export const MOCK_GRID: GridResponse = {
  sheets: {
    지출결의서: {
      sheet_name: "지출결의서",
      max_row: 22,
      max_col: 9,
      cells: [
        { row: 1, col: 1, value: "지     출     결     의     서", is_formula: false },
        { row: 3, col: 1, value: "작성자", is_formula: false },
        { row: 3, col: 2, value: "홍길동", is_formula: false },
        { row: 3, col: 5, value: "정산월", is_formula: false },
        { row: 3, col: 6, value: "2026.05", is_formula: false },
        { row: 7, col: 1, value: "연번", is_formula: false },
        { row: 7, col: 2, value: "거래일", is_formula: false },
        { row: 7, col: 3, value: "거래처", is_formula: false },
        { row: 7, col: 4, value: "프로젝트", is_formula: false },
        { row: 7, col: 5, value: "용도", is_formula: false },
        { row: 7, col: 6, value: "인원", is_formula: false },
        { row: 7, col: 7, value: "금액", is_formula: false },
        { row: 7, col: 8, value: "참석자", is_formula: false },
        { row: 7, col: 9, value: "비고", is_formula: false },
        { row: 19, col: 7, value: "=SUM(G8:G18)", is_formula: true },
      ],
    },
    증빙요약: {
      sheet_name: "증빙요약",
      max_row: 8,
      max_col: 5,
      cells: [
        { row: 1, col: 1, value: "증빙요약", is_formula: false },
      ],
    },
  },
};

export const MOCK_DASHBOARD: DashboardSummaryResponse = {
  user_name: MOCK_USER.name,
  this_month: {
    total_amount: 1230000,
    transaction_count: 12,
    pending_count: 3,
    prev_month_diff_pct: 8.5,
  },
  this_year: { completed_count: 7, time_saved_hours: 14 },
  recent_expense_reports: [
    {
      session_id: 1,
      year_month: "2026-05",
      template_name: "A사 파견용 양식",
      receipt_count: 12,
      total_amount: 1230000,
      status: "awaiting_user",
      is_submitted: false,
      updated_at: "2026-05-15T10:30:00",
    },
    {
      session_id: 2,
      year_month: "2026-04",
      template_name: "A사 파견용 양식",
      receipt_count: 8,
      total_amount: 740000,
      status: "submitted",
      is_submitted: true,
      updated_at: "2026-04-28T16:00:00",
    },
  ],
};

export const MOCK_VENDORS: VendorView[] = [
  { id: 1, name: "신용정보원", last_used_at: "2026-05-12T12:00:00", usage_count: 23 },
  { id: 2, name: "한국은행", last_used_at: "2026-05-04T13:30:00", usage_count: 8 },
  { id: 3, name: "금융결제원", last_used_at: "2026-04-22T15:00:00", usage_count: 5 },
  { id: 4, name: "코스콤", last_used_at: null, usage_count: 3 },
  { id: 5, name: "예금보험공사", last_used_at: null, usage_count: 1 },
];

export const MOCK_PROJECTS_BY_VENDOR: Record<number, ProjectView[]> = {
  1: [
    { id: 11, vendor_id: 1, name: "차세대 IT시스템 구축", last_used_at: "2026-05-12T12:00:00", usage_count: 18 },
    { id: 12, vendor_id: 1, name: "CB 데이터 통합", last_used_at: "2026-04-30T00:00:00", usage_count: 4 },
    { id: 13, vendor_id: 1, name: "모바일 인증 고도화", last_used_at: null, usage_count: 1 },
  ],
  2: [
    { id: 21, vendor_id: 2, name: "데이터 플랫폼 PoC", last_used_at: "2026-05-04T00:00:00", usage_count: 6 },
    { id: 22, vendor_id: 2, name: "BOK Wallet 연구", last_used_at: null, usage_count: 2 },
  ],
  3: [{ id: 31, vendor_id: 3, name: "오픈뱅킹 v3 개편", last_used_at: null, usage_count: 5 }],
  4: [{ id: 41, vendor_id: 4, name: "장외파생 시스템 리뉴얼", last_used_at: null, usage_count: 3 }],
  5: [{ id: 51, vendor_id: 5, name: "회수관리 차세대", last_used_at: null, usage_count: 1 }],
};

export const MOCK_TEAM_GROUPS: TeamGroupView[] = [
  {
    id: 1,
    name: "개발1팀",
    members: [
      { id: 1, name: "홍길동" },
      { id: 2, name: "김지호" },
      { id: 3, name: "박서연" },
      { id: 4, name: "이도윤" },
    ],
  },
  {
    id: 2,
    name: "기획팀",
    members: [
      { id: 5, name: "오세훈" },
      { id: 6, name: "윤아름" },
    ],
  },
];

export const MOCK_ATTENDEES: AttendeeView[] = MOCK_TEAM_GROUPS.flatMap((g) =>
  g.members.map((m) => ({ name: m.name, team: g.name })),
);

export const MOCK_TRANSACTIONS: TransactionView[] = [
  {
    id: 1,
    가맹점명: "본가설렁탕 강남점",
    거래일: "2026-05-12",
    거래시각: "12:38:00",
    금액: 78000,
    업종: "한식",
    카드사: "shinhan",
    카드번호_마스킹: "****3821",
    parser_used: "rule_based",
    field_confidence: { 가맹점명: "high", 거래일: "high", 금액: "high", 카드번호_마스킹: "high" },
    confidence_score: 0.92,
    vendor: "신용정보원",
    project: "차세대 IT시스템 구축",
    purpose: "중식",
    headcount: 3,
    attendees: ["홍길동", "김지호", "박서연"],
  },
  {
    id: 2,
    가맹점명: "카카오T 택시",
    거래일: "2026-05-12",
    거래시각: "19:24:00",
    금액: 14300,
    업종: "교통",
    카드사: "samsung",
    카드번호_마스킹: "****3821",
    parser_used: "rule_based",
    field_confidence: { 가맹점명: "high", 거래일: "high", 금액: "high", 업종: "medium" },
    confidence_score: 0.78,
    vendor: "신용정보원",
    project: "차세대 IT시스템 구축",
    purpose: "택시",
    headcount: 1,
    attendees: ["홍길동"],
  },
  {
    id: 3,
    가맹점명: "광화문 미진",
    거래일: "2026-05-13",
    거래시각: "20:48:00",
    금액: 156000,
    업종: "한식",
    카드사: "shinhan",
    카드번호_마스킹: "****3821",
    parser_used: "ocr_hybrid",
    field_confidence: { 가맹점명: "high", 거래일: "high", 금액: "high", 업종: "low" },
    confidence_score: 0.55,
    vendor: null,
    project: null,
    purpose: "석식",
    headcount: 6,
    attendees: [],
  },
];

export function mockTransactions(filter: string): TransactionListResponse {
  const status = (t: TransactionView): "missing" | "review" | "complete" => {
    if (!t.vendor || !t.purpose) return "missing";
    const low = Object.values(t.field_confidence).some((c) => c === "low" || c === "none");
    if (low || t.confidence_score < 0.6) return "review";
    return "complete";
  };
  const all = MOCK_TRANSACTIONS;
  const filtered =
    filter === "all" ? all : all.filter((t) => status(t) === (filter as "missing" | "review" | "complete"));
  const counts = {
    all: all.length,
    missing: all.filter((t) => status(t) === "missing").length,
    review: all.filter((t) => status(t) === "review").length,
    complete: all.filter((t) => status(t) === "complete").length,
  };
  return { transactions: filtered, counts };
}

export const MOCK_SESSION_STATS: SessionStats = {
  session_id: 1,
  processing_time_s: 138,
  baseline_s: 50400, // 14h = 56 거래 × 15분
  time_saved_s: 50262,
  transaction_count: 3,
};

export const MOCK_GENERATE: GenerateResponse = {
  artifacts: [
    { kind: "xlsx", url: "/api/sessions/1/download/xlsx" },
    { kind: "layout_pdf", url: "/api/sessions/1/download/layout_pdf" },
    { kind: "merged_pdf", url: "/api/sessions/1/download/merged_pdf" },
    { kind: "zip", url: "/api/sessions/1/download/zip" },
  ],
};
