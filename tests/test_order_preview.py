"""order_preview 结构单元测试。"""

from graph.products import get_selected_product, resolve_selected_code
from schemas.order_preview import build_order_preview_model, build_product_section


def test_build_product_section_from_products_list():
    products = [
        {
            "service_product_code": "FWSP01537",
            "service_product_name": "门锁损坏（困客人）",
            "service_order_type": "托管维修",
            "score": 0.6756,
            "price": "48.08",
        },
        {
            "service_product_code": "FWSP01423",
            "service_product_name": "门锁(小修)",
            "service_order_type": "托管维修",
            "score": 0.6397,
            "price": "8.02",
        },
    ]

    section = build_product_section(
        products=products,
        selected_code="FWSP01537",
        search_status="success",
        search_query="门锁 打不开",
        search_feedback="已匹配到门锁损坏（困客人）",
    )

    assert section.status == "success"
    assert section.selected_code == "FWSP01537"
    assert len(section.items) == 2
    assert section.items[0].is_selected is True
    assert section.items[1].is_selected is False


def test_resolve_selected_code_defaults_to_top1():
    products = [{"service_product_code": "FWSP01537", "service_product_name": "A"}]
    assert resolve_selected_code(products, None) == "FWSP01537"
    assert get_selected_product(products, None)["service_product_name"] == "A"


def test_build_order_preview_model_uses_single_products_field():
    preview = build_order_preview_model(
        {
            "service_type": "托管维修",
            "service_type_display": "托管维修（客房）",
            "status": "confirming",
            "order_info": {"room_number": "301", "product": "门锁", "fault": "打不开"},
            "products": [
                {
                    "service_product_code": "FWSP01537",
                    "service_product_name": "门锁损坏（困客人）",
                    "service_order_type": "托管维修",
                }
            ],
            "selected_product_code": "FWSP01537",
            "missing_info": [],
        }
    )

    assert preview is not None
    payload = preview.model_dump(mode="json")
    assert payload["products"]["items"][0]["code"] == "FWSP01537"
    assert payload["products"]["status"] == "success"
    assert payload["products"]["query"] == "门锁 打不开"
    assert "门锁损坏" in (payload["products"]["feedback"] or "")
