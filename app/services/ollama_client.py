import httpx

from app.schemas.receipt import ReceiptData
from app.services.preprocessor import ProcessedInput


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    async def extract_receipt(
        self,
        input: ProcessedInput,
        system_prompt: str,
    ) -> ReceiptData:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": input.docling_text,  # Docling이 이미 파싱 완료 — 항상 텍스트 모드
            "stream": False,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return ReceiptData.model_validate_json(resp.json()["response"])

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
