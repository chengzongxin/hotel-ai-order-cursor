from workflow.products import build_product_search_output


PRODUCTS = [
    {"service_product_code": "A", "service_product_name": "Top1", "service_order_type": "托管维修"},
    {"service_product_code": "B", "service_product_name": "Top2", "service_order_type": "单次维修服务"},
]


def test_product_search_output_uses_top_product_service_type_and_preserves_valid_selection():
    result = build_product_search_output(
        tool_result={"status": "success", "data": {"products": PRODUCTS}},
        order_info={"product": "门锁", "fault": "打不开"},
        selected_product_code="B",
        last_user_message="301 门锁打不开",
    )

    assert result.search_status == "success"
    assert result.service_type == "托管维修"
    assert result.output["selected_product_code"] == "B"
    assert result.output["phase"] == "product_selection"
    assert result.output["order_info"]["urgency"] == "medium"


def test_product_search_output_clears_invalid_selection_without_results():
    result = build_product_search_output(
        tool_result={"status": "success", "data": {"products": []}},
        order_info={"product": "不存在的商品"},
        selected_product_code="B",
        last_user_message="不存在的商品坏了",
    )

    assert result.search_status == "no_match"
    assert result.service_type is None
    assert result.output["selected_product_code"] is None
    assert result.output["phase"] == "collecting"


def test_product_search_output_marks_tool_error():
    result = build_product_search_output(
        tool_result={"status": "error", "message": "boom", "data": {"products": PRODUCTS}},
        order_info={"product": "门锁", "fault": "打不开"},
        selected_product_code=None,
        last_user_message="门锁打不开",
    )

    assert result.search_status == "error"
    assert result.output["products"] == PRODUCTS
