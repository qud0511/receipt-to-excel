/** 도메인 상수 단일 정의. UI 표시용 — 백엔드 schemas 와 정합 필요. */

export const PURPOSES = ["중식", "석식", "회의", "택시", "간식", "출장"] as const;
export type Purpose = (typeof PURPOSES)[number];

export const PURPOSE_ICONS: Record<Purpose, string> = {
  중식: "🍚",
  석식: "🍱",
  회의: "☕",
  택시: "🚖",
  간식: "🍪",
  출장: "✈️",
};

/** Session.status 4 enum — 백엔드 Session 모델과 정합 (한↔영 mapper 는 StatusPill 에). */
export const SESSION_STATUSES = ["parsing", "awaiting_user", "generated", "submitted", "failed"] as const;
export type SessionStatusKey = (typeof SESSION_STATUSES)[number];

/** Verify 필터 chip 4종 */
export const VERIFY_FILTERS = ["all", "missing", "review", "complete"] as const;
export type VerifyFilter = (typeof VERIFY_FILTERS)[number];

export const VERIFY_FILTER_LABEL: Record<VerifyFilter, string> = {
  all: "전체",
  missing: "필수 누락",
  review: "재확인 필요",
  complete: "완료",
};
