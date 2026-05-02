from __future__ import annotations

import base64
import io
import json
import re

import httpx

from app.schemas.receipt import ReceiptData
from app.services.preprocessor import ProcessedInput

_SYSTEM_PROMPT = """당신은 한국 영수증 정보 추출 전문가입니다.
첨부된 이미지가 가장 정확한 원본 데이터이니 이를 최우선 판단 기준으로 삼으세요.
함께 제공된 [OCR 텍스트]는 참고용 힌트일 뿐이며, 오타나 오인식이 있을 수 있습니다.

반드시 아래 JSON 스키마를 엄격하게 따라 결과를 출력하세요:

{
  "날짜": "YYYY.MM.DD 형식 (예: 2025.12.05)",
  "가맹점명": "영수증에 표시된 상호명 그대로",
  "금액": 정수 (쉼표·기호 없이, 예: 5500),
  "부가세": 정수 또는 0 (없으면 0),
  "카테고리": "아래 목록에서 반드시 하나 선택",
  "결제수단": "아래 목록에서 반드시 하나 선택",
  "프로젝트명": null 또는 영수증에 언급된 프로젝트명
}

카테고리 선택 기준:
  음식점/카페/편의점 식품 → "식대"
  접대·거래처 식사 → "접대비"
  택시/버스/지하철/기차 → "여비교통비"
  항공 → "항공료"
  호텔/숙박 → "숙박비"
  주유소/충전소 → "유류대"
  주차 → "주차통행료"
  그 외 모든 경우 → "기타비용"

결제수단 선택 기준:
  신용카드/체크카드 → "카드"
  현금 → "현금"
  계좌이체/간편결제(카카오페이·토스 등) → "계좌이체"
  그 외 → "기타"

JSON만 출력하세요. 마크다운 블록·설명·부연 설명 절대 없음.
예시: {"날짜":"2025.12.05","가맹점명":"스타벅스","금액":5500,"부가세":500,"카테고리":"식대","결제수단":"카드","프로젝트명":null}
"""

_VALID_CATEGORIES = frozenset({
    "식대", "접대비", "여비교통비", "항공료",
    "숙박비", "유류대", "주차통행료", "기타비용",
})


class ExtractError(Exception):
    """LLM 추출 결과가 유효하지 않아 ReceiptData로 변환할 수 없을 때 발생."""
    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    async def extract_receipt(
        self,
        inp: ProcessedInput,
        system_prompt: str | None = None,
    ) -> ReceiptData:
        prompt = system_prompt or _SYSTEM_PROMPT
        payload: dict = {
            "model": self.model,
            "system": prompt,
            "prompt": _build_user_prompt(inp),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        if inp.pil_image is not None:
            payload["images"] = [_encode_image(inp.pil_image)]

        async with httpx.AsyncClient(timeout=180.0) as http:
            resp = await http.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json()["response"]
            data = _parse_json(raw)
            return validate_and_fix(data)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                r = await http.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False


def validate_and_fix(raw: dict) -> ReceiptData:
    """LLM 응답 dict를 검증·보정하고 ReceiptData로 변환.

    필수 필드(날짜·금액)가 유효하지 않으면 ExtractError 발생.
    선택 필드는 가능하면 fallback 값으로 대체한다.
    """
    raw["날짜"] = _normalize_date(raw.get("날짜", ""))
    if not raw["날짜"]:
        raise ExtractError("날짜", "날짜를 인식할 수 없습니다")

    amount = raw.get("금액", 0)
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        raise ExtractError("금액", f"유효하지 않은 금액: {raw.get('금액')!r}")
    raw["금액"] = amount

    if raw.get("카테고리") not in _VALID_CATEGORIES:
        raw["카테고리"] = "기타비용"

    if raw.get("결제수단") not in ("카드", "현금", "계좌이체", "기타"):
        raw["결제수단"] = "기타"

    if not raw.get("가맹점명"):
        raw["가맹점명"] = (
            raw.get("merchant_name")
            or raw.get("업체명")
            or "알 수 없음"
        )

    raw.pop("업체명", None)
    raw.pop("품목", None)

    return ReceiptData.model_validate(raw)


def _encode_image(img: "PilImage.Image") -> str:  # type: ignore[name-defined]
    """PIL Image → base64 JPEG 문자열."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def _build_user_prompt(inp: ProcessedInput) -> str:
    """OCR 텍스트가 있으면 힌트로 포함한 hybrid 프롬프트를 구성한다."""
    text = (inp.docling_text or "").strip()
    if text:
        return (
            "[OCR 텍스트 힌트 — 오타·오인식이 있을 수 있음]\n"
            f"{text}\n\n"
            "위 OCR 텍스트를 참고하되, 첨부된 이미지를 최우선 판단 기준으로 삼아 영수증 정보를 추출하세요."
        )
    return "첨부된 영수증 이미지에서 정보를 추출하세요."


def _parse_json(raw: str) -> dict:
    """JSON 응답 파싱. 모델이 불필요한 텍스트를 섞어도 추출한다."""
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _normalize_date(date_str: str) -> str:
    """다양한 날짜 포맷 → 'YYYY.MM.DD'. 인식 불가 시 빈 문자열."""
    s = str(date_str or "").strip()
    m = re.match(r"(\d{4})[-./년](\d{1,2})[-./월](\d{1,2})", s)
    if m:
        return f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"
    return ""
