"""Order defaulting and normalization rules."""

from graph.expected_time import (
    infer_expected_start_time_from_message,
    merge_expected_start_time,
    normalize_expected_start_time_text,
)
from graph.order_fields import DEFAULT_URGENCY, normalize_goods_arrival_status
from graph.constants import VALID_MANAGED_REPAIR_SCOPES
from graph.text_parsing import (
    extract_room_number,
    is_guest_room_text,
    is_public_area_text,
)


def normalize_order_defaults(
    service_type: str | None,
    order_info: dict[str, object],
    last_user_message: str = "",
) -> dict[str, object]:
    normalized = dict(order_info)

    if service_type in {"托管维修", "单次维修服务"} and not normalized.get("urgency"):
        normalized["urgency"] = DEFAULT_URGENCY

    if normalized.get("goods_arrival_status"):
        normalized_status = normalize_goods_arrival_status(str(normalized.get("goods_arrival_status")))
        if normalized_status:
            normalized["goods_arrival_status"] = normalized_status
        else:
            normalized.pop("goods_arrival_status", None)

    if service_type == "托管维修":
        if not normalized.get("room_number"):
            inferred_room_number = extract_room_number(last_user_message)
            if inferred_room_number:
                normalized["room_number"] = inferred_room_number

        room_number = str(normalized.get("room_number") or "").strip()
        area = str(normalized.get("area") or "")
        scope = normalized.get("managed_repair_scope")
        if room_number and room_number != "/":
            normalized["managed_repair_scope"] = "客房"
            normalized["area"] = "客房"
        elif scope == "客房" or is_guest_room_text(area) or is_guest_room_text(last_user_message):
            normalized["managed_repair_scope"] = "客房"
            normalized["area"] = "客房"
        elif scope == "公区" or is_public_area_text(area) or is_public_area_text(last_user_message):
            normalized["managed_repair_scope"] = "公区"
            normalized["area"] = "公区"
            normalized["room_number"] = "/"
        elif scope not in VALID_MANAGED_REPAIR_SCOPES:
            normalized.pop("managed_repair_scope", None)

    inferred_time = infer_expected_start_time_from_message(last_user_message)
    existing_time = normalize_expected_start_time_text(
        str(normalized.get("expected_start_time") or "") or None
    )
    merged_time = merge_expected_start_time(existing_time, inferred_time)
    if merged_time:
        normalized["expected_start_time"] = merged_time

    return normalized
