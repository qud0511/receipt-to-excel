"""Phase 4.7 — NoteGenerator 4 케이스 (R6: 식대 + meal_type)."""

from __future__ import annotations

from datetime import time

from app.services.resolvers.note_generator import generate_note, get_meal_type


# ── 1) 식대 — 가맹점 + meal_type (R6) ───────────────────────────────────────
def test_food_note_includes_meal_type_from_time() -> None:
    note = generate_note(
        merchant="스타벅스 명동점",
        category="식대",
        transaction_time=time(8, 30),
    )
    assert note == "스타벅스 명동점/조식"


# ── 2) 식대 외 — 가맹점만 ───────────────────────────────────────────────────
def test_non_food_note_uses_merchant_only() -> None:
    note = generate_note(
        merchant="지하철공사",
        category="여비교통비",
        transaction_time=time(8, 30),
    )
    assert note == "지하철공사"


# ── 3) meal_type 시간 boundary inclusive ────────────────────────────────────
def test_meal_type_time_boundaries_inclusive() -> None:
    assert get_meal_type(time(6, 0)) == "조식"  # 06:00 시작
    assert get_meal_type(time(10, 0)) == "조식"  # 10:xx 도 조식
    assert get_meal_type(time(11, 0)) == "중식"
    assert get_meal_type(time(14, 0)) == "중식"
    assert get_meal_type(time(17, 0)) == "석식"
    assert get_meal_type(time(21, 0)) == "석식"
    # 경계 밖 — None.
    assert get_meal_type(time(15, 0)) is None
    assert get_meal_type(time(23, 0)) is None


# ── 4) transaction_time=None — meal_type 생략 ────────────────────────────────
def test_null_time_omits_meal_type() -> None:
    note = generate_note(
        merchant="스타벅스",
        category="식대",
        transaction_time=None,
    )
    assert note == "스타벅스"
