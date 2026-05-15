import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App bootstrap", () => {
  it("브랜드명을 렌더한다", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "CreditXLSX" })).toBeInTheDocument();
  });

  it("CX 로고 마크를 표시한다", () => {
    render(<App />);
    expect(screen.getByText("CX")).toBeInTheDocument();
  });

  it("Phase 7 UI bootstrap 안내를 보여준다", () => {
    render(<App />);
    expect(screen.getByText(/Phase 7 UI bootstrap/)).toBeInTheDocument();
  });
});
