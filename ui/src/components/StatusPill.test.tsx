import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("tagged 상태는 '입력완료' 표시 + success 톤", () => {
    render(<StatusPill tagged />);
    const el = screen.getByText("입력완료");
    expect(el).toBeInTheDocument();
    expect(el.closest("span")?.className).toMatch(/text-success/);
  });

  it("untagged 상태는 '미입력' 표시", () => {
    render(<StatusPill tagged={false} />);
    expect(screen.getByText("미입력")).toBeInTheDocument();
  });

  it("Session.status 매핑: parsing/awaiting_user/submitted/failed → 한글 표시", () => {
    const { rerender, getByText } = render(<StatusPill sessionStatus="parsing" />);
    expect(getByText("작성중")).toBeInTheDocument();
    rerender(<StatusPill sessionStatus="awaiting_user" />);
    expect(getByText("미입력")).toBeInTheDocument();
    rerender(<StatusPill sessionStatus="submitted" />);
    expect(getByText("제출완료")).toBeInTheDocument();
    rerender(<StatusPill sessionStatus="failed" />);
    expect(getByText("실패")).toBeInTheDocument();
  });
});
