import { describe, expect, it } from "vitest";
import { formatKRW, formatKRWshort, formatPercent, formatYearMonth, formatDateDot, formatDeltaPct } from "./format";

describe("format", () => {
  it("formatKRW: 콤마 + '원'", () => {
    expect(formatKRW(1234567)).toBe("1,234,567원");
    expect(formatKRW(0)).toBe("0원");
  });

  it("formatKRWshort: 콤마만", () => {
    expect(formatKRWshort(1234567)).toBe("1,234,567");
  });

  it("formatPercent: 소수 1자리", () => {
    expect(formatPercent(8.523)).toBe("8.5%");
    expect(formatPercent(-12)).toBe("-12.0%");
  });

  it("formatDeltaPct: 양수는 ▲, 음수는 ▼", () => {
    expect(formatDeltaPct(8.5)).toBe("▲ 8.5%");
    expect(formatDeltaPct(-3.2)).toBe("▼ 3.2%");
    expect(formatDeltaPct(0)).toBe("0.0%");
  });

  it("formatYearMonth: '2026-05' → '26.05'", () => {
    expect(formatYearMonth("2026-05")).toBe("26.05");
  });

  it("formatDateDot: ISO → 'YYYY.MM.DD'", () => {
    expect(formatDateDot("2026-05-12T10:30:00")).toBe("2026.05.12");
    expect(formatDateDot("2026-05-12")).toBe("2026.05.12");
  });
});
