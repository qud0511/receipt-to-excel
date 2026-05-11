"""Ollama Vision API 클라이언트 — temperature=0.0 + format=json 강제.

CLAUDE.md §"특이사항: LLM 파라미터 고정":
- ``temperature=0.0`` (변경 시 ADR)
- ``format="json"`` (Pydantic strict 검증과 함께 hallucination 방어 4단의 1단)
- 타임아웃 180s.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import TypedDict

import httpx
from PIL.Image import Image as PILImage


class _PayloadOptions(TypedDict):
    temperature: float


class OllamaPayload(TypedDict):
    model: str
    prompt: str
    system: str
    images: list[str]
    format: str
    options: _PayloadOptions
    stream: bool


def build_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    image: PILImage | None = None,
) -> OllamaPayload:
    """Ollama ``/api/generate`` 페이로드 생성. PIL Image → PNG base64."""
    images: list[str] = []
    if image is not None:
        buf = BytesIO()
        image.save(buf, format="PNG")
        images.append(base64.b64encode(buf.getvalue()).decode("ascii"))

    return {
        "model": model,
        "prompt": user_prompt,
        "system": system_prompt,
        "images": images,
        "format": "json",  # CLAUDE.md §"특이사항: format='json' 고정"
        "options": {"temperature": 0.0},  # CLAUDE.md §"특이사항: temperature=0.0 고정"
        "stream": False,
    }


class OllamaVisionClient:
    """Ollama HTTP wrapper. 외부 HTTP 는 CLAUDE.md §"보안" 화이트리스트 (Ollama+JWKS 만)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=180.0)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image: PILImage | None = None,
    ) -> dict[str, object]:
        payload = build_payload(
            model=self._model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image=image,
        )
        r = await self._http.post(f"{self._base_url}/api/generate", json=payload)
        r.raise_for_status()
        body = r.json()
        # 호출자가 isinstance(body, dict) 가정 가능하도록 dict 보장 (str/list 응답은 비정상).
        if not isinstance(body, dict):
            raise TypeError(f"Ollama response is not a dict: {type(body).__name__}")
        return body

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
