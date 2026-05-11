# Receipt-to-Excel v4

한국 카드/계좌 영수증 PDF·JPG 를 회계 양식 XLSX/PDF 로 자동 변환하는 FastAPI 백엔드.

> 운영 규칙: 루트의 [`/bj-dev/CLAUDE.md`](../CLAUDE.md) 가 진실의 단일 출처.
> 설계 산출물: [`/bj-dev/synthesis/`](../synthesis/) (04 설계, 05 구현 계획).

## 빠른 시작

```bash
# 1) 가상환경 + 의존성 동기화
uv sync

# 2) 환경변수 준비
cp .env.example .env

# 3) 개발 서버 (Phase 1 완료 시점부터 동작)
uv run uvicorn app.main:app --reload

# 4) 테스트
uv run pytest -m "not real_pdf"
uv run mypy --strict app/
uv run ruff check app/
```

## Phase 진행 현황

- [ ] Phase 1 — Scaffold + Auth + CI
- [ ] Phase 2 — DB Models + Migrations + Repositories
- [ ] Phase 3 — Domain + Confidence + Parser Base
- [ ] Phase 4 — Parsers + Resolvers
- [ ] Phase 5 — Templates + XLSX/PDF Generators
- [ ] Phase 6 — Sessions API + JobRunner + SSE
- [ ] Phase 7 — Transactions API + Verify UI
- [ ] Phase 8 — Generation + Download + e2e
