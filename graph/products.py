from typing import Any

VALID_MANAGED_REPAIR_SCOPES = {"客房", "公区"}


def find_product_by_code(
    products: list[dict[str, Any]],
    product_code: str,
) -> dict[str, Any] | None:
    normalized_code = product_code.strip()
    if not normalized_code:
        return None
    for product in products:
        if str(product.get("service_product_code") or "").strip() == normalized_code:
            return product
    return None


def resolve_selected_code(
    products: list[dict[str, Any]],
    selected_code: str | None,
) -> str | None:
    """返回有效的选中编码；未指定时默认 Top1。"""
    if selected_code and find_product_by_code(products, selected_code):
        return selected_code.strip()
    if products:
        return str(products[0].get("service_product_code") or "").strip() or None
    return None


def get_selected_product(
    products: list[dict[str, Any]],
    selected_code: str | None,
) -> dict[str, Any]:
    code = resolve_selected_code(products, selected_code)
    if not code:
        return {}
    return find_product_by_code(products, code) or {}


def format_service_type_display(
    service_type: str | None,
    order_info: dict[str, Any],
) -> str | None:
    if service_type != "托管维修":
        return service_type
    scope = order_info.get("managed_repair_scope")
    if scope in VALID_MANAGED_REPAIR_SCOPES:
        return f"托管维修（{scope}）"
    return service_type


def build_product_search_query(
    order_info: dict[str, Any],
    last_user_message: str = "",
) -> str:
    product = order_info.get("product")
    fault = order_info.get("fault")
    install_hint = "安装" if not fault and "安装" in last_user_message else ""
    return " ".join(
        str(value)
        for value in [product, fault, install_hint]
        if value
    )


def infer_product_search_status(
    products: list[dict[str, Any]],
    search_query: str,
) -> str:
    if products:
        return "success"
    if not search_query:
        return "skipped"
    return "no_match"


def build_product_search_feedback(
    order_info: dict[str, Any],
    selected_product: dict[str, Any],
    service_type: str | None,
) -> str | None:
    product_name = selected_product.get("service_product_name")
    if not product_name:
        return None

    described_issue = order_info.get("fault") or order_info.get("product") or "需求"
    service_type_text = format_service_type_display(service_type, order_info) or "待确认"
    return (
        f"根据您描述的【{described_issue}】，已为您匹配到【{product_name}】，"
        f"服务类型为【{service_type_text}】。"
    )


def derive_product_section_fields(state: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """从 state 推导 API products 区块的 status / query / feedback。"""
    products = state.get("products") or []
    order_info = state.get("order_info") or {}
    last_user_message = state.get("last_user_message") or ""
    search_query = build_product_search_query(order_info, last_user_message)
    status = infer_product_search_status(products, search_query)

    selected = get_selected_product(products, state.get("selected_product_code"))
    service_type = state.get("service_type") or selected.get("service_order_type")
    feedback = (
        build_product_search_feedback(order_info, selected, service_type)
        if selected
        else None
    )
    return status, search_query or None, feedback
