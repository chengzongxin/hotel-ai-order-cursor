import pytest

from schemas.user import UserContext
from tools.hosting_coverage import check_hosting_product_coverage
from tools.hosting_scope import query_hosting_scope
from tools.registry import get_tools


@pytest.mark.asyncio
async def test_query_hosting_scope_returns_card_scope(monkeypatch):
    async def fake_fetch_hosting_card_with_diagnostics(user):
        return {
            "id": 123,
            "comboName": "基础维保卡",
            "status": 1,
            "tenantName": "测试酒店",
            "address": "深圳市南山区",
            "scopeRepairSpuIdList": [
                {
                    "scopeRepairSpuId": 10,
                    "scopeRepairSpuName": "空调清洗",
                    "secondAreaName": "客房",
                    "scopeRepairSpuCode": "AC_CLEAN",
                },
                {
                    "scopeRepairSpuId": 11,
                    "scopeRepairSpuName": "门锁维修",
                    "secondAreaName": "公区",
                },
            ],
        }, {
            "endpoint": "/app-api/order/hosting-card/card",
            "reason": "ok",
            "code": 200,
            "message": "ok",
            "data": {},
            "raw_response": {"code": 200, "msg": "ok", "data": {}},
        }

    monkeypatch.setattr(
        "tools.hosting_scope.fetch_hosting_card_with_diagnostics",
        fake_fetch_hosting_card_with_diagnostics,
    )

    result = await query_hosting_scope(UserContext(user_id="u1", tenant_id="t1", access_token="token"))

    assert result["status"] == "success"
    data = result["data"]
    assert data["has_hosting_card"] is True
    assert data["hosting_card_name"] == "基础维保卡"
    assert data["hosting_card_status_display"] == "生效中"
    assert data["scope_count"] == 2
    assert data["scopes"][0]["spu_name"] == "空调清洗"
    assert data["scopes"][0]["area"] == "客房"
    assert "空调清洗" in data["summary"]
    assert data["interface_response"]["code"] == 200


@pytest.mark.asyncio
async def test_query_hosting_scope_includes_interface_response_when_card_missing(monkeypatch):
    async def fake_fetch_hosting_card_with_diagnostics(user):
        return None, {
            "endpoint": "/app-api/order/hosting-card/card",
            "reason": "empty_or_invalid_data",
            "code": 200,
            "message": "ok",
            "data": None,
            "raw_response": {"code": 200, "msg": "ok", "data": None},
        }

    monkeypatch.setattr(
        "tools.hosting_scope.fetch_hosting_card_with_diagnostics",
        fake_fetch_hosting_card_with_diagnostics,
    )

    result = await query_hosting_scope(UserContext(user_id="u1", tenant_id="t1", access_token="token"))

    assert result["status"] == "success"
    assert result["data"]["has_hosting_card"] is False
    assert result["data"]["scopes"] == []
    assert "没有可用维保卡" in result["data"]["summary"]
    assert result["data"]["interface_response"]["reason"] == "empty_or_invalid_data"
    assert result["data"]["interface_response"]["raw_response"] == {"code": 200, "msg": "ok", "data": None}


@pytest.mark.asyncio
async def test_query_hosting_scope_includes_non_200_response(monkeypatch):
    async def fake_fetch_hosting_card_with_diagnostics(user):
        return None, {
            "endpoint": "/app-api/order/hosting-card/card",
            "reason": "api_non_200",
            "code": 401,
            "message": "token expired",
            "data": None,
            "raw_response": {"code": 401, "msg": "token expired", "data": None},
        }

    monkeypatch.setattr(
        "tools.hosting_scope.fetch_hosting_card_with_diagnostics",
        fake_fetch_hosting_card_with_diagnostics,
    )

    result = await query_hosting_scope(UserContext(user_id="u1", tenant_id="t1", access_token="token"))

    assert result["status"] == "success"
    assert result["data"]["interface_response"]["code"] == 401
    assert result["data"]["interface_response"]["message"] == "token expired"


@pytest.mark.asyncio
async def test_hosting_coverage_reuses_interface_diagnostics(monkeypatch):
    async def fake_fetch_hosting_card_with_diagnostics(user):
        return None, {
            "endpoint": "/app-api/order/hosting-card/card",
            "reason": "api_non_200",
            "code": 401,
            "message": "token expired",
            "data": None,
            "raw_response": {"code": 401, "msg": "token expired", "data": None},
        }

    monkeypatch.setattr(
        "tools.hosting_coverage.fetch_hosting_card_with_diagnostics",
        fake_fetch_hosting_card_with_diagnostics,
    )

    result = await check_hosting_product_coverage(
        order_info={"managed_repair_scope": "客房"},
        matched_product={"service_product_name": "空调(小修)"},
        user=UserContext(user_id="u1", tenant_id="t1", access_token="token"),
    )

    assert result["status"] == "success"
    data = result["data"]
    assert data["covered"] is False
    assert data["effective_service_type"] == "单次维修服务"
    assert data["interface_response"]["reason"] == "api_non_200"
    assert data["interface_response"]["message"] == "token expired"


def test_assist_tools_include_query_hosting_scope_tool():
    tool_names = {tool.name for tool in get_tools()}

    assert "query_hosting_scope_tool" in tool_names
