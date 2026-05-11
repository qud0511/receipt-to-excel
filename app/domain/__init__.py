"""순수 pydantic 도메인 — db/services/api 의존 금지 (CLAUDE.md §"코드 구조").

도메인 필드는 한글 (가맹점명/거래일/금액). API 스키마는 snake_case 영문.
한↔영 매핑은 ``schemas/_mappers.py`` 한 곳에서만 (Phase 6 도입 예정).
"""
