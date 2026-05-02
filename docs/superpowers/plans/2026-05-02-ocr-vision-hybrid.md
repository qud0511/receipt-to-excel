# OCR Vision Hybrid 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** gemma4 Vision(이미지 base64) + Docling OCR 텍스트를 동시에 제공하는 하이브리드 컨텍스트 방식으로 영수증 정보 추출 정확도를 극대화한다.

**Architecture:** DoclingService의 OCR 엔진을 한국어 EasyOCR로 교체하고 불필요한 레이아웃 분석 옵션을 비활성화한다. OllamaClient에서 PIL 이미지를 base64 JPEG로 인코딩해 Ollama multimodal API로 전달하면서, Docling이 추출한 텍스트를 프롬프트의 힌트(context)로 함께 제공한다. temperature=0.0으로 구조화 추출을 강화하고 format="json"을 유지한다. pil_image=None인 경우(스프레드시트 등)는 텍스트 전용 모드로 폴백된다.

**Tech Stack:** Docling 2.91.0 (EasyOCR backend, lang=ko+en), Ollama gemma4 (vision + json format), httpx, Pillow (base64 JPEG encoding), respx (테스트 mock)

---

## File Map

| 파일 | 변경 | 책임 |
|------|------|------|
| `app/services/docling_service.py` | Modify | `_make_pipeline_options()` 추출, Korean EasyOCR 설정, 경량 옵션 |
| `app/services/ollama_client.py` | Modify | `_encode_image()`, `_build_user_prompt()`, Vision payload, 새 system prompt, temperature=0.0 |
| `tests/test_docling_service.py` | Create | OCR 옵션 단위 테스트 |
| `tests/test_ollama_client.py` | Modify | 기존 테스트 업데이트 + Vision payload/hybrid prompt 테스트 추가 |

---

### Task 1: DoclingService — Korean EasyOCR + 경량 모드

**Files:**
- Modify: `app/services/docling_service.py`
- Create: `tests/test_docling_service.py`

현재 문제: `DoclingService`가 이미지/PDF에 대해 OCR 언어를 설정하지 않아 Docling 기본 엔진(RapidOCR Chinese)이 동작 → 한국어 영수증이 한자처럼 인식됨.

목표: `_make_pipeline_options()` 헬퍼를 추출해 `EasyOcrOptions(lang=['ko', 'en'], force_full_page_ocr=True)`를 설정하고, 불필요한 테이블/그림 분석을 비활성화한다. PDF와 IMAGE 양쪽에 동일 옵션을 적용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_docling_service.py` 생성:

```python
import pytest
from docling.datamodel.pipeline_options import EasyOcrOptions


def test_make_pipeline_options_uses_korean_easyocr():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert isinstance(opts.ocr_options, EasyOcrOptions)
    assert "ko" in opts.ocr_options.lang
    assert "en" in opts.ocr_options.lang
    assert opts.ocr_options.force_full_page_ocr is True


def test_make_pipeline_options_disables_heavy_analysis():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert opts.do_table_structure is False
    assert opts.do_picture_classification is False
    assert opts.do_picture_description is False


def test_make_pipeline_options_sets_high_scale():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert opts.images_scale >= 2.0
    assert opts.generate_page_images is True
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_docling_service.py -v
```

Expected: `ImportError` 또는 `AttributeError: module has no attribute '_make_pipeline_options'`

- [ ] **Step 3: DoclingService 수정**

`app/services/docling_service.py` 전체 교체:

```python
from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image as PilImage

from app.services.preprocessor import ProcessedInput


def _make_pipeline_options():
    """Korean EasyOCR + 경량 분석 설정 반환. PDF·IMAGE 공통 사용."""
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    return PdfPipelineOptions(
        do_ocr=True,
        ocr_options=EasyOcrOptions(
            lang=["ko", "en"],
            force_full_page_ocr=True,
            confidence_threshold=0.3,
        ),
        do_table_structure=False,
        do_picture_classification=False,
        do_picture_description=False,
        generate_page_images=True,
        images_scale=2.0,
    )


class DoclingService:
    """DocumentConverter 싱글턴 래퍼. 모든 파일 타입을 ProcessedInput 목록으로 변환."""

    def __init__(self) -> None:
        from docling.document_converter import (
            DocumentConverter, PdfFormatOption, ImageFormatOption,
        )
        from docling.datamodel.base_models import InputFormat

        opts = _make_pipeline_options()
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=opts),
            }
        )

    def process(self, file_bytes: bytes, filename: str, source_name: str) -> list[ProcessedInput]:
        suffix = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_bytes)
            tmp_path = Path(f.name)

        try:
            result = self._converter.convert(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

        doc = result.document

        if suffix in (".pdf", ".pptx"):
            return self._split_by_page(doc, source_name)
        else:
            return self._single_page(doc, source_name, suffix, file_bytes)

    def _split_by_page(self, doc, source_name: str) -> list[ProcessedInput]:
        from collections import defaultdict
        page_texts: dict[int, list[str]] = defaultdict(list)
        for item, _level in doc.iterate_items():
            provs = getattr(item, "prov", None) or []
            for prov in provs:
                page_no = getattr(prov, "page_no", None)
                if page_no is None:
                    continue
                text = getattr(item, "text", None)
                if text:
                    page_texts[page_no].append(text)

        if not page_texts:
            full = doc.export_to_markdown()
            return [ProcessedInput(source_name=source_name, source_page=0,
                                   docling_text=full, pil_image=None)]

        results: list[ProcessedInput] = []
        for page_no in sorted(page_texts.keys()):
            text = "\n".join(page_texts[page_no])
            pil_img = self._page_image(doc, page_no)
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=page_no - 1,
                docling_text=text,
                pil_image=pil_img,
            ))
        return results

    def _single_page(
        self, doc, source_name: str, suffix: str, file_bytes: bytes
    ) -> list[ProcessedInput]:
        text = doc.export_to_markdown()
        pil_img: PilImage.Image | None = None
        if suffix in (".jpg", ".jpeg", ".png"):
            import io
            pil_img = PilImage.open(io.BytesIO(file_bytes)).convert("RGB")
        return [ProcessedInput(source_name=source_name, source_page=0,
                               docling_text=text, pil_image=pil_img)]

    @staticmethod
    def _page_image(doc, page_no: int) -> PilImage.Image | None:
        page = (doc.pages or {}).get(page_no)
        if page is None:
            return None
        img_ref = getattr(page, "image", None)
        if img_ref is None:
            return None
        return getattr(img_ref, "pil_image", None)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_docling_service.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: 전체 테스트 suite 확인 (docling_service 관련)**

```bash
.venv/bin/pytest tests/test_preprocessor.py tests/test_docling_service.py -v
```

Expected: PASS (docling 관련 기존 테스트도 유지)

- [ ] **Step 6: 커밋**

```bash
git add app/services/docling_service.py tests/test_docling_service.py
git commit -m "feat: DoclingService — Korean EasyOCR + lightweight pipeline options"
```

---

### Task 2: OllamaClient — Vision payload + hybrid prompt + temperature

**Files:**
- Modify: `app/services/ollama_client.py`
- Modify: `tests/test_ollama_client.py`

목표:
1. `_encode_image(img)` — PIL → base64 JPEG 문자열
2. `_build_user_prompt(inp)` — OCR 텍스트가 있으면 힌트로 포함, 없으면 이미지만 요청
3. `_SYSTEM_PROMPT` — 한국어·이미지 우선·엄격 JSON 스키마 명시
4. `extract_receipt()` — `pil_image`가 있으면 `images` 필드 포함, `options.temperature=0.0` 추가
5. 기존 테스트 `test_extract_receipt_sends_docling_text` 업데이트 (prompt 구조 변경 반영)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_ollama_client.py`에 아래 4개 테스트 추가 (파일 끝에 append):

```python
import base64
from PIL import Image as PilImage


# ── Vision payload ───────────────────────────────────────────────────────────

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
    respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    await client.extract_receipt(text_input)
    sent = json.loads(respx.calls[0].request.content)
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
    assert "OCR" in sent["prompt"]  # 힌트 레이블 확인


def test_encode_image_returns_valid_base64():
    from app.services.ollama_client import _encode_image
    img = PilImage.new("RGB", (50, 40), color="red")
    encoded = _encode_image(img)
    decoded = base64.b64decode(encoded)
    assert decoded[:3] == b"\xff\xd8\xff"  # JPEG 매직 바이트
```

- [ ] **Step 2: 기존 테스트 업데이트**

`tests/test_ollama_client.py`의 `test_extract_receipt_sends_docling_text`를 아래로 교체:

```python
@respx.mock
async def test_extract_receipt_sends_docling_text(client, text_input):
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.가맹점명 == "스타벅스"
    assert receipt.금액 == 5500
    sent = json.loads(route.calls[0].request.content)
    # prompt는 이제 hybrid 형태 (OCR 힌트 포함), raw docling_text와 동일하지 않음
    assert text_input.docling_text in sent["prompt"]
    assert "images" not in sent  # text_input은 pil_image=None
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
.venv/bin/pytest tests/test_ollama_client.py -v
```

Expected: 새 테스트들 FAIL (`_encode_image` 없음, `images` 미포함, temperature 없음 등)

- [ ] **Step 4: OllamaClient 전체 교체**

`app/services/ollama_client.py`:

```python
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
```

- [ ] **Step 5: 모든 ollama 테스트 통과 확인**

```bash
.venv/bin/pytest tests/test_ollama_client.py -v
```

Expected: 모든 테스트 PASS (기존 12개 + 신규 5개 = 17개)

- [ ] **Step 6: 커밋**

```bash
git add app/services/ollama_client.py tests/test_ollama_client.py
git commit -m "feat: OllamaClient — Vision hybrid prompt, temperature=0.0, Korean system prompt"
```

---

### Task 3: 전체 테스트 + 관련 플랜 문서 업데이트

**Files:**
- No code changes
- Update: `docs/superpowers/plans/2026-04-29-master-refactor.md` (OCR 개선 반영)

- [ ] **Step 1: 전체 테스트 suite 실행**

```bash
.venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: 모든 테스트 PASS. 실패 시 Task 1/2로 돌아가 수정.

- [ ] **Step 2: master-refactor 플랜에 완료 메모 추가**

`docs/superpowers/plans/2026-04-29-master-refactor.md` 파일 상단 또는 끝에 아래 섹션 추가:

```markdown
## 추가 개선: OCR Vision Hybrid (2026-05-02)

Phase 3 이후 실제 테스트에서 발견된 문제(Docling RapidOCR Chinese로 인한 한국어 인식 실패)를
해결하기 위해 다음이 추가 구현됨:

- `DoclingService`: EasyOCR(ko+en) + 경량 파이프라인 옵션 (`_make_pipeline_options()`)
- `OllamaClient`: Vision hybrid — 이미지 base64 + OCR 텍스트를 동시에 gemma4에 전달
- `temperature=0.0`, 한국어 강화 system prompt
- 상세 플랜: `docs/superpowers/plans/2026-05-02-ocr-vision-hybrid.md`
```

- [ ] **Step 3: 커밋**

```bash
git add docs/
git commit -m "docs: OCR Vision Hybrid 플랜 및 master-refactor 업데이트 반영"
```

---

## Self-Review

**Spec coverage 체크:**
- [x] Docling EasyOCR(ko+en) 교체 — Task 1
- [x] 불필요한 레이아웃 분석 비활성화 — Task 1 (`do_table_structure=False` 등)
- [x] images_scale=2.0 (고해상도 OCR) — Task 1
- [x] Vision base64 전송 — Task 2 (`_encode_image`, `payload["images"]`)
- [x] OCR 텍스트를 힌트로 병행 제공 — Task 2 (`_build_user_prompt`)
- [x] temperature=0.0 — Task 2 (`options.temperature`)
- [x] format="json" 유지 — Task 2 (기존 유지)
- [x] 한국어 + 이미지 우선 system prompt — Task 2 (`_SYSTEM_PROMPT`)
- [x] 엄격 JSON 스키마 명시 — Task 2 (prompt 내 스키마 포함)
- [x] pil_image=None 폴백 (텍스트 전용) — Task 2 (`if inp.pil_image is not None`)
- [x] 테스트 — Task 1 (docling_service), Task 2 (ollama_client)
- [x] 문서 업데이트 — Task 3

**Placeholder 스캔:** 없음. 모든 스텝에 실제 코드 포함.

**타입 일관성:**
- `_encode_image(img)` → Task 2 정의, Task 2 `extract_receipt`에서 사용 ✓
- `_build_user_prompt(inp: ProcessedInput)` → Task 2 정의, Task 2 `extract_receipt`에서 사용 ✓
- `_make_pipeline_options()` → Task 1 정의, Task 1 `DoclingService.__init__`에서 사용 ✓
- `validate_and_fix`, `ExtractError` — 기존 유지, 시그니처 변경 없음 ✓
