import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PurposeTile } from "./PurposeTile";
import { PURPOSES } from "@/lib/constants";

describe("PurposeTile", () => {
  it("용도 라벨 + 이모지 렌더", () => {
    render(<PurposeTile purpose="중식" />);
    expect(screen.getByRole("button", { name: /중식/ })).toBeInTheDocument();
  });

  it("active 시 brand 색", () => {
    render(<PurposeTile purpose="택시" active />);
    expect(screen.getByRole("button").className).toMatch(/brand/);
  });

  it("클릭 시 onSelect 호출", async () => {
    const fn = vi.fn();
    render(<PurposeTile purpose="회의" onSelect={fn} />);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledWith("회의");
  });

  it("PURPOSES 상수는 6종 (중식/석식/회의/택시/간식/출장)", () => {
    expect(PURPOSES).toEqual(["중식", "석식", "회의", "택시", "간식", "출장"]);
  });
});
