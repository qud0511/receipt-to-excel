"""NoteGenerator — R6: 식대면 ``가맹점/meal_type``, 그 외는 ``가맹점만``.

meal_type 시간대는 ``config/meal_type_rules.json`` 의 ``[start_hour, end_hour]`` 형식.
경계 inclusive (06:00 → 조식, 10:00 → 조식, 11:00 → 중식).
"""

from __future__ import annotations

import json
from datetime import time
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "meal_type_rules.json"


def load_meal_rules() -> dict[str, list[int]]:
    data = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"meal_type_rules.json 은 dict 여야 함: {type(data).__name__}")
    return {str(k): list(v) for k, v in data.items()}


def get_meal_type(
    t: time,
    *,
    rules: dict[str, list[int]] | None = None,
) -> str | None:
    """시간대 → meal_type. 경계 inclusive. 매칭 없으면 None."""
    effective_rules = rules if rules is not None else load_meal_rules()
    hour = t.hour
    for meal, bounds in effective_rules.items():
        if len(bounds) != 2:
            continue
        start, end = bounds
        if start <= hour <= end:
            return meal
    return None


def is_food_category(category: str) -> bool:
    return category == "식대"


def generate_note(
    *,
    merchant: str,
    category: str,
    transaction_time: time | None,
) -> str:
    """R6: 식대 + 시각 있음 → ``{merchant}/{meal_type}``. 그 외 → ``{merchant}``."""
    if is_food_category(category) and transaction_time is not None:
        meal = get_meal_type(transaction_time)
        if meal:
            return f"{merchant}/{meal}"
    return merchant
