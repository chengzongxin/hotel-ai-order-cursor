import pytest

from workflow.order_context_loader import load_order_context
from schemas.user import UserContext


@pytest.mark.asyncio
async def test_load_order_context_returns_tool_data(monkeypatch):
    async def fake_loader(user):
        return {"contacts": "张三", "phone": "13800000000"}

    monkeypatch.setattr("workflow.order_context_loader.load_managed_repair_order_context", fake_loader)

    assert await load_order_context(UserContext(user_id="u1")) == {
        "contacts": "张三",
        "phone": "13800000000",
    }


@pytest.mark.asyncio
async def test_load_order_context_returns_safe_fallback_on_error(monkeypatch):
    async def fake_loader(user):
        raise RuntimeError("boom")

    monkeypatch.setattr("workflow.order_context_loader.load_managed_repair_order_context", fake_loader)

    result = await load_order_context(UserContext(user_id="u1"))

    assert result["context_error"] == "RuntimeError: boom"
    assert result["selected_address"] == {}
    assert result["contacts"] is None
    assert result["phone"] is None
