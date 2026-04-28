from typing import Literal
from pydantic import BaseModel


class ReceiptData(BaseModel):
    날짜: str
    업체명: str
    품목: str
    금액: int
    부가세: int
    결제수단: Literal["카드", "현금", "계좌이체", "기타"]
    비고: str | None = None
