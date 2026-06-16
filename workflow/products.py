from dataclasses import dataclass
from typing import Any
from typing import Literal

from workflow.constants import PHASE_COLLECTING, PHASE_PRE_ORDER, PHASE_PRODUCT_SELECTION
from workflow.order_defaults import normalize_order_defaults
from workflow.text_parsing import parse_product_selection

VALID_MANAGED_REPAIR_SCOPES = {"客房", "公区"}
LOW_CONFIDENCE_SCORE = 0.45
AMBIGUOUS_SCORE_DELTA = 0.05

ProductSelectionAction = Literal["none", "reject", "select", "skip_confirm"]


@dataclass(frozen=True)
class ProductSelectionDecision:
    action: ProductSelectionAction
    output: dict[str, object]
    selection: int | None = None


@dataclass(frozen=True)
class ProductSearchPolicyResult:
    output: dict[str, object]
    search_status: str
    service_type: str | None


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
    *,
    default_to_first: bool = True,
) -> str | None:
    """返回有效的选中编码；未指定时默认 Top1。"""
    if selected_code and find_product_by_code(products, selected_code):
        return selected_code.strip()
    if default_to_first and products:
        return str(products[0].get("service_product_code") or "").strip() or None
    return None


def get_selected_product(
    products: list[dict[str, Any]],
    selected_code: str | None,
    *,
    default_to_first: bool = True,
) -> dict[str, Any]:
    code = resolve_selected_code(products, selected_code, default_to_first=default_to_first)
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


def apply_product_selection_policy(state: dict[str, object]) -> ProductSelectionDecision:
    existing_products = state.get("products") or []
    last_msg = str(state.get("last_user_message") or "")
    selection = parse_product_selection(last_msg)

    if existing_products and selection == 0:
        return ProductSelectionDecision(
            action="reject",
            selection=selection,
            output={
                "products": [],
                "selected_product_code": None,
                "service_type": None,
                "effective_service_type": None,
                "coverage_result": {},
                "order_submit_route": None,
                "order_card_fields": [],
                "product_selection_rejected": True,
                "missing_info": [],
                "phase": PHASE_COLLECTING,
                "step": "search_product_node",
            },
        )

    if existing_products and selection in {1, 2, 3}:
        selected_product = existing_products[int(selection) - 1] if len(existing_products) >= int(selection) else {}
        if selected_product:
            service_type = selected_product.get("service_order_type") or state.get("service_type")
            normalized_order_info = normalize_order_defaults(
                service_type=service_type,
                order_info=state.get("order_info", {}),
                last_user_message=last_msg,
            )
            return ProductSelectionDecision(
                action="select",
                selection=selection,
                output={
                    "selected_product_code": selected_product.get("service_product_code"),
                    "service_type": service_type,
                    "order_info": normalized_order_info,
                    "product_selection_rejected": False,
                    "phase": PHASE_PRE_ORDER,
                    "step": "search_product_node",
                },
            )

    if state.get("intent") == "confirm_order" and existing_products:
        return ProductSelectionDecision(
            action="skip_confirm",
            selection=selection,
            output={"step": "search_product_node"},
        )

    return ProductSelectionDecision(action="none", selection=selection, output={})


def build_product_search_output(
    *,
    tool_result: dict[str, object],
    order_info: dict[str, object],
    selected_product_code: str | None,
    last_user_message: str,
) -> ProductSearchPolicyResult:
    data = tool_result.get("data", {})
    data = data if isinstance(data, dict) else {}
    products = data.get("products") or []
    top_product = get_selected_product(products, None, default_to_first=True)
    search_status = "success" if products else "no_match"
    if tool_result.get("status") != "success":
        search_status = "error"

    service_type = top_product.get("service_order_type") or None
    normalized_order_info = normalize_order_defaults(
        service_type=service_type,
        order_info=order_info,
        last_user_message=last_user_message,
    )
    return ProductSearchPolicyResult(
        search_status=search_status,
        service_type=service_type,
        output={
            "products": products,
            "selected_product_code": resolve_selected_code(
                products,
                selected_product_code,
                default_to_first=False,
            ),
            "service_type": service_type,
            "order_info": normalized_order_info,
            "product_selection_rejected": False,
            "order_card_fields": [],
            "phase": PHASE_PRODUCT_SELECTION if products else PHASE_COLLECTING,
            "step": "search_product_node",
        },
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


def build_product_search_feedback_from_state(state: dict[str, Any]) -> str | None:
    products = state.get("products") or []
    selected_product = get_selected_product(
        products,
        state.get("selected_product_code"),
        default_to_first=False,
    )
    if not selected_product:
        return None
    service_type = (
        state.get("effective_service_type")
        or state.get("service_type")
        or selected_product.get("service_order_type")
    )
    return build_product_search_feedback(
        order_info=state.get("order_info") or {},
        selected_product=selected_product,
        service_type=service_type,
    )


def _score(product: dict[str, Any]) -> float | None:
    value = product.get("score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_product_selection_feedback(products: list[dict[str, Any]], search_query: str) -> str | None:
    """给前端展示商品候选的选择原因。

    商品推荐阶段默认不自动选 Top1；当分数偏低或候选接近时，文案会提醒用户确认，
    避免低置信匹配直接进入下单。
    """

    if not search_query:
        return None
    if not products:
        return "暂时没有匹配到可下单商品，请换一种说法描述商品和故障。"

    top_score = _score(products[0])
    second_score = _score(products[1]) if len(products) > 1 else None
    if top_score is not None and top_score < LOW_CONFIDENCE_SCORE:
        return "匹配置信度偏低，请从下方候选中选择最接近的服务商品；如果都不符合，请选择“以上都不符合”。"
    if top_score is not None and second_score is not None and abs(top_score - second_score) <= AMBIGUOUS_SCORE_DELTA:
        return "找到多个相近服务商品，请先确认要下单的具体商品。"
    return "已找到可下单的服务商品，请先选择一个商品后再生成预下单卡片。"


def derive_product_section_fields(state: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """从 state 推导 API products 区块的 status / query / feedback。"""
    products = state.get("products") or []
    order_info = state.get("order_info") or {}
    last_user_message = state.get("last_user_message") or ""
    search_query = build_product_search_query(order_info, last_user_message)
    status = infer_product_search_status(products, search_query)

    selected = get_selected_product(products, state.get("selected_product_code"), default_to_first=False)
    feedback = (
        build_product_search_feedback_from_state(state)
        if selected
        else build_product_selection_feedback(products, search_query)
    )
    return status, search_query or None, feedback
