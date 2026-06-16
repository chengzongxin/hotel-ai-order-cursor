"""Product search API contract tests."""

import pytest

from api.routes import search_products
from schemas.product import ProductSearchRequest


@pytest.mark.asyncio
async def test_search_products_passes_diagnostics_request(monkeypatch):
    captured_payload = {}
    diagnostics = {
        "query": "门锁 打不开",
        "returned_count": 1,
        "candidates": [{"service_product_code": "FWSP01537", "included": True}],
    }

    class FakeTool:
        @staticmethod
        def invoke(payload):
            captured_payload.update(payload)
            return {
                "status": "success",
                "data": {
                    "query": payload["query"],
                    "products": [
                        {
                            "score": 0.9,
                            "service_product_code": "FWSP01537",
                            "service_product_name": "门锁损坏（困客人）",
                            "service_order_type": "托管维修",
                            "product_type": "维修",
                            "related_area": "客房",
                            "fault_phenomenon": "打不开",
                            "price": "0",
                            "unit": "次",
                        }
                    ],
                    "diagnostics": diagnostics,
                },
            }

    monkeypatch.setattr("api.routes.search_product_tool", FakeTool)

    response = await search_products(
        ProductSearchRequest(
            query="门锁 打不开",
            top_k=3,
            has_fault=True,
            include_diagnostics=True,
        )
    )

    assert captured_payload["has_fault"] is True
    assert captured_payload["include_diagnostics"] is True
    assert response.diagnostics is not None
    assert response.diagnostics.query == diagnostics["query"]
    assert response.diagnostics.returned_count == 1
    assert response.diagnostics.candidates[0].service_product_code == "FWSP01537"
    assert response.products[0].service_product_code == "FWSP01537"


@pytest.mark.asyncio
async def test_search_products_omits_diagnostics_by_default(monkeypatch):
    class FakeTool:
        @staticmethod
        def invoke(payload):
            return {
                "status": "success",
                "data": {
                    "query": payload["query"],
                    "products": [],
                    "diagnostics": {"should": "not leak by default"},
                },
            }

    monkeypatch.setattr("api.routes.search_product_tool", FakeTool)

    response = await search_products(ProductSearchRequest(query="门锁 打不开"))

    assert response.diagnostics is None
