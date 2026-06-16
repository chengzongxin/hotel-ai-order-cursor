"""search_product_tool 返回结构测试。"""

from tools.product_search import search_product_tool


def test_search_product_tool_returns_unified_products(monkeypatch):
    fake_products = [
        {
            "service_product_code": "FWSP01537",
            "service_product_name": "门锁损坏（困客人）",
            "service_order_type": "托管维修",
            "score": 0.9,
        },
        {
            "service_product_code": "FWSP01423",
            "service_product_name": "门锁(小修)",
            "service_order_type": "托管维修",
            "score": 0.8,
        },
    ]

    class FakeStore:
        def search(self, **kwargs):
            return fake_products

    monkeypatch.setattr("tools.product_search.get_product_store", lambda: FakeStore())

    result = search_product_tool.invoke({"query": "门锁 打不开", "top_k": 3})
    data = result["data"]

    assert "best_match" not in data
    assert "candidates" not in data
    assert data["products"] == fake_products
    assert data["count"] == 2
    assert data["query"] == "门锁 打不开"


def test_search_product_tool_can_return_diagnostics(monkeypatch):
    fake_products = [
        {
            "service_product_code": "FWSP01537",
            "service_product_name": "门锁损坏（困客人）",
            "service_order_type": "托管维修",
            "score": 0.9,
        },
    ]
    fake_diagnostics = {
        "query": "门锁 打不开",
        "returned_count": 1,
        "candidates": [
            {
                "service_product_code": "FWSP01537",
                "vector_score": 0.91,
                "adjusted_score": 0.9,
                "included": True,
            }
        ],
    }

    class FakeStore:
        def search(self, **kwargs):
            return []

        def search_with_diagnostics(self, **kwargs):
            return fake_products, fake_diagnostics

    monkeypatch.setattr("tools.product_search.get_product_store", lambda: FakeStore())

    result = search_product_tool.invoke(
        {
            "query": "门锁 打不开",
            "top_k": 3,
            "include_diagnostics": True,
        }
    )
    data = result["data"]

    assert data["products"] == fake_products
    assert data["diagnostics"] == fake_diagnostics
