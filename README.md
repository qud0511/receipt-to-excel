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

## 도커 배포 (운영 단일 명령)

```bash
# 1) 환경변수 준비 (없어도 기본값으로 구동 — REQUIRE_AUTH=false, sqlite)
cp .env.example .env

# 2) ui(:8080) + backend(:8000 내부) 빌드·기동
docker compose up -d --build

# 3) (선택) ollama 포함 — LLM 백오프 사용 시
#    .env 에 LLM_ENABLED=true, OLLAMA_BASE_URL=http://ollama:11434
docker compose --profile llm up -d --build
docker compose exec ollama ollama pull qwen2.5vl:7b
```

- 진입점: `http://localhost:8080` (nginx 가 `/api/` → backend:8000 프록시, SSE 버퍼링 off).
- backend 호스트 포트는 비공개 — 외부 노출은 ui nginx 경유만.
- 영속 데이터(sqlite DB + 사용자 FS): named volume `backend-storage` (`/app/storage`).
- backend 컨테이너는 부팅 시 `alembic upgrade head` 후 uvicorn(단일 워커, SSE 잡 버스 in-process) 기동.
- OCR(easyocr/docling) 기본 제외 — `INSTALL_OCR=true docker compose build backend` 로 opt-in.

## Phase 진행 현황

- [ ] Phase 1 — Scaffold + Auth + CI
- [ ] Phase 2 — DB Models + Migrations + Repositories
- [ ] Phase 3 — Domain + Confidence + Parser Base
- [ ] Phase 4 — Parsers + Resolvers
- [ ] Phase 5 — Templates + XLSX/PDF Generators
- [ ] Phase 6 — Sessions API + JobRunner + SSE
- [ ] Phase 7 — Transactions API + Verify UI
- [ ] Phase 8 — Generation + Download + e2e
