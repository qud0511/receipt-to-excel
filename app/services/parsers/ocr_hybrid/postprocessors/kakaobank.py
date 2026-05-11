"""카카오뱅크 OCR 후처리 — JPG-only 카드사 영수증의 LLM 응답 보강.

사양 (synthesis/05 §Phase 4):
- 카드사 = "kakaobank"
- 라우팅 트리거: OCR 텍스트에 ``"kakaobank"`` 또는 ``"카드매출 온라인전표"``
- 후처리 결과는 LLM 응답을 **덮어쓰지 않고 보강** — 정규식이 잡은 필드만
  ``confidence="high"`` 로 승격 (CLAUDE.md §"특이사항": Hallucination 방어 3단).
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import TypedDict

# 카드번호 뒤 유효기간 (예: "12/26") suffix 는 정규식 자체가 정확한 형식만 잡아 자동 분리.
_CARD = re.compile(r"(\d{4})-\d{2}\*\*-\*\*\*\*-(\d{4})")
# 사양: YYYY.MM.DD HH:MM:SS — 점(.) 구분자. 신한/삼성/케이뱅크와 다름.
_DATE_TIME = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")
# 승인번호 앞에 "국내매입"/"해외매입" prefix 가 있을 수 있음 — non-capturing 으로 제거.
_APPROVAL = re.compile(r"(?:국내매입|해외매입|승인번호)?\s*(\d{8})")
_CATEGORY = re.compile(r"업종[:\s]*(.+?)\s*$", re.MULTILINE)


class KakaobankExtracted(TypedDict, total=False):
    카드번호_마스킹: str
    거래일: date
    거래시각: time
    승인번호: str
    업종: str


def is_kakaobank_text(ocr_text: str) -> bool:
    """카카오뱅크 시그니처 감지 — 라우팅 분기 진입점."""
    return "kakaobank" in ocr_text.lower() or "카드매출 온라인전표" in ocr_text


def extract_kakaobank_fields(ocr_text: str) -> KakaobankExtracted:
    """OCR 텍스트에서 정규식으로 필드 추출.

    매치되는 필드만 dict 로 반환. 호출자가 LLM 응답에 merge.
    매치 안 된 키는 dict 에 부재 — `result.get(key)` 패턴으로 안전 접근.
    """
    result: KakaobankExtracted = {}

    card_match = _CARD.search(ocr_text)
    if card_match:
        first4, last4 = card_match.groups()
        # AD-2 canonical 변환.
        result["카드번호_마스킹"] = f"{first4}-****-****-{last4}"

    dt_match = _DATE_TIME.search(ocr_text)
    if dt_match:
        y, mo, d, hh, mm, ss = (int(g) for g in dt_match.groups())
        result["거래일"] = date(y, mo, d)
        result["거래시각"] = time(hh, mm, ss)

    approval_match = _APPROVAL.search(ocr_text)
    if approval_match:
        result["승인번호"] = approval_match.group(1)

    cat_match = _CATEGORY.search(ocr_text)
    if cat_match:
        result["업종"] = cat_match.group(1)

    return result
