"""SQLAlchemy 2 ORM — 11 테이블. CLAUDE.md §"보안": 모든 변경 쿼리 user_id WHERE 책임은 Repository.

도메인은 한글 (가맹점명/거래일/금액) 이지만 DB 컬럼명은 영문 snake_case.
한↔영 매핑은 schemas/_mappers.py 한 곳에서만 (CLAUDE.md §"가독성").
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 base."""


class _TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ── 1. User ───────────────────────────────────────────────────────────────────
class User(_TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    oid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # default_card_id: User ↔ Card 순환 참조 — use_alter 로 deferred FK.
    default_card_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "card.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_user_default_card_id",
        ),
        nullable=True,
    )
    # Phase 8.7: 사용자별 처리시간 baseline EMA 누적기(거래당 초). None=아직 없음.
    baseline_s_per_tx: Mapped[float | None] = mapped_column(Float, nullable=True)


# ── 2. Card ───────────────────────────────────────────────────────────────────
class Card(_TimestampMixin, Base):
    __tablename__ = "card"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    # AD-2: 표준 형식 NNNN-****-****-NNNN — 32자 여유.
    card_number_masked: Mapped[str] = mapped_column(String(32))
    card_type: Mapped[Literal["법인", "개인"]] = mapped_column(String(8))
    card_provider: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "card_number_masked", name="uq_card_user_number"),
        CheckConstraint("card_type IN ('법인', '개인')", name="ck_card_type"),
        # CLAUDE.md §"성능": card_meta(user_id, card_number_masked) 인덱스.
        Index("ix_card_user_masked", "user_id", "card_number_masked"),
    )


# ── 3. Template ───────────────────────────────────────────────────────────────
class Template(_TimestampMixin, Base):
    __tablename__ = "template"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    # TemplateConfig.sheets 직렬화 — Phase 5 에서 정확한 schema 정의.
    sheets_json: Mapped[dict[str, object]] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Phase 6 (ADR-011): Template Analyzer 결과 — 모든 시트 analyzable=True 면 mapped,
    # 한 시트라도 False 면 needs_mapping. UI Templates sidebar 의 "매핑 필요" flag 매핑.
    mapping_status: Mapped[Literal["mapped", "needs_mapping"]] = mapped_column(
        String(16), default="mapped", nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "mapping_status IN ('mapped', 'needs_mapping')",
            name="ck_template_mapping_status",
        ),
    )


# ── 4. Vendor ─────────────────────────────────────────────────────────────────
class Vendor(Base):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_vendor_user_name"),
        # CLAUDE.md §"성능": vendor(user_id, last_used_at DESC).
        Index("ix_vendor_user_last_used", "user_id", "last_used_at"),
    )


# ── 5. Project ────────────────────────────────────────────────────────────────
class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("vendor_id", "name", name="uq_project_vendor_name"),
        # CLAUDE.md §"성능": project(vendor_id, last_used_at DESC).
        Index("ix_project_vendor_last_used", "vendor_id", "last_used_at"),
    )


# ── 6. Merchant ───────────────────────────────────────────────────────────────
class Merchant(Base):
    __tablename__ = "merchant"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    # 정규화된 가맹점명 (registry-time normalization).
    # AD-1: raw Transaction.merchant_name 은 immutable 이며 본 컬럼과 별개.
    name: Mapped[str] = mapped_column(String(255))
    business_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    auto_expense_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── 7. TeamGroup ──────────────────────────────────────────────────────────────
class TeamGroup(Base):
    __tablename__ = "team_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    members: Mapped[list[TeamMember]] = relationship(
        back_populates="team_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# ── 8. TeamMember ─────────────────────────────────────────────────────────────
class TeamMember(Base):
    __tablename__ = "team_member"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_group_id: Mapped[int] = mapped_column(
        ForeignKey("team_group.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))

    team_group: Mapped[TeamGroup] = relationship(back_populates="members")


# ── 9. UploadSession ──────────────────────────────────────────────────────────
class UploadSession(_TimestampMixin, Base):
    __tablename__ = "upload_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    year_month: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"
    batch_card_type: Mapped[Literal["법인", "개인"] | None] = mapped_column(
        String(8), nullable=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("template.id", ondelete="SET NULL"), nullable=True
    )
    source_filenames: Mapped[list[str]] = mapped_column(JSON)
    # Phase 6: 'review' → 'awaiting_user' rename (ADR-010 D-3 + 사용자 4-state 동의).
    # parsing: OCR/LLM 진행, awaiting_user: 검수 대기 (구 review),
    # generated: 검수 완료 + 파일 생성됨, failed: 잡 실패.
    status: Mapped[Literal["parsing", "awaiting_user", "generated", "failed"]] = mapped_column(
        String(16)
    )
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Phase 6: 처리 시간 메트릭 (Dashboard "절약된 시간" + Result "처리 시간 N분 N초").
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Phase 6: 사용자가 명시적으로 "제출" 표시한 시각. NULL = 작성중, NOT NULL = 제출완료.
    # Dashboard "최근 작성한 지출결의서" status 라벨 결정 (UI 캡처: 작성중/제출완료).
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase 8.7: baseline EMA 멱등 — 이미 반영된 세션은 재처리해도 재반영 안 함.
    counted_in_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Phase 8.7: 이 세션이 비교한 baseline 스냅샷(거래당 초). None=콜드스타트 시드(학습 중).
    baseline_ref_s_per_tx: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('parsing', 'awaiting_user', 'generated', 'failed')",
            name="ck_upload_session_status",
        ),
        CheckConstraint(
            "batch_card_type IS NULL OR batch_card_type IN ('법인', '개인')",
            name="ck_upload_session_batch_card_type",
        ),
    )

    def get_year_month(self) -> str:
        """R12 — 다중월 확장 시 본 accessor 하나만 바꾸면 라우터/리포지토리 전부 흡수."""
        return self.year_month


# ── 10. Transaction ───────────────────────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("upload_session.id", ondelete="CASCADE"), index=True
    )
    # 빠른 사용자 단위 필터 위해 denormalized — Repository 가 user_id WHERE 강제.
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    # AD-4 Raw — AD-1 immutable.
    merchant_name: Mapped[str] = mapped_column(String(255))
    transaction_date: Mapped[date] = mapped_column(Date)
    transaction_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    # CLAUDE.md §"특이사항": 금액은 항상 int gt=0 (원 단위), float 금지.
    amount: Mapped[int] = mapped_column(Integer)
    supply_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    business_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # AD-2 — NNNN-****-****-NNNN 형식만 허용 (Repository 진입 시점 검증).
    card_number_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_provider: Mapped[str] = mapped_column(String(64))

    # AD-4 Derived.
    card_type: Mapped[Literal["법인", "개인"] | None] = mapped_column(String(8), nullable=True)
    parser_used: Mapped[Literal["rule_based", "ocr_hybrid", "llm"]] = mapped_column(String(16))
    # dict[str, "high"|"medium"|"low"|"none"] — Phase 3 confidence labeler 산출물.
    field_confidence: Mapped[dict[str, str]] = mapped_column(JSON)

    source_filename: Mapped[str] = mapped_column(String(255))
    source_file_path: Mapped[str] = mapped_column(String(512))
    # Phase 6: 한글 원본 파일명 metadata (UploadGuard 가 source_filename 은 uuid 디스크명 저장,
    # 원본명은 본 컬럼만 — CLAUDE.md 보안 + ADR-010 추천 7).
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # CLAUDE.md §"성능": transaction(session_id, user_id) 인덱스.
        Index("ix_transaction_session_user", "session_id", "user_id"),
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
        CheckConstraint(
            "parser_used IN ('rule_based', 'ocr_hybrid', 'llm')",
            name="ck_transaction_parser_used",
        ),
        CheckConstraint(
            "card_type IS NULL OR card_type IN ('법인', '개인')",
            name="ck_transaction_card_type",
        ),
    )


# ── 11. ExpenseRecord ─────────────────────────────────────────────────────────
class ExpenseRecord(_TimestampMixin, Base):
    __tablename__ = "expense_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("project.id", ondelete="SET NULL"), nullable=True
    )
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attendees_json: Mapped[list[str]] = mapped_column(JSON)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receipt_attachment_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    xlsx_sheet: Mapped[Literal["법인", "개인"]] = mapped_column(String(8))
    expense_column: Mapped[str] = mapped_column(String(64))
    auto_note: Mapped[str] = mapped_column(String(512))

    __table_args__ = (
        CheckConstraint(
            "xlsx_sheet IN ('법인', '개인')",
            name="ck_expense_record_xlsx_sheet",
        ),
    )


# ── 12. GeneratedArtifact (Phase 6, ADR-010 D-4; Phase 8.8 kind 분리) ─────────
class GeneratedArtifact(Base):
    """잡 완료 후 생성된 파일 (XLSX / layout PDF / merged PDF / ZIP) — Session 1:N.

    Phase 8.8: 단일 ``pdf`` kind 을 두 kind 로 분리.
    - layout_pdf: PNG/JPG 영수증 → A4 모아찍기 (per_page=2~3, R11)
    - merged_pdf: PDF 영수증 원본 → 거래일 ASC 페이지 병합
    """

    __tablename__ = "generated_artifact"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("upload_session.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[Literal["xlsx", "layout_pdf", "merged_pdf", "zip"]] = mapped_column(
        String(16)
    )
    fs_path: Mapped[str] = mapped_column(String(512))
    display_filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "artifact_type IN ('xlsx', 'layout_pdf', 'merged_pdf', 'zip')",
            name="ck_generated_artifact_type",
        ),
        Index("ix_generated_artifact_session", "session_id", "user_id"),
    )
