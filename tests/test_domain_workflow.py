from domain.events import ProductSelected, apply_order_event
from domain.validation import missing_fields_for_order, validate_order_ready
from services.order_workflow import OrderWorkflowService


def test_validation_rules_delegate_service_required_fields():
    ready, missing = validate_order_ready(
        "单次维修服务",
        {"product": "空调", "fault": "不制冷"},
    )

    assert ready is False
    assert missing == ["expected_start_time"]
    assert missing_fields_for_order("单次测量", {"product": "窗帘"}) == ["expected_start_time"]


def test_order_event_reducer_projection_appends_event():
    state = {"phase": "collecting"}
    projected = apply_order_event(
        state,
        ProductSelected(payload={"selected_product_code": "A", "phase": "pre_order"}),
    )

    assert projected["selected_product_code"] == "A"
    assert projected["phase"] == "pre_order"
    assert projected["last_order_event"] == "ProductSelected"
    assert projected["order_events"][0]["type"] == "ProductSelected"


def test_order_workflow_service_uses_default_dependencies():
    service = OrderWorkflowService()

    update = service.match_products(
        state={
            "order_info": {"room_number": "301", "product": "门锁", "fault": "打不开"},
            "last_user_message": "301 门锁打不开",
        },
        products=[
            {
                "service_product_code": "A",
                "service_product_name": "门锁",
                "service_order_type": "托管维修",
            }
        ],
        service_type="托管维修",
    )

    assert update["phase"] == "product_selection"
    assert update["service_type"] == "托管维修"
    assert update["order_info"]["managed_repair_scope"] == "客房"
    assert update["last_order_event"] == "ProductMatched"
