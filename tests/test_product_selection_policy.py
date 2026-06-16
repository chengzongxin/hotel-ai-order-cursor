from workflow.products import apply_product_selection_policy


PRODUCTS = [
    {"service_product_code": "A", "service_product_name": "Top1", "service_order_type": "单次维修服务"},
    {"service_product_code": "B", "service_product_name": "Top2", "service_order_type": "单次安装"},
]


def test_product_selection_policy_rejects_existing_recommendations():
    decision = apply_product_selection_policy(
        {
            "products": PRODUCTS,
            "last_user_message": "以上都不符合",
        }
    )

    assert decision.action == "reject"
    assert decision.output["products"] == []
    assert decision.output["product_selection_rejected"] is True
    assert decision.output["phase"] == "collecting"


def test_product_selection_policy_selects_numbered_product():
    decision = apply_product_selection_policy(
        {
            "products": PRODUCTS,
            "last_user_message": "第二个",
            "order_info": {"product": "洗衣机"},
        }
    )

    assert decision.action == "select"
    assert decision.selection == 2
    assert decision.output["selected_product_code"] == "B"
    assert decision.output["service_type"] == "单次安装"
    assert decision.output["phase"] == "pre_order"


def test_product_selection_policy_skips_research_on_confirm_with_products():
    decision = apply_product_selection_policy(
        {
            "intent": "confirm_order",
            "products": PRODUCTS,
            "last_user_message": "确认",
        }
    )

    assert decision.action == "skip_confirm"
    assert decision.output == {"step": "search_product_node"}


def test_product_selection_policy_returns_none_without_existing_products():
    decision = apply_product_selection_policy(
        {
            "intent": "create_order",
            "last_user_message": "1208 空调不制冷",
            "order_info": {"product": "空调", "fault": "不制冷"},
        }
    )

    assert decision.action == "none"
    assert decision.output == {}
