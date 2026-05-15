import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilterChips } from "./FilterChips";

const counts = { all: 12, missing: 3, review: 2, complete: 7 };

describe("FilterChips", () => {
  it("4 filter chip 렌더 + 한국어 라벨", () => {
    render(<FilterChips current="all" counts={counts} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /전체/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /필수 누락/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /재확인 필요/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /완료/ })).toBeInTheDocument();
  });

  it("각 chip 에 counts 숫자 표시", () => {
    render(<FilterChips current="all" counts={counts} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /전체/ })).toHaveTextContent("12");
    expect(screen.getByRole("button", { name: /필수 누락/ })).toHaveTextContent("3");
  });

  it("active chip 강조", () => {
    render(<FilterChips current="missing" counts={counts} onChange={() => {}} />);
    const missing = screen.getByRole("button", { name: /필수 누락/ });
    expect(missing).toHaveAttribute("aria-pressed", "true");
  });

  it("클릭 시 onChange callback", async () => {
    const fn = vi.fn();
    render(<FilterChips current="all" counts={counts} onChange={fn} />);
    await userEvent.click(screen.getByRole("button", { name: /완료/ }));
    expect(fn).toHaveBeenCalledWith("complete");
  });
});
