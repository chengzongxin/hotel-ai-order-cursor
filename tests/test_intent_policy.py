from types import SimpleNamespace

from workflow.intent_policy import (
    apply_intent_policy,
    build_detected_order_fields,
    get_extractor_history,
    merge_intent_order_info,
    resolve_phase_after_intent,
)
from langchain_core.messages import AIMessage, HumanMessage


def test_resolve_phase_after_intent_handles_submitted_smalltalk():
    assert resolve_phase_after_intent("create_order", "submitted", has_active_order=False) == "collecting"
    assert resolve_phase_after_intent("smalltalk", "submitted", has_active_order=False) == "idle"
    assert resolve_phase_after_intent("unknown", "pre_order", has_active_order=True) == "pre_order"


def test_build_detected_order_fields_normalizes_scope_and_goods_status():
    extraction = SimpleNamespace(
        room_number="301",
        product="空调",
        fault="不制冷",
        area="客房",
        urgency=None,
        expected_start_time="明天上午",
        goods_arrival_status="已到场",
        contacts="张三",
        phone="13800000000",
        managed_repair_scope="不存在的范围",
        user_confirmed=True,
    )

    fields = build_detected_order_fields(extraction, user_cancelled=False)

    assert fields["goods_arrival_status"] == "已到场"
    assert fields["managed_repair_scope"] is None
    assert fields["user_confirmed"] is True


def test_merge_intent_order_info_public_area_clears_stale_room():
    merged = merge_intent_order_info(
        intent="create_order",
        existing_order_info={"room_number": "301", "area": "客房", "expected_start_time": "明天"},
        detected_fields={
            "managed_repair_scope": "公区",
            "area": "大堂",
            "product": "灯",
            "fault": "不亮",
            "expected_start_time": "上午",
            "user_confirmed": False,
            "user_cancelled": False,
        },
        has_active_order=True,
        inferred_expected_start_time=None,
    )

    assert "room_number" not in merged
    assert merged["managed_repair_scope"] == "公区"
    assert merged["area"] == "大堂"
    assert merged["expected_start_time"] == "上午"


def test_merge_intent_order_info_room_clears_stale_public_scope():
    merged = merge_intent_order_info(
        intent="create_order",
        existing_order_info={"managed_repair_scope": "公区", "area": "公区"},
        detected_fields={
            "room_number": "301",
            "product": "门锁",
            "fault": "打不开",
            "expected_start_time": None,
            "user_confirmed": False,
            "user_cancelled": False,
        },
        has_active_order=True,
        inferred_expected_start_time="明天上午",
    )

    assert merged["room_number"] == "301"
    assert "managed_repair_scope" not in merged
    assert "area" not in merged
    assert merged["expected_start_time"] == "明天上午"


def test_apply_intent_policy_cancel_keeps_active_order_but_marks_cancelled():
    result = apply_intent_policy(
        intent="cancel_order",
        current_phase="pre_order",
        has_active_order=True,
        existing_order_info={"room_number": "301", "product": "空调"},
        detected_fields={"user_confirmed": False, "user_cancelled": True},
        inferred_expected_start_time=None,
    )

    assert result.phase == "pre_order"
    assert result.order_info["room_number"] == "301"
    assert result.order_info["user_confirmed"] is False
    assert result.order_info["user_cancelled"] is True


def test_get_extractor_history_uses_latest_human_after_submitted_order():
    history = get_extractor_history(
        {
            "last_order": {"order_id": "O1"},
            "order_info": {},
            "messages": [
                HumanMessage(content="301 空调不制冷"),
                AIMessage(content="已提交"),
                HumanMessage(content="再帮我修门锁"),
            ],
        }
    )

    assert history == "human: 再帮我修门锁"


def test_get_extractor_history_uses_full_history_for_active_order():
    history = get_extractor_history(
        {
            "order_info": {"product": "空调"},
            "messages": [
                HumanMessage(content="301 空调不制冷"),
                AIMessage(content="请问具体时间？"),
            ],
        }
    )

    assert history.splitlines() == ["human: 301 空调不制冷", "ai: 请问具体时间？"]
