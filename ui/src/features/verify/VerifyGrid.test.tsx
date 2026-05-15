import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VerifyGrid } from "./VerifyGrid";
import type { TransactionView } from "@/lib/api/types";

const rows: TransactionView[] = [
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
];

describe("VerifyGrid", () => {
  it("9 컬럼 헤더 + row 렌더", () => {
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={null} />);
    expect(screen.getByText(/AI신뢰도/)).toBeInTheDocument();
    expect(screen.getByText("일시")).toBeInTheDocument();
    expect(screen.getByText("가맹점")).toBeInTheDocument();
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText("거래처")).toBeInTheDocument();
    expect(screen.getByText("프로젝트")).toBeInTheDocument();
    expect(screen.getByText("용도")).toBeInTheDocument();
    expect(screen.getByText("인원")).toBeInTheDocument();
    expect(screen.getByText("본가설렁탕 강남점")).toBeInTheDocument();
    expect(screen.getByText("광화문 미진")).toBeInTheDocument();
  });

  it("신뢰도 % 표시 (confidence_score * 100)", () => {
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={null} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("42%")).toBeInTheDocument();
  });

  it("체크박스 클릭 시 onToggleSelect 호출", async () => {
    const fn = vi.fn();
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={null} onToggleSelect={fn} />);
    const cb = screen.getAllByRole("checkbox").find((el) => el.getAttribute("data-row-id") === "1");
    expect(cb).toBeDefined();
    await userEvent.click(cb!);
    expect(fn).toHaveBeenCalledWith(1, true);
  });

  it("row 클릭 시 onActivate 호출", async () => {
    const fn = vi.fn();
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={null} onActivate={fn} />);
    await userEvent.click(screen.getByText("본가설렁탕 강남점"));
    expect(fn).toHaveBeenCalledWith(1);
  });

  it("빈 거래처 셀에 입력 후 Enter 시 onPatch 호출", async () => {
    const fn = vi.fn();
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={null} onPatch={fn} />);
    // row 2 (id=2) 는 vendor=null — Autocomplete 셀이 typing 후 Enter 로 commit
    const inputs = screen.getAllByPlaceholderText("거래처 입력");
    const emptyVendorInput = inputs[1]!; // 두 번째 행
    await userEvent.click(emptyVendorInput);
    await userEvent.type(emptyVendorInput, "한국은행");
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(fn).toHaveBeenCalled());
    const lastCall = fn.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe(2);
    expect(lastCall?.[1]).toMatchObject({ vendor: "한국은행" });
  });

  it("active row 시각 강조", () => {
    render(<VerifyGrid rows={rows} selected={new Set()} activeId={2} />);
    const tr = screen.getByText("광화문 미진").closest("tr");
    expect(tr?.className).toMatch(/active/);
  });
});
