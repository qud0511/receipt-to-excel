# ADR-001 — `mypy.disallow_any_explicit` 비활성화

- 상태: Accepted
- 날짜: 2026-05-11
- Phase: 1 (Scaffold)

## 배경

CLAUDE.md §"가독성"은 `mypy --strict` 와 `Any` 금지를 요구한다. 초기 `pyproject.toml`
은 이를 강제하기 위해 `disallow_any_explicit = true` 를 명시했다.

그러나 Phase 1 첫 `BaseModel` 서브클래스(`_HealthOk`, `_ReadyzResponse` 등) 정의 시점에
mypy 가 6개의 `[explicit-any]` 에러를 보고했다.

```
app/api/routes/health.py:15: error: Explicit "Any" is not allowed
    class _HealthOk(BaseModel):
```

원인은 pydantic v2 의 `BaseModel` 메타클래스(`_ModelMetaclass`)와 generic 기반
`__class_getitem__` 시그니처에 내부적으로 `Any` 가 노출되어, **서브클래스 정의 라인 자체**가
explicit-any 위반으로 판정되는 것이다. `pydantic.mypy` plugin 활성화 후에도 동일하다.

## 결정

`mypy.disallow_any_explicit` 를 제거한다.

`Any` 회피 정책은 다음 두 장치로 대체한다:

1. **mypy** — `strict = true` + `disallow_any_generics` + `warn_return_any` 유지
   (제네릭 형태의 implicit Any 와 반환값 Any 는 여전히 차단).
2. **ruff** — `select` 에 `ANN401` 추가. 우리 코드 함수 시그니처에 `Any` 가 등장하면
   lint 단계에서 차단된다.

`Any` 가 진정으로 불가피한 외부 라이브러리 boundary 는 `# type: ignore[...]` + 사유 주석
한 줄로 처리 (CLAUDE.md §"가독성" 단서 조항).

## 결과

- mypy `--strict` 가 0 error 로 통과한다.
- 우리 코드에서 `def f(x: Any) -> Any` 같은 패턴은 여전히 ruff 가 차단한다.
- `disallow_any_explicit` 만큼 광범위하지는 않지만 (변수 annotation 의 `Any` 는 미검출),
  실무에서 가장 흔한 함수 시그니처 누출 경로는 막힌다.

## 대안

- pydantic.mypy plugin: 활성화해도 본 이슈 미해결 (확인됨).
- per-file `# type: ignore[explicit-any]`: 모든 `BaseModel` 서브클래스마다 부착 필요 —
  코드 노이즈가 과도하며 신규 모델 추가 시 누락 위험 상존.

## 참조

- pydantic GitHub Issue #6231 (BaseModel + disallow_any_explicit 호환성).
- CLAUDE.md §"가독성".
- synthesis/05 §Phase 1.
