#!/bin/sh
# 백엔드 컨테이너 엔트리포인트.
# 앱은 시작 시 자동 마이그레이션을 하지 않으므로(app/main.py) 부팅 전 스키마를 정렬한다.
# alembic env.py 가 Settings().database_url(=DATABASE_URL env) 로 alembic.ini 를 덮어쓰므로
# compose 의 DATABASE_URL 이 마이그레이션·런타임 모두에 일관 적용된다.
set -eu

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

# JobEventBus/JobRunner 는 app.state in-process 싱글턴(SSE 잡 버스) — 워커 다중화 시
# 잡 상태가 워커별로 분리돼 SSE 가 깨진다. 컨테이너는 단일 워커로 고정한다.
echo "[entrypoint] uvicorn app.main:app :8000 (workers=1)"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
