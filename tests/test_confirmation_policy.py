from workflow.confirmation_policy import PRE_ORDER_CARD_CONFIRMATION_TEXT, build_confirmation_text


def test_confirmation_text_for_product_card():
    text = build_confirmation_text(
        {
            "products": [{"service_product_code": "A", "service_product_name": "空调维修"}],
            "selected_product_code": "A",
            "order_info": {"product": "空调", "fault": "不制冷"},
        }
    )

    assert text == PRE_ORDER_CARD_CONFIRMATION_TEXT


def test_confirmation_text_includes_product_feedback():
    text = build_confirmation_text(
        {
            "products": [{"service_product_code": "A", "service_product_name": "空调维修"}],
            "selected_product_code": "A",
            "order_info": {"product": "空调", "fault": "不制冷"},
        },
        product_search_feedback="已匹配到标准商品。",
    )

    assert text.startswith("已匹配到标准商品。\n\n")
    assert text.endswith(PRE_ORDER_CARD_CONFIRMATION_TEXT)


def test_confirmation_text_prefixes_uncovered_reason():
    text = build_confirmation_text(
        {
            "products": [{"service_product_code": "A", "service_product_name": "空调维修"}],
            "selected_product_code": "A",
            "coverage_result": {"checked": True, "covered": False, "reason": "不在维保范围"},
            "order_info": {"product": "空调", "fault": "不制冷"},
        },
        product_search_feedback="已匹配到标准商品。",
    )

    assert text.startswith("不在维保范围\n已匹配到标准商品。")


def test_confirmation_text_without_products_uses_prompt_template():
    text = build_confirmation_text(
        {
            "service_type": "单次维修服务",
            "order_info": {
                "room_number": "301",
                "product": "空调",
                "fault": "不制冷",
                "area": "客房",
                "urgency": "medium",
                "expected_start_time": "明天上午",
            },
        }
    )

    assert "请确认订单信息" in text
    assert "订单类型：单次维修服务" in text
    assert "商品/设备：空调" in text
    assert "紧急度：普通" in text
