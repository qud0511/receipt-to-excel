# Smoke Gate — 실 카드사 매출전표 검증

CI 에서는 실행하지 않는 **로컬 전용 smoke** suite. 합성 fixture 가 못 잡는 실 카드사
양식 변동성을 Phase 5 진입 전 1회 검증 (synthesis/05 §Phase 4 Smoke Gate).

## 사전 준비

1. **실 자료 보관** — `tests/smoke/real_pdfs/` (gitignore). 본 디렉토리는 비어 있어야 하며
   사용자가 다음 명명 규칙으로 직접 채운다:

   | provider | 파일명 | 갯수 |
   |---|---|---|
   | shinhan | `shinhan_NN.pdf` | 12 |
   | shinhan (택시) | `shinhan_taxi_NN.pdf` | 6 |
   | samsung | `samsung_NN.pdf` | 8 |
   | kbank | `kbank_NN.pdf` | 5 |
   | kakaobank | `kakaobank_NN.jpg` | 3 |
   | hana (stub fallback) | `hana_NN.jpg` | 2 |
   | woori (stub fallback) | `woori_NN.jpg` | 2 |
   | lotte (stub fallback) | `lotte_NN.pdf` | 1 |

2. **OCR 의존성 설치** — kakaobank JPG + hana/woori/lotte fallback 검증용.
   ```bash
   uv sync --extra ocr
   ```

3. **Ollama 인스턴스 실행** — `.env` 의 `OLLAMA_BASE_URL` (기본 `http://localhost:11434`)
   에 `gemma4` 모델 가용해야 한다.

## 실행

```bash
uv run pytest tests/smoke/ -m real_pdf --no-header -q
```

CI 는 `-m "not real_pdf"` 로 본 suite 제외 (`.github/workflows/ci.yml`).

## 검증 기준 (per file)

- `가맹점명` / `거래일` / `금액` 3개 필수 필드가 `None` 이면 실패.
- `field_confidence` 에 `high` 또는 `medium` 라벨 1개 이상.
- 처리 시간:
  - `parser_used="rule_based"` → < 5s
  - `parser_used="ocr_hybrid"` → < 60s
- 기대 `parser_used`:
  - shinhan/samsung/kbank PDF → `rule_based`
  - kakaobank JPG → `ocr_hybrid` (kakaobank postprocessor 로그 트리거)
  - hana/woori/lotte → `ocr_hybrid` + 로그 `tier_skipped="rule_based:stub"`

## 결과 기록

각 실행은 `tests/smoke/results/YYYYMMDD.md` 에 자동 누적 (gitignore).

```markdown
# Smoke Run — 2026-05-12

| file | parser_used | 가맹점명 | 거래일 | 금액 | confidence(high+medium) | latency_s |
|---|---|---|---|---|---|---|
| samsung_01.pdf | rule_based | 스타벅스 명동점 | 2025-12-08 | 8900 | 7/9 | 0.4 |
| kakaobank_01.jpg | ocr_hybrid | 갈비집 | 2025-12-10 | 150000 | 5/9 | 23.4 |
| ...
```

## Phase 5 진입 게이트

위 smoke 를 확보된 11+ 파일로 실행해 `results/YYYYMMDD.md` 기록 후 진입.
실패 케이스가 있으면 다음 중 하나로 해소:
1. parser / postprocessor 보강 (예: 정규식 추가)
2. 합성 fixture 보강 + 알려진 한계 문서화 (`docs/limitations/`)
