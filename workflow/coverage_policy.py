"""Policy helpers for coverage-check state updates."""

from dataclasses import dataclass
from typing import Literal

from services.service_types import SERVICE_TYPE_MANAGED_REPAIR, resolve_order_submit_route
from workflow.order_defaults import normalize_order_defaults
from workflow.products import get_selected_product

CoverageAction = Literal["missing_product", "missing_service_type", "skip_check", "check"]


@dataclass(frozen=True)
class CoverageDecision:
    action: CoverageAction
    selected_product: dict[str, object]
    service_type: str | None
    output: dict[str, object] | None = None


def decide_coverage_action(state: dict[str, object]) -> CoverageDecision:
    selected_product = get_selected_product(
        state.get("products") or [],
        state.get("selected_product_code"),
        default_to_first=False,
    )
    if (state.get("products") or []) and not selected_product:
        return CoverageDecision(
            action="missing_product",
            selected_product={},
            service_type=None,
            output=empty_coverage_output(),
        )

    service_type = state.get("service_type") or selected_product.get("service_order_type")
    if not service_type:
        return CoverageDecision(
            action="missing_service_type",
            selected_product=selected_product,
            service_type=None,
            output=empty_coverage_output(),
        )

    if service_type != SERVICE_TYPE_MANAGED_REPAIR:
        return CoverageDecision(
            action="skip_check",
            selected_product=selected_product,
            service_type=str(service_type),
            output=build_non_managed_coverage_output(str(service_type)),
        )

    return CoverageDecision(
        action="check",
        selected_product=selected_product,
        service_type=str(service_type),
    )


def empty_coverage_output() -> dict[str, object]:
    return {
        "effective_service_type": None,
        "coverage_result": {},
        "order_submit_route": None,
        "step": "coverage_node",
    }


def build_non_managed_coverage_output(service_type: str) -> dict[str, object]:
    return {
        "effective_service_type": service_type,
        "coverage_result": {
            "checked": False,
            "covered": None,
            "reason": "非托管维修商品，无需校验维保卡范围",
            "effective_service_type": service_type,
        },
        "order_submit_route": resolve_order_submit_route(service_type),
        "step": "coverage_node",
    }


def build_checked_coverage_output(
    *,
    coverage_data: dict[str, object],
    fallback_service_type: str,
    order_info: dict[str, object],
    last_user_message: str,
) -> dict[str, object]:
    effective_service_type = str(coverage_data.get("effective_service_type") or fallback_service_type)
    normalized_order_info = normalize_order_defaults(
        service_type=effective_service_type,
        order_info=order_info,
        last_user_message=last_user_message,
    )
    return {
        "effective_service_type": effective_service_type,
        "coverage_result": coverage_data,
        "order_submit_route": resolve_order_submit_route(effective_service_type),
        "order_info": normalized_order_info,
        "step": "coverage_node",
    }
