"""search_product_node 选中商品保留逻辑测试。"""

import pytest

from graph.builder import search_product_node


@pytest.mark.asyncio
async def test_search_product_node_skips_research_on_confirm(monkeypatch):
    calls: list[dict] = []

    def fake_invoke(args):
        calls.append(args)
        return {"status": "success", "data": {"products": [], "query": args["query"], "count": 0}}

    monkeypatch.setattr(
        "graph.builder.asyncio.to_thread",
        lambda func, args: fake_invoke(args),
    )

    result = await search_product_node(
        {
            "intent": "confirm_order",
            "products": [{"service_product_code": "FWSP01537", "service_product_name": "门锁"}],
            "selected_product_code": "FWSP01537",
            "order_info": {"user_confirmed": True},
        }
    )

    assert calls == []
    assert result == {"step": "search_product_node"}


@pytest.mark.asyncio
async def test_search_product_node_preserves_selected_code(monkeypatch):
    tool_products = [
        {"service_product_code": "A", "service_product_name": "Top1", "service_order_type": "托管维修"},
        {"service_product_code": "B", "service_product_name": "Top2", "service_order_type": "托管维修"},
    ]

    async def fake_to_thread(func, arg):
        return {
            "status": "success",
            "data": {"products": tool_products, "query": arg["query"], "count": 2},
        }

    monkeypatch.setattr("graph.builder.asyncio.to_thread", fake_to_thread)

    result = await search_product_node(
        {
            "intent": "create_order",
            "order_info": {"product": "门锁", "fault": "打不开"},
            "last_user_message": "301 门锁打不开",
            "selected_product_code": "B",
        }
    )

    assert result["selected_product_code"] == "B"
    assert result["products"] == tool_products
