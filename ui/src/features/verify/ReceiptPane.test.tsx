import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReceiptPane } from "./ReceiptPane";
import type { TransactionView } from "@/lib/api/types";

const sample: TransactionView = {
  id: 1,
  가맹점명: "본가설렁탕 강남점",
  거래일: "2025-12-02",
  거래시각: "12:38:00",
  금액: 78000,
  업종: "한식",
  카드사: "shinhan",
  카드번호_마스킹: "****3821",
  parser_used: "rule_based",
  field_confidence: { 가맹점명: "high", 금액: "high", 거래일: "high" },
  confidence_score: 0.92,
  vendor: "신용정보원",
  project: "차세대 IT시스템 구축",
  purpose: "중식",
  headcount: 3,
  attendees: ["홍길동"],
};

describe("ReceiptPane", () => {
  it("선택된 row 의 가맹점 + 금액 + 거래일 표시", () => {
    render(<ReceiptPane sessionId={1} active={sample} index={0} total={1} />);
    expect(screen.getByText("본가설렁탕 강남점")).toBeInTheDocument();
    expect(screen.getByText(/78,000/)).toBeInTheDocument();
    expect(screen.getByText(/2025\.12\.02/)).toBeInTheDocument();
  });

  it("카드 정보 (카드사 + 마스킹 번호)", () => {
    render(<ReceiptPane sessionId={1} active={sample} index={0} total={1} />);
    expect(screen.getByText(/\*\*\*\*3821/)).toBeInTheDocument();
  });

  it("active 가 null 이면 빈 안내", () => {
    render(<ReceiptPane sessionId={1} active={null} index={0} total={0} />);
    expect(screen.getByText(/선택된 거래가 없습니다/)).toBeInTheDocument();
  });

  it("prev/next 버튼 클릭 callback", async () => {
    const onPrev = vi.fn();
    const onNext = vi.fn();
    render(
      <ReceiptPane sessionId={1} active={sample} index={2} total={5} onPrev={onPrev} onNext={onNext} />,
    );
    await userEvent.click(screen.getByLabelText(/이전/));
    await userEvent.click(screen.getByLabelText(/다음/));
    expect(onPrev).toHaveBeenCalledOnce();
    expect(onNext).toHaveBeenCalledOnce();
  });

  it("페이지 표시 (3/5)", () => {
    render(<ReceiptPane sessionId={1} active={sample} index={2} total={5} />);
    expect(screen.getByText(/3 \/ 5/)).toBeInTheDocument();
  });
});
