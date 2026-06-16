"""Pure policy helpers for applying intent extraction results to graph state."""

from dataclasses import dataclass
from typing import Protocol

from workflow.constants import PHASE_IDLE, PHASE_SUBMITTED, VALID_MANAGED_REPAIR_SCOPES
from workflow.expected_time import merge_expected_start_time, normalize_expected_start_time_text
from workflow.messages import format_messages, get_last_human_message
from workflow.order_fields import normalize_goods_arrival_status


class IntentExtractionLike(Protocol):
    room_number: str | None
    product: str | None
    fault: str | None
    area: str | None
    urgency: str | None
    expected_start_time: str | None
    goods_arrival_status: str | None
    contacts: str | None
    phone: str | None
    managed_repair_scope: str | None
    user_confirmed: bool


@dataclass(frozen=True)
class IntentPolicyResult:
    phase: str | None
    order_info: dict[str, object]


def get_extractor_history(state: dict[str, object]) -> str:
    """提交后的新订单默认只看最新输入，避免已提交订单被重新抽取。"""

    if state.get("last_order") and not state.get("order_info"):
        return f"human: {get_last_human_message(state.get('messages', []))}"
    return format_messages(state.get("messages", []))


def resolve_phase_after_intent(
    intent: str,
    current_phase: str | None,
    has_active_order: bool,
) -> str | None:
    if intent in {"create_order", "confirm_order"}:
        return "collecting"
    if intent in {"smalltalk", "unknown"} and not has_active_order:
        return PHASE_IDLE if current_phase == PHASE_SUBMITTED else current_phase or PHASE_IDLE
    return current_phase


def build_detected_order_fields(
    extraction: IntentExtractionLike,
    user_cancelled: bool,
) -> dict[str, object | None]:
    return {
        "room_number": extraction.room_number,
        "product": extraction.product,
        "fault": extraction.fault,
        "area": extraction.area,
        "urgency": extraction.urgency,
        "expected_start_time": extraction.expected_start_time,
        "goods_arrival_status": normalize_goods_arrival_status(extraction.goods_arrival_status),
        "contacts": extraction.contacts,
        "phone": extraction.phone,
        "managed_repair_scope": extraction.managed_repair_scope
        if extraction.managed_repair_scope in VALID_MANAGED_REPAIR_SCOPES
        else None,
        "user_confirmed": extraction.user_confirmed,
        "user_cancelled": user_cancelled,
    }


def merge_intent_order_info(
    intent: str,
    existing_order_info: dict[str, object],
    detected_fields: dict[str, object | None],
    has_active_order: bool,
    inferred_expected_start_time: str | None,
) -> dict[str, object]:
    if intent in {"smalltalk", "unknown", "cancel_order"}:
        order_info = dict(existing_order_info) if has_active_order else {}
        if intent == "cancel_order":
            order_info.update({"user_confirmed": False, "user_cancelled": True})
        return order_info

    cleaned_existing = dict(existing_order_info)
    if detected_fields.get("managed_repair_scope") == "公区":
        cleaned_existing.pop("room_number", None)
        cleaned_existing.pop("area", None)
        cleaned_existing.pop("managed_repair_scope", None)
    elif detected_fields.get("room_number") or detected_fields.get("managed_repair_scope") == "客房":
        cleaned_existing.pop("managed_repair_scope", None)
        cleaned_existing.pop("area", None)

    order_info = {
        **cleaned_existing,
        **{
            key: value
            for key, value in detected_fields.items()
            if value is not None and key != "expected_start_time"
        },
    }
    merged_expected_time = merge_expected_start_time(
        cleaned_existing.get("expected_start_time"),
        normalize_expected_start_time_text(detected_fields.get("expected_start_time")),
    )
    merged_expected_time = merge_expected_start_time(merged_expected_time, inferred_expected_start_time)
    if merged_expected_time:
        order_info["expected_start_time"] = merged_expected_time
    order_info["user_confirmed"] = bool(detected_fields.get("user_confirmed"))
    order_info["user_cancelled"] = bool(detected_fields.get("user_cancelled"))
    return order_info


def apply_intent_policy(
    intent: str,
    current_phase: str | None,
    has_active_order: bool,
    existing_order_info: dict[str, object],
    detected_fields: dict[str, object | None],
    inferred_expected_start_time: str | None,
) -> IntentPolicyResult:
    return IntentPolicyResult(
        phase=resolve_phase_after_intent(intent, current_phase, has_active_order),
        order_info=merge_intent_order_info(
            intent=intent,
            existing_order_info=existing_order_info,
            detected_fields=detected_fields,
            has_active_order=has_active_order,
            inferred_expected_start_time=inferred_expected_start_time,
        ),
    )
