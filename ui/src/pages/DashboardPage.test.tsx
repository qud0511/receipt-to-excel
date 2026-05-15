import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "./DashboardPage";
import type { DashboardSummaryResponse } from "@/lib/api/types";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("Dashboard summary 로딩 + KPI 4 + 최근 결의서 표시", async () => {
    const payload: DashboardSummaryResponse = {
      user_name: "홍길동",
      this_month: { total_amount: 1230000, transaction_count: 12, pending_count: 3, prev_month_diff_pct: 8.5 },
      this_year: { completed_count: 7, time_saved_hours: 14 },
      recent_expense_reports: [
        {
          session_id: 1,
          year_month: "2026-05",
          template_name: "A사 양식",
          receipt_count: 12,
          total_amount: 1230000,
          status: "submitted",
          is_submitted: true,
          updated_at: "2026-05-12T10:30:00",
        },
      ],
    };
    server.use(http.get("/api/dashboard/summary", () => HttpResponse.json(payload)));

    renderPage();

    // KPI + RecentList row 양쪽에 1,230,000원이 나타남
    await waitFor(() => expect(screen.getAllByText("1,230,000원").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText(/이번 달 총 지출/)).toBeInTheDocument();
    expect(screen.getByText(/결제 건수/)).toBeInTheDocument();
    expect(screen.getByText(/완료된 결의서/)).toBeInTheDocument();
    expect(screen.getByText(/절약된 시간/)).toBeInTheDocument();
    expect(screen.getByText("홍길동")).toBeInTheDocument();
    expect(screen.getByText("A사 양식")).toBeInTheDocument();
  });

  it("미입력 N건 강조 표시", async () => {
    server.use(
      http.get("/api/dashboard/summary", () =>
        HttpResponse.json({
          user_name: "홍길동",
          this_month: { total_amount: 0, transaction_count: 8, pending_count: 5, prev_month_diff_pct: 0 },
          this_year: { completed_count: 0, time_saved_hours: 0 },
          recent_expense_reports: [],
        }),
      ),
    );
    renderPage();
    await waitFor(() => expect(screen.getByText(/5건 미입력/)).toBeInTheDocument());
  });
});
