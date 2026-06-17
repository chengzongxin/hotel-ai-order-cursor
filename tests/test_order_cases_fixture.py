"""业务验收用例 fixtures 的基础自动化检查。

这组测试不调用 LLM，目标是保证 `order_cases.json` 中的核心验收资产
能被 pytest 读取，并且关键追问规则与后端兜底问题保持一致。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from graph.builder import build_missing_info_fallback_question


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "order_cases.json"
REQUIRED_CATEGORIES = {
    "normal",
    "missing_field",
    "fuzzy",
    "asr_error",
    "deviation",
    "malicious",
    "multi_turn",
}


@pytest.fixture(scope="module")
def order_cases() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return data["cases"]


@pytest.fixture(scope="module")
def order_cases_meta() -> dict[str, Any]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {key: value for key, value in data.items() if key != "cases"}


def test_order_cases_fixture_meta(order_cases_meta: dict[str, Any]):
    assert order_cases_meta.get("version")
    assert order_cases_meta.get("domain") == "hotel_order"
    assert isinstance(order_cases_meta.get("fields"), list)


def test_order_cases_cover_core_risk_categories(order_cases: list[dict[str, Any]]):
    categories = {case["category"] for case in order_cases}
    assert REQUIRED_CATEGORIES.issubset(categories)


def test_order_cases_ids_are_unique(order_cases: list[dict[str, Any]]):
    ids = [case["id"] for case in order_cases]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_order_cases_have_expected_fields(order_cases: list[dict[str, Any]]):
    for case in order_cases:
        assert case.get("id")
        assert case.get("category") in REQUIRED_CATEGORIES
        assert case.get("title")
        assert case.get("turns")
        assert case.get("expected_behavior")
        assert case.get("acceptance")
        assert len(case["acceptance"]) >= 1
        assert any(turn["role"] == "user" for turn in case["turns"])


def test_order_cases_with_expected_question_have_missing_info(order_cases: list[dict[str, Any]]):
    for case in order_cases:
        if case.get("expected_question"):
            assert case.get("expected_missing_info"), case["id"]


@pytest.mark.parametrize(
    ("case_id", "missing_info", "expected_question"),
    [
        ("missing_001", ["room_number"], "请问您住哪个房间？"),
        ("missing_002", ["fault"], "具体是什么故障呢？"),
        ("missing_003", ["product"], "是哪样东西坏了？"),
    ],
)
def test_missing_field_questions_match_backend_fallback(
    order_cases: list[dict[str, Any]],
    case_id: str,
    missing_info: list[str],
    expected_question: str,
):
    case = next(item for item in order_cases if item["id"] == case_id)

    assert case["expected_missing_info"] == missing_info
    assert build_missing_info_fallback_question(missing_info) == expected_question


def test_all_expected_questions_match_backend_fallback(order_cases: list[dict[str, Any]]):
    for case in order_cases:
        question = case.get("expected_question")
        missing = case.get("expected_missing_info")
        if not question or not missing:
            continue
        assert build_missing_info_fallback_question(missing) == question, case["id"]
