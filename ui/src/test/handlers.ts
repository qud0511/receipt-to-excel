import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

/**
 * MSW handler 카탈로그.
 * 24 endpoint mock 은 Phase 7.3 부터 채워짐 — 본 setup 단계는 healthz 만 mock.
 */
export const handlers = [
  http.get("/healthz", () => HttpResponse.json({ status: "ok" })),
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),
  // 기본 빈 응답 — 개별 test 가 server.use() 로 override
  http.get("/api/templates", () => HttpResponse.json([])),
  http.get("/api/dashboard/summary", () =>
    HttpResponse.json({
      user_name: "테스트",
      this_month: { total_amount: 0, transaction_count: 0, pending_count: 0, prev_month_diff_pct: 0 },
      this_year: { completed_count: 0, time_saved_hours: 0 },
      recent_expense_reports: [],
    }),
  ),
];

export const server = setupServer(...handlers);
