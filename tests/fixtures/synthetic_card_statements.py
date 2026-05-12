"""합성 카드 사용내역 — XLSX/CSV. 카드사별 가상 layout 으로 parser 단위 검증.

CLAUDE.md TDD: 합성 fixture 만 — 실 카드사 다운로드 자료는 smoke real_pdfs/ 분리.
형식 가짜 — 가맹점명 "가짜한식당" / 카드번호 마스킹 9999-99**-****-9999 패턴.
"""

from __future__ import annotations

import csv
import io

from openpyxl import Workbook


def make_shinhan_xlsx_statement(
    *,
    card_number_masked: str = "9999-99**-****-9999",
    transactions: list[dict[str, object]] | None = None,
) -> bytes:
    """신한카드 다운로드 양식 합성 — header row 1 + 거래 row 2~.

    Columns (신한카드 v3 다운로드 양식 가정):
        A=거래일자 B=거래시각 C=가맹점명 D=업종 E=거래금액 F=승인번호 G=카드번호
    """
    if transactions is None:
        transactions = [
            {
                "거래일자": "2026-05-01",
                "거래시각": "12:34:56",
                "가맹점명": "가짜한식당",
                "업종": "일반음식점",
                "거래금액": 12000,
                "승인번호": "12345678",
            },
            {
                "거래일자": "2026-05-02",
                "거래시각": "19:00:00",
                "가맹점명": "가짜커피숍",
                "업종": "카페",
                "거래금액": 4500,
                "승인번호": "12345679",
            },
        ]
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("openpyxl active sheet missing")
    ws.title = "신한카드 거래내역"
    # 신한 헤더 시그니처 — provider 감지용.
    headers = ["거래일자", "거래시각", "가맹점명", "업종", "거래금액", "승인번호", "카드번호"]
    ws.append(headers)
    for tx in transactions:
        ws.append(
            [
                tx["거래일자"],
                tx["거래시각"],
                tx["가맹점명"],
                tx["업종"],
                tx["거래금액"],
                tx["승인번호"],
                card_number_masked,
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_shinhan_csv_statement(
    *,
    card_number_masked: str = "9999-99**-****-9999",
    transactions: list[dict[str, object]] | None = None,
) -> bytes:
    """신한카드 CSV 변형 — XLSX 와 동일 컬럼.

    한국 카드사 CSV 는 UTF-8 BOM + cp949 양쪽 — Phase 6 은 UTF-8 only 가정
    (encoding 자동 감지는 후속).
    """
    if transactions is None:
        transactions = [
            {
                "거래일자": "2026-05-03",
                "거래시각": "10:00:00",
                "가맹점명": "가짜편의점",
                "업종": "편의점",
                "거래금액": 3000,
                "승인번호": "99999999",
            }
        ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["거래일자", "거래시각", "가맹점명", "업종", "거래금액", "승인번호", "카드번호"]
    )
    for tx in transactions:
        writer.writerow(
            [
                tx["거래일자"],
                tx["거래시각"],
                tx["가맹점명"],
                tx["업종"],
                tx["거래금액"],
                tx["승인번호"],
                card_number_masked,
            ]
        )
    return buf.getvalue().encode("utf-8")


def make_unknown_xlsx_statement() -> bytes:
    """provider 감지 실패 케이스 — 알 수 없는 헤더."""
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("openpyxl active sheet missing")
    ws.title = "Unknown"
    ws.append(["foo", "bar", "baz"])
    ws.append([1, 2, 3])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
