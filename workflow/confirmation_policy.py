"""Confirmation text policy for pre-order review turns."""

from workflow.order_fields import DEFAULT_URGENCY
from workflow.products import get_selected_product
from workflow.prompts import render_prompt
from workflow.submission import get_effective_service_type
from workflow.text_parsing import format_service_type, format_urgency


PRE_ORDER_CARD_CONFIRMATION_TEXT = (
    "好的，收到。信息已齐全，已为您生成预下单页面，如需修改，"
    "请直接点击修改下单信息；如确认无误，请对我说”确认“，"
    "或手动点击下方的”确认“按钮。"
)


def build_confirmation_text(
    state: dict[str, object],
    *,
    product_search_feedback: str | None = None,
) -> str:
    order_info = state.get("order_info") or {}
    products = state.get("products") or []
    if products:
        confirmation_text = PRE_ORDER_CARD_CONFIRMATION_TEXT
        if product_search_feedback:
            confirmation_text = f"{product_search_feedback}\n\n{confirmation_text}"
        coverage_result = state.get("coverage_result") or {}
        if coverage_result.get("checked") and coverage_result.get("covered") is False:
            confirmation_text = f"{coverage_result.get('reason')}\n{confirmation_text}"
        return confirmation_text

    service_type = get_effective_service_type(state)
    selected_product = get_selected_product(
        products,
        state.get("selected_product_code"),
        default_to_first=False,
    )
    return render_prompt(
        "confirm/confirm.md",
        service_type=format_service_type(service_type, order_info),
        room_number=order_info.get("room_number"),
        product=order_info.get("product"),
        fault=order_info.get("fault"),
        area=order_info.get("area"),
        urgency=format_urgency(order_info.get("urgency") or DEFAULT_URGENCY),
        expected_start_time=order_info.get("expected_start_time") or "无",
        goods_arrival_status=order_info.get("goods_arrival_status") or "无",
        product_name=selected_product.get("service_product_name") or "未匹配到标准商品",
        product_code=selected_product.get("service_product_code") or "无",
    )
