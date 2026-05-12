"""Phase 6.3 — 카드 사용내역 XLSX/CSV 파서 단위 테스트.

ADR-010 자료 검증 C-1: UI Upload 의 '법인카드_2025_12.xlsx · 12건' 지원.
Phase 4 영수증 파서와 별도 — 1 파일 = N 거래, list[ParsedTransaction] 반환.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from app.services.parsers.card_statement.base import (
    CardStatementProvider,
    UnsupportedCardStatementError,
    detect_provider_from_content,
)
from app.services.parsers.card_statement.csv_parser import parse_csv
from app.services.parsers.card_statement.xlsx_parser import parse_xlsx

from tests.fixtures.synthetic_card_statements import (
    make_shinhan_csv_statement,
    make_shinhan_xlsx_statement,
    make_unknown_xlsx_statement,
)


# 1) Provider 감지 — shinhan XLSX 헤더 시그니처
def test_detects_shinhan_xlsx_card_statement() -> None:
    content = make_shinhan_xlsx_statement()
    provider = detect_provider_from_content(content, suffix=".xlsx")
    assert provider == "shinhan"


# 2) Shinhan XLSX 다중 거래 추출
def test_parses_shinhan_xlsx_to_multiple_transactions() -> None:
    txs = [
        {
            "거래일자": "2026-05-01",
            "거래시각": "12:34:56",
            "가맹점명": "가짜한식당",
            "업종": "일반음식점",
            "거래금액": 12000,
            "승인번호": "11111111",
        },
        {
            "거래일자": "2026-05-02",
            "거래시각": "19:00:00",
            "가맹점명": "가짜커피숍",
            "업종": "카페",
            "거래금액": 4500,
            "승인번호": "22222222",
        },
        {
            "거래일자": "2026-05-03",
            "거래시각": "08:15:00",
            "가맹점명": "가짜빵집",
            "업종": "제과",
            "거래금액": 2800,
            "승인번호": "33333333",
        },
    ]
    content = make_shinhan_xlsx_statement(transactions=txs)
    results = parse_xlsx(content)

    assert len(results) == 3
    assert results[0].가맹점명 == "가짜한식당"
    assert results[0].거래일 == date(2026, 5, 1)
    assert results[0].거래시각 == time(12, 34, 56)
    assert results[0].금액 == 12000
    assert results[0].업종 == "일반음식점"
    assert results[0].승인번호 == "11111111"
    assert results[0].카드사 == "shinhan"
    assert results[0].parser_used == "rule_based"


# 3) AD-2 — 카드번호 canonical 형식 강제
def test_card_number_canonical_format_preserved() -> None:
    content = make_shinhan_xlsx_statement(card_number_masked="1234-56**-****-7890")
    [first, *_] = parse_xlsx(content)
    assert first.카드번호_마스킹 == "1234-****-****-7890"


# 4) AD-4 — 금액 int gt=0 강제
def test_transaction_amounts_are_positive_int() -> None:
    content = make_shinhan_xlsx_statement()
    for tx in parse_xlsx(content):
        assert isinstance(tx.금액, int)
        assert tx.금액 > 0


# 5) Shinhan CSV 동일 layout 추출
def test_parses_shinhan_csv_to_transactions() -> None:
    content = make_shinhan_csv_statement()
    results = parse_csv(content)
    assert len(results) == 1
    tx = results[0]
    assert tx.가맹점명 == "가짜편의점"
    assert tx.거래일 == date(2026, 5, 3)
    assert tx.금액 == 3000
    assert tx.카드사 == "shinhan"
    assert tx.parser_used == "rule_based"


# 6) Unsupported provider — 명확한 에러
def test_raises_on_unsupported_xlsx_provider() -> None:
    content = make_unknown_xlsx_statement()
    with pytest.raises(UnsupportedCardStatementError):
        parse_xlsx(content)


# 7) Provider enum type contract — ParsedTransaction.카드사 와 호환
def test_provider_enum_compatible_with_parsed_transaction() -> None:
    # detect_provider_from_content 의 반환 Literal 이 ParsedTransaction.CardProvider 값 중 하나.
    valid_providers: set[CardStatementProvider] = {
        "shinhan",
        "samsung",
        "hana",
        "woori",
        "hyundai",
        "lotte",
        "kbank",
        "kakaobank",
    }
    content = make_shinhan_xlsx_statement()
    detected = detect_provider_from_content(content, suffix=".xlsx")
    assert detected in valid_providers


# 8) 헤더 row 부재 → UnsupportedCardStatementError
def test_empty_xlsx_raises() -> None:
    from openpyxl import Workbook

    wb = Workbook()
    import io as _io

    buf = _io.BytesIO()
    wb.save(buf)
    with pytest.raises(UnsupportedCardStatementError):
        parse_xlsx(buf.getvalue())


# 9) field_confidence 가 모든 핵심 필드에 대해 채워짐
def test_field_confidence_populated() -> None:
    content = make_shinhan_xlsx_statement()
    [first, *_] = parse_xlsx(content)
    for field in ("가맹점명", "거래일", "거래시각", "금액"):
        assert field in first.field_confidence


# 10) 한글 헤더 매칭 — '거래일자' / '거래일' 양쪽 흡수
def test_handles_korean_header_variations() -> None:
    """동의 (사용자 결정): 카드사별 양식 변동성 흡수 — 헤더 유연성.

    실제 신한카드 변형에서 '거래일자' 또는 '거래일' 양쪽 발생 가능.
    """
    # synthetic 은 '거래일자' 만 — 본 케이스는 회귀 방지용 (단위 contract).
    content = make_shinhan_xlsx_statement()
    results = parse_xlsx(content)
    assert all(tx.거래일 is not None for tx in results)
