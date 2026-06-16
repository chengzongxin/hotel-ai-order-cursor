"""OrderPreview API contract guardrails."""

from pathlib import Path

from workflow.preview import build_order_preview
from schemas.order_preview import OrderPreview

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ORDER_TYPES = PROJECT_ROOT / "frontend/src/types/order.ts"


def test_order_preview_schema_keeps_frontend_contract_fields():
    schema = OrderPreview.model_json_schema()
    properties = schema["properties"]

    expected_fields = {
        "phase",
        "service_type",
        "effective_service_type",
        "order_info",
        "products",
        "order_card",
        "coverage",
        "missing_info",
        "submission",
        "submitted_order",
    }

    assert expected_fields <= set(properties)


def test_frontend_order_preview_type_mentions_backend_contract_fields():
    source = FRONTEND_ORDER_TYPES.read_text(encoding="utf-8")

    for field in [
        "phase",
        "service_type",
        "effective_service_type",
        "order_info",
        "products",
        "order_card",
        "coverage",
        "missing_info",
        "submission",
        "submitted_order",
    ]:
        assert f"{field}?" in source or f"{field}:" in source


def test_graph_preview_builds_frontend_json_payload():
    payload = build_order_preview(
        {
            "phase": "pre_order",
            "service_type": "单次维修服务",
            "effective_service_type": "单次维修服务",
            "order_info": {"product": "空调", "fault": "不制冷", "expected_start_time": "明天上午"},
            "products": [
                {
                    "service_product_code": "AC_REPAIR",
                    "service_product_name": "空调(小修)",
                    "service_order_type": "单次维修服务",
                }
            ],
            "selected_product_code": "AC_REPAIR",
            "missing_info": [],
        }
    )

    assert payload is not None
    assert payload["phase"] == "pre_order"
    assert payload["products"]["selected_code"] == "AC_REPAIR"
    assert payload["service_type_display"] == "单次维修服务"
