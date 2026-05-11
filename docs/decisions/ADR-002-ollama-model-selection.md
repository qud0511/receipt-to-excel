# ADR-002 — Ollama 모델 선정: `qwen2.5vl:7b`

- 상태: Accepted
- 날짜: 2026-05-11
- Phase: 4 (Smoke Gate 진입 시점)

## 컨텍스트

Phase 4 OCR Hybrid + LLM-only 가 Ollama Vision API 에 의존한다. Phase 4 초안은
default 모델로 `gemma4` 를 명시했지만, 실 배포 서버 환경에서 다음 제약이 확인됨:

- **GPU 없음**: NVIDIA / AMD GPU 미장착. PyTorch `CUDA_AVAILABLE=False`.
- **CPU 추론 성능**: `gemma4` 는 영수증 1장당 5~15분 (smoke 39장 → 최소 3시간).
- **Smoke Gate 가용성**: synthesis/05 §Phase 4 의 `< 60s/file` 기준 자체가 비현실적.

이대로는 Phase 5 진입 게이트가 사실상 통과 불가.

## 결정

기본 Ollama 모델을 **`qwen2.5vl:7b`** 로 교체.

영향 파일:
- `app/core/config.py` — `Settings.ollama_model` default
- `.env.example` — `OLLAMA_MODEL` 키 값
- 운영 사전 작업: `ollama pull qwen2.5vl:7b` (≈ 6GB 다운로드)

## 근거

| 항목 | `qwen2.5vl:7b` | `gemma4` |
|---|---|---|
| OCR / 구조화 추출 특화 | ✅ Vision-Language 모델, 영수증/문서 강점 | △ general purpose |
| 한국어 지원 | ✅ Qwen2.5 multilingual (한국어 포함) | ✅ |
| CPU 추론 | ✅ Q4 양자화 시 30~60s/page (예상) | ❌ 5~15분/page |
| VRAM 요구 (선택) | 8GB (GPU 가용 시) | 12GB+ |
| 모델 크기 | ≈ 6GB | ≈ 7GB |
| Ollama 가용성 | ✅ `ollama pull qwen2.5vl:7b` | ✅ |

Smoke 39장 처리시간 예상치: **20~40분** (이전 3시간 → 90% 단축).

## 대안 검토

1. **`gemma4` 유지 + GPU 서버 확보**: 인프라 변경 요구. 단기 비현실.
2. **`llama3.2-vision`**: 8GB+ VRAM 필요. CPU 동작 가능하나 OCR 정확도 `qwen2.5vl` 대비 열세 (영수증 도메인).
3. **`moondream2`**: 경량 (2B) Vision LM. CPU 빠름. **한국어 인식 약함** — AD-1/AD-2 한글 추출 회귀 위험.
4. **`llava`**: 7B/13B 변형. 한국어 지원 약함. OCR 정확도 `qwen2.5vl` 미달.

## 결과

- **Smoke Gate 실현 가능**: 39장 20~40분 → Phase 5 진입 차단 해소.
- **품질 trade-off 위험**: 영수증 도메인 정확도는 smoke 결과로 검증 — 실패 케이스가 다수면
  parser/postprocessor 보강 (Phase 4.5 의 정규식 후처리 패턴 확장) 으로 흡수.
- **확장 포인트 유지**: Ollama 모델 변경은 `.env` 1줄 + 본 ADR. 코드 변경 없음
  (Settings.ollama_model 만 참조).

## 후속 작업

1. 사용자가 `ollama pull qwen2.5vl:7b` 수동 실행.
2. `uv run pytest tests/smoke/ -m real_pdf` 재실행.
3. Smoke 결과 (`tests/smoke/results/YYYYMMDD.md`) 보고 — 실패 케이스 시 본 ADR 에 정확도
   섹션 추가 + 후속 ADR 로 모델 변경.

## 참조

- synthesis/05 §Phase 4 Smoke Gate
- CLAUDE.md §"성능: 컨테이너 메모리 ≥8GB (qwen2.5vl 7B + 앱)"
- Phase 4.4 docling buffer fix (DocumentConverter 가 BytesIO 미허용) — 별개 버그, 본 ADR 과 동시 해소.
