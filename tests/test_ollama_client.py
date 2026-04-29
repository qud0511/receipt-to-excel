import json
import pytest
import respx
import httpx
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput


MOCK_BASE = "http://localhost:11434"

VALID_RECEIPT_JSON = json.dumps({
    "날짜": "2024-01-15",
    "업체명": "스타벅스",
    "품목": "아메리카노",
    "금액": 5500,
    "부가세": 500,
    "결제수단": "카드",
    "비고": None,
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


@respx.mock
async def test_extract_receipt_sends_docling_text(client, text_input):
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.업체명 == "스타벅스"
    assert receipt.금액 == 5500
    sent = json.loads(route.calls[0].request.content)
    assert sent["prompt"] == text_input.docling_text
    assert "images" not in sent


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
