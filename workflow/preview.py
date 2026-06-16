"""Order preview and legacy interrupt helpers."""

from __future__ import annotations

from workflow.products import get_selected_product
from workflow.text_parsing import format_service_type
from schemas.order_preview import build_order_preview_model


def get_interrupt_answer(result: dict[str, object]) -> str | None:
    """兼容旧 checkpoint 中可能残留的 interrupt 结果。"""

    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None

    first_interrupt = interrupts[0]
    payload = getattr(first_interrupt, "value", first_interrupt)
    if isinstance(payload, dict):
        question = payload.get("question")
        return str(question) if question else None

    return str(payload)


def build_order_preview(state: dict[str, object]) -> dict[str, object] | None:
    """Build the JSON payload consumed by the frontend order panel."""

    order_info = state.get("order_info") or {}
    products = state.get("products") or []
    service_type = state.get("service_type")
    if not service_type and products:
        selected = get_selected_product(products, state.get("selected_product_code"), default_to_first=False)
        service_type = selected.get("service_order_type") or None

    enriched_state = dict(state)
    enriched_state["service_type"] = service_type
    enriched_state["service_type_display"] = format_service_type(service_type, order_info)
    effective_service_type = state.get("effective_service_type")
    if effective_service_type:
        enriched_state["effective_service_type_display"] = format_service_type(
            str(effective_service_type),
            order_info,
        )
    preview = build_order_preview_model(enriched_state)
    if preview is None:
        return None
    return preview.model_dump(mode="json")
