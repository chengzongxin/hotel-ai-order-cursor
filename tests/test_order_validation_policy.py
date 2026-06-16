from workflow.order_validation_policy import (
    build_prepare_order_context_output,
    build_validate_order_output,
)


PRODUCTS = [
    {"service_product_code": "A", "service_product_name": "空调维修", "service_order_type": "单次维修服务"},
]


def test_prepare_order_context_output_requires_selected_product():
    result = build_prepare_order_context_output(
        state={"products": PRODUCTS, "selected_product_code": None},
        order_context={"contacts": "张三", "phone": "13800000000"},
    )

    assert result.service_type is None
    assert result.output == {
        "order_context": {},
        "order_card_fields": [],
        "step": "prepare_order_context_node",
    }


def test_prepare_order_context_output_builds_card_fields():
    result = build_prepare_order_context_output(
        state={
            "products": PRODUCTS,
            "selected_product_code": "A",
            "service_type": "单次维修服务",
            "order_info": {"product": "空调", "fault": "不制冷", "expected_start_time": "明天上午"},
        },
        order_context={"contacts": "张三", "phone": "13800000000"},
    )

    assert result.service_type == "单次维修服务"
    assert result.output["phase"] == "pre_order"
    assert [field["key"] for field in result.output["order_card_fields"]] == [
        "expected_time",
        "remark",
        "product_quantity",
        "contacts",
        "phone",
        "total_fee",
    ]


def test_validate_order_output_requires_product_selection_first():
    result = build_validate_order_output(
        {
            "products": PRODUCTS,
            "selected_product_code": None,
            "retry_count": 2,
        }
    )

    assert result.output["missing_info"] == ["selected_product"]
    assert result.output["retry_count"] == 2
    assert result.output["phase"] == "product_selection"


def test_validate_order_output_increments_retry_for_missing_time():
    result = build_validate_order_output(
        {
            "products": PRODUCTS,
            "selected_product_code": "A",
            "service_type": "单次维修服务",
            "order_info": {"product": "空调", "fault": "不制冷"},
            "order_card_fields": [],
            "retry_count": 0,
        }
    )

    assert result.required_fields == ["product", "fault", "expected_start_time"]
    assert result.output["missing_info"] == ["expected_start_time"]
    assert result.output["retry_count"] == 1
    assert result.output["phase"] == "pre_order"


def test_validate_order_output_drops_invalid_expected_start_time():
    result = build_validate_order_output(
        {
            "service_type": "单次测量",
            "order_info": {"product": "窗帘", "expected_start_time": "1208"},
            "retry_count": 0,
        }
    )

    assert "expected_start_time" not in result.output["order_info"]
    assert result.output["missing_info"] == ["expected_start_time"]
