import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Icon, BrandLogo } from "./Icon";

describe("Icon set", () => {
  it.each([
    "Search",
    "Filter",
    "Calendar",
    "Download",
    "Plus",
    "Receipt",
    "Close",
    "Chevron",
    "Check",
    "Sparkle",
    "Upload",
  ] as const)("%s 아이콘이 SVG 로 렌더된다", (name) => {
    const { container } = render(<Icon name={name} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("alias 가 있으면 role=img + aria-label 부여", () => {
    const { container } = render(<Icon name="Search" alias="검색" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("role", "img");
    expect(svg).toHaveAttribute("aria-label", "검색");
  });
});

describe("BrandLogo", () => {
  it("CX 그라데이션 스퀘어를 렌더한다", () => {
    const { getByText } = render(<BrandLogo />);
    expect(getByText("CX")).toBeInTheDocument();
  });
});
