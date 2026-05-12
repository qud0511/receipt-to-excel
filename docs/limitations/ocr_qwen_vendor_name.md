---
title: OCR Hybrid (qwen2.5vl) 가맹점명 빈 응답 한계
status: known_limitation
date: 2026-05-12
refs:
  - tests/smoke/results/20260512.md (3차 smoke 88% — 잔여 실패 5건 전체)
  - ADR-002 (Ollama 모델 선정)
  - ADR-007, ADR-008 (rule_based 경로 보강 완료 후 격리됨)
---

# 요약

3차 smoke (37/42 = 88%) 의 잔여 실패 **5 건 전체 (hana 2 + kakaobank 3)** 가
동일 패턴: **OCR Hybrid 경로의 LLM (qwen2.5vl:7b) 이 가맹점명 빈 문자열 반환**.

본 한계는 Phase 4 의 rule_based 보강 (ADR-007/008) 으로 격리됨 — 텍스트 임베디드
PDF 는 100 % rule_based 경유, JPG (이미지 영수증) 만 본 한계의 영향을 받음.

# 영향 범위 (좁음)

| 입력 유형 | 경로 | 본 한계 영향 |
| --- | --- | --- |
| 텍스트 임베디드 PDF | rule_based | ❌ 무관 (영향 0) |
| 이미지 PDF (스캔본) | OCR Hybrid | ⚠️ 잠재 영향 (현재 hyundai_01, lotte_01 은 성공) |
| JPG 영수증 | OCR Hybrid | ⚠️ **본 한계 영향** (5/7 실패: hana, kakaobank) |

성공 사례 (`hyundai_01.pdf`, `lotte_01.pdf`, `woori_legacy_01/02.jpg`): qwen2.5vl 응답 일관성
이 일관성 운에 의존. 동일 입력 대비 응답 가변성 존재.

# 재현 조건

1. 입력: 한글 영수증 JPG (특히 hana, kakaobank 카카오뱅크 OCR 후처리 케이스).
2. 경로: `app/services/parsers/ocr_hybrid/`
   - `DoclingService` 가 EasyOCR 로 한글 텍스트 추출 → OCR 텍스트 hint
   - `OllamaVisionClient` 가 이미지 + hint 를 qwen2.5vl 에 전달
   - LLM 이 JSON `{"가맹점명": "..."}` 형식 응답
3. 실패 양상: 응답 JSON 의 `가맹점명` 키가 빈 문자열 `""` 반환.
4. 후처리: `ParsedTransaction` 의 `가맹점명: str` 이 empty string 을 허용 (Pydantic
   strict 미차단), smoke `assert result.가맹점명` 만 차단.

# 책임 분리 — 본 한계가 다루는 것 / 다루지 않는 것

**다루는 것**:
- 5 건 실패의 단일 근본 원인이 LLM 응답 일관성임을 명시.
- OCR Hybrid 경로의 알려진 한계로 분류.
- Phase 5 (Templates + XLSX) 진입 결정 시 본 한계 별도 트랙 (Phase 4.6 또는 Phase 5 후반).

**다루지 않는 것**:
- rule_based 경로의 결함 — ADR-007, ADR-008 으로 별도 해결됨.
- Provider 감지 — ADR-007 으로 별도 해결됨.
- qwen2.5vl 모델 자체 교체 — ADR-002 의 재검토 사안.

# 해소 방안 (후속 ADR-009 후보)

본 한계 해소는 별도 ADR-009 로 추적 권장. 후보 전략:

1. **빈 응답 retry 로직** — `OllamaVisionClient.generate()` 가 `가맹점명 == ""` 인
   응답에 대해 1-2 회 재시도 (temperature=0.0 유지, prompt 동일). 비용 ~30-60s
   추가 latency × 일부 케이스.
2. **프롬프트 강화** — `ocr_hybrid/prompt.py` 의 시스템 지시를 "한글 가맹점명을
   반드시 추출, 비어 있으면 OCR hint 의 가장 두드러진 한글 명사 사용" 으로 강화.
3. **OCR hint 후처리 fallback** — LLM 가 empty 반환 시 EasyOCR 추출 텍스트의
   첫 한글 라인을 가맹점명으로 사용 (confidence=low).
4. **모델 교체** — qwen2.5vl 외에 `llava:34b` 또는 `gemma3:vision` 평가 (ADR-002 재검토).
5. **Pydantic 강화** — `ParsedTransaction.가맹점명: str` 에 `min_length=1` 추가
   → LLM 빈 응답 시 Pydantic strict 차단 → caller 가 fallback 결정. (단, 다른 경로
   의도하지 않은 영향 검토 필요.)

후속 ADR-009 작성 시 위 전략 평가 + 채택 명시.

# Phase 5 진입에 미치는 영향 — **없음 또는 제한적**

본 한계는 **Phase 4 → Phase 5 진입 차단 사유 아님**:

- Phase 5 작업은 `services/templates/` + `services/xlsx_writer/` + `services/pdf_generator/`
  → ParsedTransaction → XLSX 매핑 (입력 측 변환). 본 한계는 입력 측 7건 / 42건의
  품질 문제로, Phase 5 의 mapping 로직과 직교.
- 사용자 운영 시 hana/kakaobank JPG 5건은 수동 가맹점명 입력 또는 재OCR 으로 대응
  가능 (CLAUDE.md §"자동완성 < 100ms" 의 vendor_matcher 가 도움).
- Phase 5 완료 + 본 한계 해소 (ADR-009) 는 병행 트랙으로 가능.

# 사용자 작업 권장

운영 단계에서 본 한계 영향 받는 경우:

1. **hana / kakaobank JPG 영수증**: 가맹점명 빈 응답 검출 시 사용자 수동 입력.
2. **자동완성 활용**: `services/resolvers/vendor_matcher.py` 가 기존 가맹점명
   레지스트리에서 유사 매칭 제공.
3. **Phase 4.6 또는 Phase 5 후반 ADR-009 처리** — 위 후보 1, 2, 3 우선 평가.

# 검증 데이터

| File | 카드사 | OCR Hint 한글 추출 | LLM 응답 가맹점명 | smoke 결과 |
| --- | --- | --- | --- | --- |
| hana_01.jpg | hana | (확인 필요) | `""` | FAIL |
| hana_02.jpg | hana | (확인 필요) | `""` | FAIL |
| kakaobank_01.jpg | kakaobank | (확인 필요) | `""` | FAIL |
| kakaobank_02.jpg | kakaobank | (확인 필요) | `""` | FAIL |
| kakaobank_03.jpg | kakaobank | (확인 필요) | `""` | FAIL |

OCR Hint 검증은 ADR-009 작성 시점에 실 자료 dump 로 보강.
