---
id: ADR-003
title: 실 자료 fixture 파일명 정규화 (한글 PII → ASCII-safe 영문)
date: 2026-05-12
status: accepted
refs:
  - CLAUDE.md §"한국어 환경" / §"fixture 분리"
  - tests/smoke/results/20260512.md
---

# 결정

`tests/smoke/real_pdfs/`, `tests/smoke/real_templates/` 의 모든 실 자료는
ASCII-safe 영문 파일명으로 보관한다. 원본 한글 파일명(거래자명·계정주·날짜 등 PII 포함)
은 저장소 내부에 두지 않는다.

# 이유

1. **PII 누출 차단** — Smoke 결과 보고서(`tests/smoke/results/YYYYMMDD.md`)와
   `pytest --collect-only` 출력에 파라미터 ID 로 파일명이 노출된다. 원본 한글명에는
   "지출결의서_{성명}" 형태로 자연인 이름이 포함되어 있어 보고서에 PII 가 유출된다.
2. **인코딩 안정성** — 한자/한글 파일명은 git/CI/Docker 레이어에서
   normalization 차이(NFC vs NFD) 로 silent skew 가 발생한 적이 있다 (v1 사고).
   ASCII 만 사용하면 동일 위험 제거.
3. **CLAUDE.md §한국어 환경** "디스크는 ASCII-safe, 한글 원본은 메타 컬럼" 규칙의
   fixture 영역 적용. 운영 코드와 fixture 가 같은 규칙을 따라야 일관성 유지.

# 적용 — 매핑 정책

## PDF (`tests/smoke/real_pdfs/`)

| 영문명                    | 출처 카드사 | 비고                                                |
| ------------------------- | ----------- | --------------------------------------------------- |
| `woori_nup_01.pdf`        | 우리카드    | 1 페이지 N-up 배치 (4 거래)                         |
| `woori_nup_02.pdf`        | 우리카드    | 2 페이지 N-up 배치 (5 거래)                         |
| `hyundai_01.pdf`          | 현대카드    | 이미지 PDF (OCR Hybrid 경로 대상)                   |
| `woori_legacy_01.jpg`     | 우리카드    | 기존 woori_01.jpg rename — N-up PDF 와 충돌 회피    |
| `woori_legacy_02.jpg`     | 우리카드    | 기존 woori_02.jpg rename — 동일                     |

woori_legacy 확인 근거: 영수증 헤더 "우리카드", 카드번호 prefix `9102-34**-****-NNNN`
모두 우리카드 BIN 형식. ImageRead 시각 확인 완료 (2026-05-12).

## XLSX 지출결의서 (`tests/smoke/real_templates/`)

| 영문명                         | 연/월     | 사용자 (익명)        |
| ------------------------------ | --------- | -------------------- |
| `expense_2025_12_a.xlsx`       | 2025-12   | user-α               |
| `expense_2026_03_a.xlsx`       | 2026-03   | user-β               |
| `expense_2026_03_b.xlsx`       | 2026-03   | user-γ               |

> 익명 식별자(user-α/β/γ)는 본 ADR 외부의 사용자 사적 보관 매핑에서만 실명과 연결.
> 본 ADR · 본 저장소 어디에도 실명을 기재하지 않는다.

# 운영 규칙

- `tests/smoke/real_pdfs/`, `tests/smoke/real_templates/` 는 `.gitignore` 에 등록 (PII 보호).
- 신규 실 자료 투입 시: ① 외부 한글 원본은 사용자 개인 영역에 보존 → ② 영문명으로 복사 →
  ③ 본 매핑표에 한 줄 추가.
- 매핑표에 등재된 파일만 Smoke Gate 통과 후보로 인정. 한글명 파일은 즉시 제거.

# 영향

- `tests/smoke/test_real_pdfs.py` 의 fixture id 가 한글 → 영문화. 보고서 가독성·재현성 향상.
- 신규 카드사 추가 시 `{provider}_NN.{ext}` 또는 `{provider}_{variant}_NN.{ext}` 명명 강제.
- 기존 `woori_NN.jpg` 참조 코드/문서(phase-4-done.md, smoke README, smoke 결과 20260512.md)는
  `woori_legacy_NN.jpg` 로 일괄 정정 필요 (Task 6 에서 처리).

# 대안 폐기

1. **한글명 유지 + 보고서 마스킹**: 보고서 마스킹은 누락 시 silent PII 누출. 디스크-원본 단계에서 차단하는 편이 안전.
2. **UUID 명명**: provider 식별성 손실. 디버깅 시 grep 가독성·smoke 보고서 가독성 모두 저하.
