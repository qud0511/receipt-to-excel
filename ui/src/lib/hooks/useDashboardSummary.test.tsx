import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useDashboardSummary } from "./useDashboardSummary";
import type { DashboardSummaryResponse } from "@/lib/api/types";

function wrapper(client?: QueryClient) {
  const qc = client ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrap = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrap.displayName = "TestQueryWrapper";
  return Wrap;
}

describe("useDashboardSummary", () => {
  it("GET /dashboard/summary 응답을 그대로 반환", async () => {
    const payload: DashboardSummaryResponse = {
      user_name: "홍길동",
      this_month: { total_amount: 1230000, transaction_count: 12, pending_count: 3, prev_month_diff_pct: 8.5 },
      this_year: { completed_count: 7, time_saved_hours: 14 },
      recent_expense_reports: [],
    };
    server.use(http.get("/api/dashboard/summary", () => HttpResponse.json(payload)));

    const { result } = renderHook(() => useDashboardSummary(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
  });
});
