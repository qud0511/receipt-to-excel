import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("default variant 렌더", () => {
    render(<Chip>2026.05</Chip>);
    expect(screen.getByRole("button", { name: "2026.05" })).toBeInTheDocument();
  });

  it("active variant 는 brand 배경", () => {
    render(<Chip active>법인카드</Chip>);
    expect(screen.getByRole("button").className).toMatch(/bg-brand-soft/);
  });

  it("outline variant", () => {
    render(<Chip variant="outline">미입력만</Chip>);
    expect(screen.getByRole("button").className).toMatch(/border/);
  });
});
