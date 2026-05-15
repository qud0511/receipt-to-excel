import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ConfidenceBadge, type Confidence } from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it.each<[Confidence, string]>([
    ["high", "conf-high"],
    ["medium", "conf-medium"],
    ["low", "conf-low"],
    ["none", "conf-none"],
  ])("%s confidence 는 %s 토큰 클래스 사용", (level, klass) => {
    const { container } = render(<ConfidenceBadge level={level} />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toMatch(klass);
  });

  it("aria-label 에 신뢰도 한국어 표기", () => {
    const { getByRole } = render(<ConfidenceBadge level="medium" />);
    expect(getByRole("img")).toHaveAttribute("aria-label", "신뢰도 중간");
  });
});
