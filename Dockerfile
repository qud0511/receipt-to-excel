# Receipt-to-Excel v4 — 백엔드(FastAPI/uvicorn) 운영 이미지.
# CLAUDE.md "배포": python:3.12-slim-bookworm · non-root · uv sync --frozen 캐시 레이어 · HEALTHCHECK /healthz.
FROM python:3.12-slim-bookworm

# uv 는 CI(.github/workflows/ci.yml)와 동일 버전 고정 — 빌드 재현성.
COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /bin/uv

# UV_PYTHON_DOWNLOADS=0: 슬림 이미지의 시스템 python3.12 만 사용(네트워크 python 다운로드 차단).
# UV_LINK_MODE=copy: 레이어 간 하드링크 경고 제거. UV_COMPILE_BYTECODE=1: 콜드스타트 단축.
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# OCR/LLM heavy extra(easyocr/docling, 200MB+)는 기본 제외 — 운영 배포 첫 step 은 경량.
# 필요 시 `docker build --build-arg INSTALL_OCR=true` 로 opt-in.
ARG INSTALL_OCR=false

# 의존성 레이어 — pyproject/uv.lock 만 먼저 복사해 캐시 적중 극대화.
# --no-install-project: 앱은 /app 의 소스로 직접 구동(패키지 설치 불필요) → README.md(.dockerignore 제외) 의존 회피.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && if [ "$INSTALL_OCR" = "true" ]; then uv sync --frozen --no-dev --no-install-project --extra ocr; fi

# 애플리케이션 소스 + 마이그레이션 + 엔트리포인트.
COPY app ./app
COPY config ./config
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh

# non-root 사용자. storage/ 는 런타임 named volume 마운트 지점 — 이미지 dir 소유권을
# appuser 로 두면 최초 볼륨 생성 시 해당 소유권을 상속(Docker 동작).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# slim 이미지에 curl/wget 없음 → stdlib urllib 로 /healthz liveness 검사.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=4).status==200 else 1)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
