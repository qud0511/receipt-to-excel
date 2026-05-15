import type { Page, Route } from "@playwright/test";

/** 공통 API mock 등록 — 각 spec 첫 줄에서 호출 */
export async function mountMocks(page: Page): Promise<void> {
  // Dashboard
  await page.route("**/api/dashboard/summary", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user_name: "홍길동",
        this_month: { total_amount: 1230000, transaction_count: 12, pending_count: 3, prev_month_diff_pct: 8.5 },
        this_year: { completed_count: 7, time_saved_hours: 14 },
        recent_expense_reports: [
          {
            session_id: 1,
            year_month: "2026-05",
            template_name: "A사 파견용 양식",
            receipt_count: 12,
            total_amount: 1230000,
            status: "submitted",
            is_submitted: true,
            updated_at: "2026-05-12T10:30:00",
          },
        ],
      }),
    }),
  );

  // Templates list
  await page.route("**/api/templates", (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
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
      ]),
    });
  });

  // Templates grid
  await page.route("**/api/templates/*/grid", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sheets: {
          지출결의서: {
            sheet_name: "지출결의서",
            max_row: 12,
            max_col: 8,
            cells: [
              { row: 1, col: 1, value: "지출결의서", is_formula: false },
              { row: 3, col: 1, value: "작성자", is_formula: false },
              { row: 3, col: 2, value: "홍길동", is_formula: false },
              { row: 6, col: 1, value: "거래일", is_formula: false },
              { row: 6, col: 2, value: "거래처", is_formula: false },
              { row: 6, col: 3, value: "금액", is_formula: false },
              { row: 19, col: 3, value: "=SUM(C7:C18)", is_formula: true },
            ],
          },
        },
      }),
    }),
  );

  // Sessions transactions
  await page.route("**/api/sessions/*/transactions*", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        transactions: [
          {
            id: 1,
            가맹점명: "본가설렁탕 강남점",
            거래일: "2025-12-02",
            거래시각: "12:38",
            금액: 78000,
            업종: "한식",
            카드사: "shinhan",
            카드번호_마스킹: "****3821",
            parser_used: "rule_based",
            field_confidence: { 가맹점명: "high", 거래일: "high", 금액: "high" },
            confidence_score: 0.85,
            vendor: "신용정보원",
            project: "차세대 IT시스템 구축",
            purpose: "중식",
            headcount: 3,
            attendees: ["홍길동"],
          },
          {
            id: 2,
            가맹점명: "광화문 미진",
            거래일: "2025-12-03",
            거래시각: "20:48",
            금액: 156000,
            업종: "한식",
            카드사: "shinhan",
            카드번호_마스킹: "****3821",
            parser_used: "ocr_hybrid",
            field_confidence: { 가맹점명: "high", 거래일: "high", 금액: "high" },
            confidence_score: 0.42,
            vendor: null,
            project: null,
            purpose: null,
            headcount: null,
            attendees: [],
          },
        ],
        counts: { all: 2, missing: 1, review: 0, complete: 1 },
      }),
    }),
  );

  // Sessions stats + generate
  await page.route("**/api/sessions/*/stats", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: 1,
        processing_time_s: 138,
        baseline_s: 50400,
        time_saved_s: 50262,
        transaction_count: 56,
      }),
    }),
  );
  await page.route("**/api/sessions/*/generate", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        artifacts: [
          { kind: "xlsx", url: "/sessions/1/download/xlsx" },
          { kind: "layout_pdf", url: "/sessions/1/download/layout_pdf" },
          { kind: "merged_pdf", url: "/sessions/1/download/merged_pdf" },
          { kind: "zip", url: "/sessions/1/download/zip" },
        ],
      }),
    }),
  );

  // Autocomplete (fallback empty)
  await page.route("**/api/vendors*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/projects*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/attendees*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/team-groups", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}
