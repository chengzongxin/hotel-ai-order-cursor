"""Backward-compatible imports for order field policy.

The business rules live in `services.order_policy`; this module remains as a
stable import path for workflow nodes and existing tests.
"""

from services.order_policy import (
    DEFAULT_PRODUCT_QUANTITY,
    DEFAULT_URGENCY,
    GOODS_ARRIVAL_OPTIONS,
    PUBLIC_AREA_KEYWORDS,
    URGENCY_OPTIONS,
    VALID_GOODS_ARRIVAL_STATUSES,
    build_order_card_fields,
    collect_missing_order_info,
    get_missing_fields_from_card,
    get_required_order_fields,
    is_public_area_text,
    normalize_goods_arrival_status,
    normalize_order_card_update,
    normalize_product_quantity,
)

__all__ = [
    "DEFAULT_PRODUCT_QUANTITY",
    "DEFAULT_URGENCY",
    "GOODS_ARRIVAL_OPTIONS",
    "PUBLIC_AREA_KEYWORDS",
    "URGENCY_OPTIONS",
    "VALID_GOODS_ARRIVAL_STATUSES",
    "build_order_card_fields",
    "collect_missing_order_info",
    "get_missing_fields_from_card",
    "get_required_order_fields",
    "is_public_area_text",
    "normalize_goods_arrival_status",
    "normalize_order_card_update",
    "normalize_product_quantity",
]
