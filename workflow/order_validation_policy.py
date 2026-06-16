"""Policy helpers for preparing and validating pre-order state."""

from dataclasses import dataclass

from workflow.constants import PHASE_PRE_ORDER, PHASE_PRODUCT_SELECTION
from workflow.expected_time import looks_like_expected_start_time
from workflow.order_defaults import normalize_order_defaults
from workflow.order_fields import build_order_card_fields, collect_missing_order_info, get_required_order_fields
from workflow.products import get_selected_product
from workflow.submission import get_effective_service_type


@dataclass(frozen=True)
class PrepareOrderContextResult:
    output: dict[str, object]
    service_type: str | None


@dataclass(frozen=True)
class ValidateOrderResult:
    output: dict[str, object]
    service_type: str | None
    required_fields: list[str]


def build_prepare_order_context_output(
    *,
    state: dict[str, object],
    order_context: dict[str, object],
) -> PrepareOrderContextResult:
    selected_product = get_selected_product(
        state.get("products") or [],
        state.get("selected_product_code"),
        default_to_first=False,
    )
    if not selected_product:
        return PrepareOrderContextResult(
            service_type=None,
            output={
                "order_context": {},
                "order_card_fields": [],
                "step": "prepare_order_context_node",
            },
        )

    service_type = get_effective_service_type(state)
    order_card_fields = build_order_card_fields(
        service_type=service_type,
        order_info=state.get("order_info", {}),
        order_context=order_context,
    )
    return PrepareOrderContextResult(
        service_type=service_type,
        output={
            "order_context": order_context,
            "order_card_fields": order_card_fields,
            "phase": PHASE_PRE_ORDER,
            "step": "prepare_order_context_node",
        },
    )


def build_validate_order_output(state: dict[str, object]) -> ValidateOrderResult:
    products = state.get("products") or []
    selected_product = get_selected_product(products, state.get("selected_product_code"), default_to_first=False)
    if products and not selected_product:
        return ValidateOrderResult(
            service_type=None,
            required_fields=[],
            output={
                "missing_info": ["selected_product"],
                "retry_count": state.get("retry_count", 0),
                "phase": PHASE_PRODUCT_SELECTION,
                "step": "validate_order_node",
            },
        )

    service_type = get_effective_service_type(state)
    order_info = normalize_order_defaults(
        service_type=service_type,
        order_info=state.get("order_info", {}),
        last_user_message=state.get("last_user_message", ""),
    )
    required_fields = get_required_order_fields(service_type, order_info)
    missing_info = collect_missing_order_info(
        service_type,
        order_info,
        state.get("order_card_fields") or [],
    )
    if "expected_start_time" in required_fields and order_info.get("expected_start_time"):
        if not looks_like_expected_start_time(str(order_info["expected_start_time"])):
            order_info.pop("expected_start_time", None)
            if "expected_start_time" not in missing_info:
                missing_info.append("expected_start_time")

    retry_count = state.get("retry_count", 0)
    if missing_info:
        retry_count += 1

    return ValidateOrderResult(
        service_type=service_type,
        required_fields=required_fields,
        output={
            "missing_info": missing_info,
            "order_info": order_info,
            "retry_count": retry_count,
            "phase": PHASE_PRE_ORDER,
            "step": "validate_order_node",
        },
    )
