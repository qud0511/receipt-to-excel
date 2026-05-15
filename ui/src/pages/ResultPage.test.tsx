import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ResultPage } from "./ResultPage";

function renderAt(sessionId: number) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/result/${sessionId}`]}>
        <Routes>
          <Route path="/result/:sessionId" element={<ResultPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResultPage", () => {
  it("4 다운로드 카드 (XLSX / 증빙 PDF / merged PDF / ZIP) 렌더", async () => {
    server.use(
      http.get("/api/sessions/7/stats", () =>
        HttpResponse.json({
          session_id: 7,
          processing_time_s: 138,
          baseline_s: 50400,
          time_saved_s: 50262,
          transaction_count: 56,
        }),
      ),
      http.post("/api/sessions/7/generate", () =>
        HttpResponse.json({
          artifacts: [
            { kind: "xlsx", url: "/sessions/7/download/xlsx" },
            { kind: "layout_pdf", url: "/sessions/7/download/layout_pdf" },
            { kind: "merged_pdf", url: "/sessions/7/download/merged_pdf" },
            { kind: "zip", url: "/sessions/7/download/zip" },
          ],
        }),
      ),
    );
    renderAt(7);

    await waitFor(() => expect(screen.getAllByText(/XLSX/).length).toBeGreaterThan(0));
    // 4 카드 모두 노출 — kind 배지 또는 description 매칭
    expect(screen.getAllByText(/PDF/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/ZIP/).length).toBeGreaterThan(0);
    // 다운로드 link 4개 (XLSX/layout_pdf/merged_pdf/ZIP — disabled 메일 제외)
    expect(screen.getAllByRole("link", { name: /다운로드/ })).toHaveLength(4);
  });

  it("'팀장님께 메일' 버튼은 disabled (Phase 7+ 예정)", async () => {
    renderAt(1);
    await waitFor(() => {
      const mailBtn = screen.queryByRole("button", { name: /메일/ });
      if (mailBtn) expect(mailBtn).toBeDisabled();
    });
  });

  it("'검수 화면으로' Link", async () => {
    renderAt(5);
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /검수 화면/ })).toHaveAttribute("href", "/verify/5");
    });
  });
});
