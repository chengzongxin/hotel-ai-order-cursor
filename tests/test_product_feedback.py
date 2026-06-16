from workflow.products import build_product_search_feedback_from_state


def test_product_feedback_from_state_uses_effective_service_type():
    feedback = build_product_search_feedback_from_state(
        {
            "products": [
                {
                    "service_product_code": "A",
                    "service_product_name": "空调维修",
                    "service_order_type": "托管维修",
                }
            ],
            "selected_product_code": "A",
            "service_type": "托管维修",
            "effective_service_type": "单次维修服务",
            "order_info": {"fault": "不制冷"},
        }
    )

    assert feedback == "根据您描述的【不制冷】，已为您匹配到【空调维修】，服务类型为【单次维修服务】。"


def test_product_feedback_from_state_returns_none_without_selected_product():
    assert build_product_search_feedback_from_state({"products": [], "selected_product_code": None}) is None
