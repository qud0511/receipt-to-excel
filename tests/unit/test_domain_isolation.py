"""Phase 3 DoD — domain 모듈이 db/services/api 를 import 하지 않음을 정적 검증.

CLAUDE.md §"코드 구조": ``domain → (없음, pure pydantic)``.
import-linter 패키지 도입 전까지 AST walk 로 검증 — 빠르고 의존성 없음.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"
_FORBIDDEN_PREFIXES = ("app.db", "app.services", "app.api")


def _iter_domain_files() -> list[Path]:
    return [p for p in _DOMAIN_DIR.rglob("*.py") if p.stat().st_size > 0]


def test_domain_modules_do_not_import_db_services_or_api() -> None:
    offenders: list[str] = []
    for py in _iter_domain_files():
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in _FORBIDDEN_PREFIXES:
                    if node.module.startswith(prefix):
                        offenders.append(f"{py.name}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in _FORBIDDEN_PREFIXES:
                        if alias.name.startswith(prefix):
                            offenders.append(f"{py.name}: import {alias.name}")
    assert not offenders, f"domain 격리 위반: {offenders}"
