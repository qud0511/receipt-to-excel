"""CategoryClassifier — raw business_category → 회계 카테고리.

``config/category_rules.json`` 단일 파일 변경으로 카테고리 확장 가능
(CLAUDE.md §"코드 구조: 새 카테고리/meal_type = config/*.json 1 파일").
"""

from __future__ import annotations

import json
from pathlib import Path

# /bj-dev/v4/app/services/resolvers/category_classifier.py → parents[3] = /bj-dev/v4
_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "category_rules.json"
_DEFAULT_KEY = "__default__"


def load_rules() -> dict[str, str]:
    """category_rules.json 디스크 로드."""
    data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"category_rules.json 은 dict 여야 함: {type(data).__name__}")
    return {str(k): str(v) for k, v in data.items()}


def classify_category(
    business_category: str | None,
    *,
    rules: dict[str, str] | None = None,
) -> str:
    """raw business_category 에 substring 매핑 → 회계 카테고리.

    매핑 안 되면 ``__default__`` 키 값 (보통 "기타비용"). 키 ``__*__`` 는 메타.
    """
    effective_rules = rules if rules is not None else load_rules()
    default = effective_rules.get(_DEFAULT_KEY, "기타비용")

    if business_category is None:
        return default

    for keyword, category in effective_rules.items():
        if keyword.startswith("__"):
            continue
        if keyword in business_category:
            return category

    return default
