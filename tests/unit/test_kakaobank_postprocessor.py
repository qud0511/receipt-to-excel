"""Phase 4.5 — Kakaobank OCR postprocessor 4 케이스.

카카오뱅크는 JPG 만 발급 → RuleBased 불가.
OCR Hybrid 의 LLM 응답을 정규식 후처리로 보강 + confidence high 승격.
"""

from __future__ import annotations

from datetime import date, time

from app.services.parsers.ocr_hybrid.postprocessors.kakaobank import (
    extract_kakaobank_fields,
    is_kakaobank_text,
)


# ── 1) 승인번호 — "국내매입"/"해외매입" prefix 제거 후 8자리만 ──────────────────
def test_승인번호_strips_국내매입_prefix() -> None:
    ocr_text = "국내매입 12345678\n다른 텍스트"
    result = extract_kakaobank_fields(ocr_text)
    assert result.get("승인번호") == "12345678"

    # 해외매입도 동일하게 처리.
    ocr2 = "해외매입 87654321"
    result2 = extract_kakaobank_fields(ocr2)
    assert result2.get("승인번호") == "87654321"

    # prefix 없어도 정상 추출.
    ocr3 = "승인번호 11223344"
    result3 = extract_kakaobank_fields(ocr3)
    assert result3.get("승인번호") == "11223344"


# ── 2) 카드번호 — 유효기간 suffix 제거 (정규식이 정확한 형식만 매치) ──────────
def test_카드번호_strips_유효기간_suffix() -> None:
    # 카드번호 뒤에 유효기간 "12/26" 가 붙어 있음. 정규식이 카드번호 부분만 추출.
    ocr_text = "카드 1234-56**-****-7890 12/26\n승인 12345678"
    result = extract_kakaobank_fields(ocr_text)
    assert result.get("카드번호_마스킹") == "1234-****-****-7890"


# ── 3) 거래일 — YYYY.MM.DD HH:MM:SS 점(.) 구분자 ─────────────────────────────
def test_거래일_parses_dot_separated_format() -> None:
    ocr_text = "거래일시: 2026.05.10 14:23:11"
    result = extract_kakaobank_fields(ocr_text)
    assert result.get("거래일") == date(2026, 5, 10)
    assert result.get("거래시각") == time(14, 23, 11)


# ── 4) 업종 추출 + is_kakaobank_text 감지 ───────────────────────────────────
def test_업종_extracted_when_present() -> None:
    ocr_text = "kakaobank 카드매출 온라인전표\n업종: 일반음식점\n가맹점: 갈비집"
    # 후처리기 적용 여부 판단 — kakaobank 시그니처 감지.
    assert is_kakaobank_text(ocr_text) is True

    result = extract_kakaobank_fields(ocr_text)
    assert result.get("업종") == "일반음식점"

    # 시그니처 부재 케이스 — 후처리기 미적용 분기.
    assert is_kakaobank_text("samsung 매출전표") is False
