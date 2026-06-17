"""Order validation rules by service type."""

from typing import Any

from graph.order_fields import (
    collect_missing_order_info,
    get_required_order_fields,
)


def required_fields_for_service(
    service_type: str | None,
    order_info: dict[str, Any],
) -> list[str]:
    return get_required_order_fields(service_type, order_info)


def missing_fields_for_order(
    service_type: str | None,
    order_info: dict[str, Any],
    order_card_fields: list[dict[str, Any]] | None = None,
) -> list[str]:
    return collect_missing_order_info(service_type, order_info, order_card_fields)


def validate_order_ready(
    service_type: str | None,
    order_info: dict[str, Any],
    order_card_fields: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str]]:
    missing = missing_fields_for_order(service_type, order_info, order_card_fields)
    return not missing, missing

