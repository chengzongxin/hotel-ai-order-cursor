"""Executable workflow policy evals backed by JSON fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from services.order_policy import build_order_card_fields, collect_missing_order_info
from services.service_types import resolve_order_submit_route
from workflow.builder import route_after_search_product, route_after_validation
from schemas.order_preview import build_order_preview_model

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "workflow_policy_cases.json"


@pytest.fixture(scope="module")
def workflow_policy_cases() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert data["domain"] == "hotel_order_workflow_policy"
    return data["cases"]


def build_state(case: dict[str, Any]) -> dict[str, Any]:
    service_type = case["service_type"]
    order_info = dict(case.get("order_info") or {})
    order_card_fields = build_order_card_fields(
        service_type=service_type,
        order_info=order_info,
        order_context=case.get("order_context") or {},
    )
    missing_info = collect_missing_order_info(service_type, order_info, order_card_fields)
    if case.get("phase") == "product_selection" and not case.get("selected_product_code"):
        missing_info = ["selected_product"]

    return {
        "phase": case["phase"],
        "service_type": service_type,
        "effective_service_type": case.get("effective_service_type") or service_type,
        "order_submit_route": resolve_order_submit_route(case.get("effective_service_type") or service_type),
        "order_info": order_info,
        "order_card_fields": order_card_fields if case.get("selected_product_code") else [],
        "products": case.get("products") or [],
        "selected_product_code": case.get("selected_product_code"),
        "missing_info": missing_info,
    }


@pytest.mark.parametrize("case_index", range(6))
def test_workflow_policy_cases(case_index: int, workflow_policy_cases: list[dict[str, Any]]):
    case = workflow_policy_cases[case_index]
    expected = case["expected"]
    state = build_state(case)

    assert state["order_submit_route"] == expected["order_submit_route"]
    assert state["missing_info"] == expected["missing_info"]

    preview = build_order_preview_model(state)
    assert preview is not None
    payload = preview.model_dump(mode="json")
    assert payload["phase"] == expected["preview_phase"]
    assert payload["missing_info"] == expected["missing_info"]

    expected_card_keys = expected.get("card_keys")
    if expected_card_keys:
        assert [item["key"] for item in payload["order_card"]["fields"]] == expected_card_keys

    if expected.get("next_after_validation"):
        assert route_after_validation(state) == expected["next_after_validation"]
    if expected.get("next_after_search"):
        assert route_after_search_product(state) == expected["next_after_search"]
