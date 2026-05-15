import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "./KpiCard";

describe("KpiCard", () => {
  it("label + value + delta 렌더", () => {
    render(<KpiCard label="이번 달 총 지출" value="1,230,000원" delta="▲ 8.5%" deltaTone="up" />);
    expect(screen.getByText("이번 달 총 지출")).toBeInTheDocument();
    expect(screen.getByText("1,230,000원")).toBeInTheDocument();
    expect(screen.getByText("▲ 8.5%")).toBeInTheDocument();
  });

  it("deltaTone=up 시 success 색", () => {
    render(<KpiCard label="결제 건수" value="12" delta="3건 미입력" deltaTone="up" />);
    const delta = screen.getByText("3건 미입력");
    expect(delta.className).toMatch(/text-success|text-conf-high/);
  });

  it("delta 가 없으면 표시 안 함", () => {
    render(<KpiCard label="X" value="0" />);
    expect(screen.queryByText(/▲|▼/)).not.toBeInTheDocument();
  });
});
