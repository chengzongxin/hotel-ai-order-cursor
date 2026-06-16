"""Executable multi-turn workflow evals with fake LLM/tool dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from workflow.builder import IntentResult, clear_checkpoint_session, run_agent
from schemas.user import UserContext

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fake_llm_workflow_cases.json"
TEST_USER = UserContext(user_id="fake-eval-user", tenant_id="tenant-1", access_token="token")


class FakeStructuredLLM:
    def __init__(self, schema):
        self.schema = schema

    async def ainvoke(self, messages, config=None):
        content = str(messages[0].content if messages else "")
        user_input = extract_prompt_value(content, "用户最近输入")
        payload = fake_intent_payload(user_input)
        return self.schema(**payload)


class FakeLLM:
    def with_structured_output(self, schema):
        return FakeStructuredLLM(schema)

    async def astream(self, messages, config=None):
        yield AIMessage(content="请补充订单信息。")


class FakeProductSearchTool:
    @staticmethod
    def invoke(payload):
        query = str(payload.get("query") or "")
        if "洗衣机" in query:
            products = [
                product("WASHER_INSTALL", "洗衣机(安装)", "单次安装"),
                product("WASHER_DEBUG", "洗衣机(安装+调试)", "单次安装"),
            ]
        elif "空调" in query:
            products = [
                product("AC_REPAIR", "空调(小修)", "单次维修服务", fault="不制冷"),
                product("AC_REPAIR_MEDIUM", "空调(中修)", "单次维修服务", fault="压缩机故障"),
            ]
        else:
            products = [product("GENERIC_REPAIR", "通用维修", "单次维修服务")]

        return {
            "status": "success",
            "data": {
                "query": query,
                "products": products,
                "count": len(products),
            },
        }


def extract_prompt_value(prompt: str, label: str) -> str:
    pattern = rf"{re.escape(label)}：\n(.*?)(?:\n\n|$)"
    match = re.search(pattern, prompt, flags=re.S)
    return match.group(1).strip() if match else ""


def fake_intent_payload(user_input: str) -> dict[str, Any]:
    base = {
        "intent": "unknown",
        "room_number": None,
        "product": None,
        "fault": None,
        "area": None,
        "urgency": None,
        "expected_start_time": None,
        "goods_arrival_status": None,
        "contacts": None,
        "phone": None,
        "managed_repair_scope": None,
        "user_confirmed": False,
        "user_cancelled": False,
    }

    if "取消" in user_input or "不用了" in user_input:
        return {**base, "intent": "cancel_order", "user_cancelled": True}
    if user_input in {"第一个", "第1个", "1", "以上都不符合"}:
        return {**base, "intent": "unknown"}
    if "明天上午" in user_input and not any(keyword in user_input for keyword in ("空调", "洗衣机")):
        return {**base, "intent": "create_order", "expected_start_time": "明天上午"}
    if "洗衣机" in user_input:
        return {
            **base,
            "intent": "create_order",
            "room_number": extract_room(user_input),
            "product": "洗衣机",
            "expected_start_time": "明天上午" if "明天上午" in user_input else None,
        }
    if "空调" in user_input:
        return {
            **base,
            "intent": "create_order",
            "room_number": extract_room(user_input),
            "product": "空调",
            "fault": "不制冷" if "不制冷" in user_input else None,
            "area": "客房" if "房" in user_input else None,
            "managed_repair_scope": "客房" if "房" in user_input else None,
        }
    return base


def extract_room(text: str) -> str | None:
    match = re.search(r"(\d{3,4})\s*房", text)
    return match.group(1) if match else None


def product(code: str, name: str, service_type: str, fault: str = "") -> dict[str, Any]:
    return {
        "score": 0.9,
        "service_product_code": code,
        "service_product_name": name,
        "service_order_type": service_type,
        "product_type": "测试商品",
        "category": "测试分类",
        "related_area": "客房",
        "fault_phenomenon": fault,
        "price": "0",
        "unit": "次",
    }


async def fake_load_order_context(user):
    return {
        "selected_address": {"houseNumber": "301", "address": "测试酒店"},
        "contacts": "测试联系人",
        "phone": "13600000000",
        "hosting_card": {},
        "user_profile": {},
        "global_config": {},
    }


@pytest.fixture(scope="module")
def fake_workflow_cases() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert data["domain"] == "hotel_order_fake_llm_workflow"
    return data["cases"]


@pytest.fixture(autouse=True)
def fake_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr("workflow.builder.get_llm", lambda: FakeLLM())
    monkeypatch.setattr("workflow.builder.search_product_tool", FakeProductSearchTool)
    monkeypatch.setattr("workflow.builder.load_order_context", fake_load_order_context)
    monkeypatch.setattr("workflow.builder.save_conversation_log", async_noop)
    monkeypatch.setattr("workflow.builder.infer_expected_start_time_from_message", fake_infer_expected_time)
    monkeypatch.setattr("workflow.order_defaults.infer_expected_start_time_from_message", fake_infer_expected_time)
    monkeypatch.setattr("core.settings.settings.sqlite_memory_path", str(tmp_path / "fake_eval.sqlite3"))


async def async_noop(*args, **kwargs):
    return None


def fake_infer_expected_time(message: str) -> str | None:
    return "明天上午" if "明天上午" in message else None


def preview(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("order_preview")
    assert isinstance(data, dict), result
    return data


def assert_expected(payload: dict[str, Any], expected: dict[str, Any]):
    assert payload.get("phase") == expected.get("phase")
    if "service_type" in expected:
        assert payload.get("service_type") == expected["service_type"]
    if "selected_code" in expected:
        assert (payload.get("products") or {}).get("selected_code") == expected["selected_code"]
    if "products_count" in expected:
        assert len((payload.get("products") or {}).get("items") or []) == expected["products_count"]
    if "selection_rejected" in expected:
        assert (payload.get("products") or {}).get("selection_rejected") == expected["selection_rejected"]
    if "missing_info" in expected:
        assert payload.get("missing_info") == expected["missing_info"]
    for key, value in (expected.get("order_info") or {}).items():
        assert (payload.get("order_info") or {}).get(key) == value


@pytest.mark.asyncio
@pytest.mark.parametrize("case_index", range(5))
async def test_fake_llm_multi_turn_workflow(case_index: int, fake_workflow_cases: list[dict[str, Any]]):
    case = fake_workflow_cases[case_index]
    session_id = f"fake-{case['id']}"
    try:
        result: dict[str, Any] | None = None
        for turn in case["turns"]:
            result = await run_agent(turn, session_id=session_id, user=TEST_USER)

        assert result is not None
        if case["expected"].get("phase") == "cancelled" and result.get("order_preview") is None:
            assert "取消" in str(result.get("answer") or "")
        else:
            assert_expected(preview(result), case["expected"])
    finally:
        await clear_checkpoint_session(session_id, user=TEST_USER)
