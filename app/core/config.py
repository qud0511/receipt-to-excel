"""애플리케이션 설정 — 모든 환경 변수의 단일 진입점."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 → 타입 안전 설정. CLAUDE.md §"보안": os.environ 직접 접근 금지."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 인증
    require_auth: bool = False
    azure_tenant_id: str = ""
    azure_client_id: str = ""

    # DB
    database_url: str = "sqlite+aiosqlite:///storage/app.db"

    # LLM / Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    llm_enabled: bool = False

    # 관측성
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # CORS / 업로드 — 빈 문자열은 비활성으로 해석.
    cors_origins: str = ""
    max_upload_size_mb: int = Field(default=20, gt=0, le=1024)
    max_batch_size_mb: int = Field(default=200, gt=0, le=4096)

    @model_validator(mode="after")
    def _validate_auth_config(self) -> Settings:
        # REQUIRE_AUTH=true 면 Azure 자격 필수 — 부팅 시점에 차단해
        # 런타임에 익명 토큰을 통한 우회를 원천 봉쇄 (CLAUDE.md §"보안").
        if self.require_auth:
            if not self.azure_tenant_id:
                raise ValueError("REQUIRE_AUTH=true requires AZURE_TENANT_ID")
            if not self.azure_client_id:
                raise ValueError("REQUIRE_AUTH=true requires AZURE_CLIENT_ID")
        return self


def get_settings() -> Settings:
    """FastAPI Depends 진입점 — 후속 Phase 에서 lru_cache 도입 예정."""
    return Settings()
