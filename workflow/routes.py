"""LangGraph conditional routing helpers."""

from __future__ import annotations

from langgraph.graph import END

from workflow.constants import ACTIVE_ORDER_PHASES
from workflow.products import get_selected_product
from workflow.state import AgentState
from workflow.text_parsing import parse_product_selection


def has_active_order(state: AgentState) -> bool:
    return state.get("phase") in ACTIVE_ORDER_PHASES


def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent")
    order_info = state.get("order_info", {})
    if intent == "cancel_order" or order_info.get("user_cancelled"):
        return "cancel_node"
    if state.get("products") and parse_product_selection(state.get("last_user_message", "")) is not None:
        return "search_product_node"
    if intent in {"create_order", "confirm_order"}:
        return "search_product_node"
    if intent in {"smalltalk", "unknown"} and not has_active_order(state):
        return "assist_node"
    return "ask_node"


def route_after_search_product(state: AgentState) -> str:
    if state.get("product_selection_rejected"):
        return "ask_node"
    products = state.get("products") or []
    selected_product = get_selected_product(products, state.get("selected_product_code"), default_to_first=False)
    if products and not selected_product:
        return "ask_node"
    return "coverage_node"


def route_after_validation(state: AgentState) -> str:
    if state.get("missing_info"):
        return "ask_node"
    return "confirm_node"


def route_after_confirm(state: AgentState) -> str:
    order_info = state.get("order_info", {})
    if order_info.get("user_confirmed"):
        return "submit_node"
    return END
