import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecentList } from "./RecentList";
import type { RecentExpenseReport } from "@/lib/api/types";

const sample: RecentExpenseReport[] = [
  {
    session_id: 7,
    year_month: "2026-05",
    template_name: "A사 파견용 양식",
    receipt_count: 12,
    total_amount: 1230000,
    status: "submitted",
    is_submitted: true,
    updated_at: "2026-05-12T10:30:00",
  },
  {
    session_id: 8,
    year_month: "2026-04",
    template_name: "신용정보원 결의서",
    receipt_count: 5,
    total_amount: 480000,
    status: "awaiting_user",
    is_submitted: false,
    updated_at: "2026-04-28T16:00:00",
  },
];

describe("RecentList", () => {
  it("빈 list 시 안내 문구", () => {
    render(
      <MemoryRouter>
        <RecentList items={[]} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/없습니다/)).toBeInTheDocument();
  });

  it("각 row: period · template · 영수증 N장 · 금액 · 상태", () => {
    render(
      <MemoryRouter>
        <RecentList items={sample} />
      </MemoryRouter>,
    );
    expect(screen.getByText("26.05")).toBeInTheDocument();
    expect(screen.getByText("A사 파견용 양식")).toBeInTheDocument();
    expect(screen.getByText(/영수증 12장/)).toBeInTheDocument();
    expect(screen.getByText("1,230,000원")).toBeInTheDocument();
    expect(screen.getByText("제출완료")).toBeInTheDocument();
    expect(screen.getByText("미입력")).toBeInTheDocument();
  });

  it("row 클릭 가능 (Verify 화면 link)", () => {
    render(
      <MemoryRouter>
        <RecentList items={sample} />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /A사 파견용 양식/ });
    expect(link).toHaveAttribute("href", "/verify/7");
  });
});
