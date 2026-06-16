"""LangGraph route contract tests."""

from workflow.routes import (
    route_after_confirm,
    route_after_intent,
    route_after_search_product,
    route_after_validation,
)


def test_route_after_intent_cancels_active_order():
    assert route_after_intent({"intent": "cancel_order", "order_info": {}}) == "cancel_node"
    assert route_after_intent({"intent": "create_order", "order_info": {"user_cancelled": True}}) == "cancel_node"


def test_route_after_intent_uses_assist_only_without_active_order():
    assert route_after_intent({"intent": "smalltalk", "phase": "idle"}) == "assist_node"
    assert route_after_intent({"intent": "smalltalk", "phase": "pre_order"}) == "ask_node"


def test_route_after_intent_accepts_product_selection_text():
    assert (
        route_after_intent(
            {
                "intent": "smalltalk",
                "phase": "product_selection",
                "products": [{"service_product_code": "A"}],
                "last_user_message": "1",
            }
        )
        == "search_product_node"
    )


def test_route_after_search_product_requires_selected_product():
    products = [{"service_product_code": "A", "service_product_name": "门锁"}]

    assert route_after_search_product({"product_selection_rejected": True}) == "ask_node"
    assert route_after_search_product({"products": products, "selected_product_code": None}) == "ask_node"
    assert route_after_search_product({"products": products, "selected_product_code": "A"}) == "coverage_node"


def test_route_after_validation_and_confirm():
    assert route_after_validation({"missing_info": ["phone"]}) == "ask_node"
    assert route_after_validation({"missing_info": []}) == "confirm_node"
    assert route_after_confirm({"order_info": {"user_confirmed": True}}) == "submit_node"
