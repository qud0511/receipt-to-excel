import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepIndicator } from "./StepIndicator";

describe("StepIndicator", () => {
  it("3개 step 을 모두 렌더 (① 업로드 → ② 검수·수정 → ③ 다운로드)", () => {
    render(<StepIndicator current="upload" />);
    expect(screen.getByText("업로드")).toBeInTheDocument();
    expect(screen.getByText(/검수/)).toBeInTheDocument();
    expect(screen.getByText("다운로드")).toBeInTheDocument();
  });

  it("current=upload 면 1번 step active", () => {
    render(<StepIndicator current="upload" />);
    const upload = screen.getByText("업로드").closest("li");
    expect(upload?.className).toMatch(/active/);
  });

  it("current=verify 면 1번 done, 2번 active", () => {
    render(<StepIndicator current="verify" />);
    expect(screen.getByText("업로드").closest("li")?.className).toMatch(/done/);
    expect(screen.getByText(/검수/).closest("li")?.className).toMatch(/active/);
  });

  it("current=result 면 1,2 done, 3 active", () => {
    render(<StepIndicator current="result" />);
    expect(screen.getByText("업로드").closest("li")?.className).toMatch(/done/);
    expect(screen.getByText(/검수/).closest("li")?.className).toMatch(/done/);
    expect(screen.getByText("다운로드").closest("li")?.className).toMatch(/active/);
  });
});
