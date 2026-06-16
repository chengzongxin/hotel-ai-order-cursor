from workflow.coverage_policy import (
    build_checked_coverage_output,
    decide_coverage_action,
)


PRODUCTS = [
    {"service_product_code": "A", "service_product_name": "空调维修", "service_order_type": "托管维修"},
]


def test_decide_coverage_action_requires_selected_product_when_products_exist():
    decision = decide_coverage_action(
        {
            "products": PRODUCTS,
            "selected_product_code": None,
        }
    )

    assert decision.action == "missing_product"
    assert decision.output == {
        "effective_service_type": None,
        "coverage_result": {},
        "order_submit_route": None,
        "step": "coverage_node",
    }


def test_decide_coverage_action_skips_non_managed_service():
    decision = decide_coverage_action(
        {
            "products": [{"service_product_code": "B", "service_order_type": "单次安装"}],
            "selected_product_code": "B",
        }
    )

    assert decision.action == "skip_check"
    assert decision.service_type == "单次安装"
    assert decision.output["effective_service_type"] == "单次安装"
    assert decision.output["order_submit_route"] == "single_install"


def test_decide_coverage_action_checks_managed_repair():
    decision = decide_coverage_action(
        {
            "products": PRODUCTS,
            "selected_product_code": "A",
        }
    )

    assert decision.action == "check"
    assert decision.service_type == "托管维修"
    assert decision.selected_product["service_product_code"] == "A"
    assert decision.output is None


def test_build_checked_coverage_output_normalizes_effective_service_type():
    output = build_checked_coverage_output(
        coverage_data={
            "checked": True,
            "covered": False,
            "reason": "不在维保范围",
            "effective_service_type": "单次维修服务",
        },
        fallback_service_type="托管维修",
        order_info={"product": "空调", "fault": "不制冷"},
        last_user_message="1208 空调不制冷",
    )

    assert output["effective_service_type"] == "单次维修服务"
    assert output["order_submit_route"] == "single_repair"
    assert output["order_info"]["urgency"] == "medium"
