"""ParsedTransaction — 파서 출력의 단일 계약. AD-1 immutable / AD-2 canonical."""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.confidence import ConfidenceLabel

CardProvider = Literal[
    "shinhan",
    "hana",
    "samsung",
    "woori",
    "hyundai",
    "lotte",
    "kbank",
    "kakaobank",
    "unknown",
]
ParserUsed = Literal["rule_based", "ocr_hybrid", "llm"]

# AD-2 canonical: NNNN-****-****-NNNN (정확히 19자).
_CARD_MASKED_PATTERN = r"^\d{4}-\*{4}-\*{4}-\d{4}$"


class ParsedTransaction(BaseModel):
    """파서가 PDF/이미지에서 추출한 결과 — AD-4 raw fields only.

    AD-1 (가맹점명 immutable): 파서는 raw 그대로 저장.
    정규화는 표시 레이어/Merchant 레지스트리에서만.
    AD-2 (카드번호 canonical): 모든 파서 출력 시점에 NNNN-****-****-NNNN 형식 강제.
    AD-4 (금액 int gt 0): 원 단위, float 금지.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    # Raw — 파서 출력, 변형 금지.
    가맹점명: str
    거래일: date
    거래시각: time | None = None
    금액: int = Field(gt=0)
    공급가액: int | None = Field(default=None, gt=0)
    부가세: int | None = Field(default=None, ge=0)
    승인번호: str | None = None
    업종: str | None = None
    카드사: CardProvider = "unknown"
    # None 은 파서가 카드번호를 못 찾은 케이스. 값이 있다면 canonical 형식 강제.
    카드번호_마스킹: str | None = Field(default=None, pattern=_CARD_MASKED_PATTERN)

    # Derived — 파서 라우팅 / confidence labeler 결과.
    parser_used: ParserUsed
    # 필드별 4-label — pydantic 이 ConfidenceLabel Literal 로 자동 검증.
    field_confidence: dict[str, ConfidenceLabel]
