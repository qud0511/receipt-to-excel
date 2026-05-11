"""SQLAlchemy 2 declarative Base — Task 2.2 에서 11 테이블 구현 예정."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 base."""
