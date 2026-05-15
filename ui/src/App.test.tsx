import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App routing", () => {
  it("/ 경로 진입 시 Dashboard 페이지 렌더 (CreditXLSX 브랜드 노출)", () => {
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(screen.getByText("CreditXLSX")).toBeInTheDocument();
  });

  it("/upload 경로 진입 시 step indicator 노출", () => {
    window.history.pushState({}, "", "/upload");
    render(<App />);
    expect(screen.getByText("업로드")).toBeInTheDocument();
  });

  it("/templates 경로 진입 시 템플릿 페이지 헤더", () => {
    window.history.pushState({}, "", "/templates");
    render(<App />);
    expect(screen.getByRole("heading", { name: /템플릿/ })).toBeInTheDocument();
  });
});
