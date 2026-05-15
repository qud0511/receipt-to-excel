import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SummaryBar } from "./SummaryBar";

describe("SummaryBar", () => {
  it("총 N건 / 입력완료 M/N / 합계 표시", () => {
    render(<SummaryBar total={12} completed={7} sumAmount={1230000} dueDate="2026-05-25" />);
    expect(screen.getByText(/총/)).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/1,230,000원/)).toBeInTheDocument();
  });

  it("dueDate 기반 D-N 카운트다운 (today 인자 주입)", () => {
    render(
      <SummaryBar
        total={1}
        completed={0}
        sumAmount={0}
        dueDate="2026-05-25"
        today={new Date("2026-05-15")}
      />,
    );
    expect(screen.getByText(/D-10/)).toBeInTheDocument();
  });

  it("dueDate 가 지난 경우 'D+N' 표시", () => {
    render(
      <SummaryBar
        total={1}
        completed={0}
        sumAmount={0}
        dueDate="2026-05-10"
        today={new Date("2026-05-15")}
      />,
    );
    expect(screen.getByText(/D\+5/)).toBeInTheDocument();
  });
});
