/** 한국어 표시 포매터 — 도메인 정합 (ADR-010 §"표기"). */

export function formatKRW(n: number): string {
  return `${n.toLocaleString("ko-KR")}원`;
}

export function formatKRWshort(n: number): string {
  return n.toLocaleString("ko-KR");
}

export function formatPercent(p: number): string {
  return `${p.toFixed(1)}%`;
}

export function formatDeltaPct(p: number): string {
  if (p > 0) return `▲ ${p.toFixed(1)}%`;
  if (p < 0) return `▼ ${(-p).toFixed(1)}%`;
  return "0.0%";
}

export function formatYearMonth(ym: string): string {
  // "2026-05" → "26.05"
  const [y, m] = ym.split("-");
  if (!y || !m) return ym;
  return `${y.slice(2)}.${m}`;
}

export function formatDateDot(iso: string): string {
  // ISO datetime 또는 date → "YYYY.MM.DD"
  const datePart = iso.split("T")[0] ?? iso;
  const [y, m, d] = datePart.split("-");
  if (!y || !m || !d) return iso;
  return `${y}.${m}.${d}`;
}
