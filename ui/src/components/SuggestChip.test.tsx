import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SuggestChip } from "./SuggestChip";

describe("SuggestChip", () => {
  it("라벨 렌더", () => {
    render(<SuggestChip label="신용정보원" />);
    expect(screen.getByRole("button", { name: /신용정보원/ })).toBeInTheDocument();
  });

  it("recent 시 '최근' 뱃지 표시", () => {
    render(<SuggestChip label="한국은행" recent />);
    expect(screen.getByText("최근")).toBeInTheDocument();
  });

  it("active 시 brand 색", () => {
    render(<SuggestChip label="금융결제원" active />);
    expect(screen.getByRole("button").className).toMatch(/brand/);
  });

  it("클릭 시 onPick 호출", async () => {
    const fn = vi.fn();
    render(<SuggestChip label="코스콤" onPick={fn} />);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledWith("코스콤");
  });
});
