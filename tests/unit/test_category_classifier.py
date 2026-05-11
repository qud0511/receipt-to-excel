"""Phase 4.7 — CategoryClassifier 5 케이스. config/category_rules.json 의존."""

from __future__ import annotations

from app.services.resolvers.category_classifier import classify_category, load_rules


# ── 1) JSON 파일 로드 — 식대 / __default__ 키 존재 ──────────────────────────
def test_category_rules_loaded_from_json() -> None:
    rules = load_rules()
    assert "식대" in rules
    assert rules["__default__"] == "기타비용"


# ── 2) 식대 raw → 식대 회계 카테고리 ────────────────────────────────────────
def test_business_category_식대_maps_식대() -> None:
    assert classify_category("식대") == "식대"
    # substring 매핑: "일반음식점" 도 "음식점" 키 매치 → 식대.
    assert classify_category("일반음식점") == "식대"


# ── 3) 택시 → 여비교통비 ────────────────────────────────────────────────────
def test_business_category_택시_maps_여비교통비() -> None:
    assert classify_category("택시") == "여비교통비"
    assert classify_category("주유") == "여비교통비"


# ── 4) unknown → 기타비용 (default) ─────────────────────────────────────────
def test_business_category_unknown_maps_기타비용() -> None:
    assert classify_category("미지의업종이름XYZ") == "기타비용"
    # None 입력 (raw 업종 부재) 도 default.
    assert classify_category(None) == "기타비용"


# ── 5) config 파일만 바꿔서 새 카테고리 — 코드 변경 없이 ─────────────────────
def test_new_category_added_via_config_file_without_code_change() -> None:
    custom_rules = {
        "꽃집": "복리후생비",
        "선물": "복리후생비",
        "__default__": "기타비용",
    }
    assert classify_category("꽃집", rules=custom_rules) == "복리후생비"
    assert classify_category("선물세트", rules=custom_rules) == "복리후생비"
    # 기존 rule 에 없던 키 — default.
    assert classify_category("주유", rules=custom_rules) == "기타비용"
