import json
import pytest
import respx
import httpx
from app.services.ollama_client import ExtractError, OllamaClient, validate_and_fix
from app.services.preprocessor import ProcessedInput


MOCK_BASE = "http://localhost:11434"

VALID_RECEIPT_JSON = json.dumps({
    "날짜": "2024-01-15",
    "가맹점명": "스타벅스",
    "프로젝트명": None,
    "금액": 5500,
    "부가세": 500,
    "카테고리": "기타비용",
    "결제수단": "카드",
})


@pytest.fixture
def client():
    return OllamaClient(base_url=MOCK_BASE, model="gemma4")


@pytest.fixture
def text_input():
    return ProcessedInput(
        source_name="receipt.jpg",
        source_page=0,
        docling_text="업체명: 스타벅스\n금액: 5500\n결제수단: 카드",
        pil_image=None,
    )


# ── OllamaClient.extract_receipt ─────────────────────────────────────────────

@respx.mock
async def test_extract_receipt_sends_docling_text(client, text_input):
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.가맹점명 == "스타벅스"
    assert receipt.금액 == 5500
    sent = json.loads(route.calls[0].request.content)
    # prompt는 hybrid 형태 — raw docling_text가 OCR 힌트로 포함됨
    assert text_input.docling_text in sent["prompt"]
    assert "images" not in sent  # text_input은 pil_image=None


@respx.mock
async def test_extract_receipt_returns_receipt_data(client, text_input):
    respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.결제수단 == "카드"


@respx.mock
async def test_health_check_ok(client):
    respx.get(f"{MOCK_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert await client.health_check() is True


@respx.mock
async def test_health_check_fail(client):
    respx.get(f"{MOCK_BASE}/api/tags").mock(side_effect=httpx.ConnectError("refused"))
    assert await client.health_check() is False


# ── validate_and_fix ─────────────────────────────────────────────────────────

def test_validate_and_fix_valid():
    raw = {"날짜": "2024-01-15", "가맹점명": "스타벅스", "금액": 5500, "카테고리": "식대", "결제수단": "카드"}
    receipt = validate_and_fix(raw)
    assert receipt.가맹점명 == "스타벅스"
    assert receipt.날짜 == "2024.01.15"
    assert receipt.금액 == 5500


def test_validate_and_fix_invalid_date_raises():
    raw = {"날짜": "invalid", "가맹점명": "업체", "금액": 1000}
    with pytest.raises(ExtractError) as exc_info:
        validate_and_fix(raw)
    assert exc_info.value.field == "날짜"


def test_validate_and_fix_zero_amount_raises():
    raw = {"날짜": "2024-01-15", "가맹점명": "업체", "금액": 0}
    with pytest.raises(ExtractError) as exc_info:
        validate_and_fix(raw)
    assert exc_info.value.field == "금액"


def test_validate_and_fix_negative_amount_raises():
    raw = {"날짜": "2024-01-15", "가맹점명": "업체", "금액": -100}
    with pytest.raises(ExtractError) as exc_info:
        validate_and_fix(raw)
    assert exc_info.value.field == "금액"


def test_validate_and_fix_invalid_category_defaults_to_기타():
    raw = {"날짜": "2024-01-15", "가맹점명": "업체", "금액": 1000, "카테고리": "불명확비용"}
    receipt = validate_and_fix(raw)
    assert receipt.카테고리 == "기타비용"


def test_validate_and_fix_missing_merchant_fallback():
    raw = {"날짜": "2024-01-15", "금액": 1000, "업체명": "구버전업체"}
    receipt = validate_and_fix(raw)
    assert receipt.가맹점명 == "구버전업체"  # 구 스키마 업체명 → 가맹점명


def test_validate_and_fix_empty_merchant_uses_unknown():
    raw = {"날짜": "2024-01-15", "금액": 1000, "가맹점명": ""}
    receipt = validate_and_fix(raw)
    assert receipt.가맹점명 == "알 수 없음"


def test_extract_error_str():
    err = ExtractError("금액", "유효하지 않은 금액: 0")
    assert "금액" in str(err)
    assert err.field == "금액"


# ── Vision payload ────────────────────────────────────────────────────────────

import base64
from PIL import Image as PilImage


@respx.mock
async def test_extract_receipt_sends_images_when_pil_given(client):
    """pil_image가 있으면 payload에 images 필드가 포함된다."""
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    img = PilImage.new("RGB", (100, 80), color="white")
    inp = ProcessedInput(
        source_name="receipt.jpg", source_page=0,
        docling_text="스타벅스 5500", pil_image=img,
    )
    await client.extract_receipt(inp)
    sent = json.loads(route.calls[0].request.content)
    assert "images" in sent
    assert len(sent["images"]) == 1
    base64.b64decode(sent["images"][0])  # 유효한 base64인지 확인


@respx.mock
async def test_extract_receipt_no_images_when_pil_none(client, text_input):
    """pil_image=None이면 images 필드가 없다."""
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    await client.extract_receipt(text_input)
    sent = json.loads(route.calls[0].request.content)
    assert "images" not in sent


@respx.mock
async def test_extract_receipt_temperature_zero(client, text_input):
    """options.temperature=0.0으로 전송된다."""
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    await client.extract_receipt(text_input)
    sent = json.loads(route.calls[0].request.content)
    assert sent.get("options", {}).get("temperature") == 0.0


@respx.mock
async def test_extract_receipt_hybrid_prompt_contains_ocr_hint(client):
    """docling_text가 있으면 prompt에 OCR 힌트가 포함된다."""
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    inp = ProcessedInput(
        source_name="receipt.jpg", source_page=0,
        docling_text="스타벅스 5500원", pil_image=None,
    )
    await client.extract_receipt(inp)
    sent = json.loads(route.calls[0].request.content)
    assert "스타벅스 5500원" in sent["prompt"]
    assert "OCR" in sent["prompt"]


def test_encode_image_returns_valid_base64():
    from app.services.ollama_client import _encode_image
    img = PilImage.new("RGB", (50, 40), color="red")
    encoded = _encode_image(img)
    decoded = base64.b64decode(encoded)
    assert decoded[:3] == b"\xff\xd8\xff"  # JPEG 매직 바이트
