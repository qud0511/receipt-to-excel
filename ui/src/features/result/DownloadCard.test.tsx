import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DownloadCard } from "./DownloadCard";

describe("DownloadCard", () => {
  it("kind=xlsx 카드 + 다운로드 link", () => {
    render(
      <DownloadCard
        kind="xlsx"
        name="2026_05_지출결의서_홍길동.xlsx"
        desc="자동 합계 포함"
        href="/api/sessions/1/download/xlsx"
      />,
    );
    expect(screen.getByText("2026_05_지출결의서_홍길동.xlsx")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /다운로드/ })).toHaveAttribute(
      "href",
      "/api/sessions/1/download/xlsx",
    );
  });

  it("primary variant 강조", () => {
    render(<DownloadCard kind="zip" name="bundle.zip" desc="" href="/x" primary />);
    const link = screen.getByRole("link", { name: /다운로드/ });
    expect(link.className).toMatch(/bg-brand/);
  });

  it("disabled 시 link 가 button (anchor 비활성)", () => {
    render(<DownloadCard kind="xlsx" name="x.xlsx" desc="" href="/x" disabled />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByRole("button", { name: /Phase/ })).toBeDisabled();
  });
});
