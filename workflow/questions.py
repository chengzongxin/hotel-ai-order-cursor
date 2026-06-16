"""Question generation helpers for missing fields and topic boundary turns."""

from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import SystemMessage

from workflow.constants import MAX_RETRY_COUNT, PHASE_IDLE
from workflow.messages import get_asked_questions, get_last_human_message
from workflow.prompts import render_prompt
from workflow.products import get_selected_product
from workflow.routes import has_active_order
from workflow.state import AgentState
from workflow.streaming import stream_llm_text
from workflow.text_parsing import (
    build_product_recommendation_text,
    build_selected_product_text,
    parse_product_selection,
)


@dataclass(frozen=True)
class AskResponse:
    question: str
    off_topic_count: int
    is_topic_deviation: bool
    should_emit: bool = False


def build_missing_info_fallback_question(missing_info: list[str]) -> str:
    if not missing_info:
        return "请确认是否提交订单？"

    field = missing_info[0]
    questions = {
        "selected_product": build_product_recommendation_text([]),
        "room_number": "请问您住哪个房间？",
        "product": "是哪样东西坏了？",
        "fault": "具体是什么故障呢？",
        "area": "请问是客房还是公区？",
        "expected_start_time": "还需补充：期待开工时间。请问具体什么时间？比如明天上午或3月20日",
        "goods_arrival_status": "请问货物是否到场？",
        "contacts": "请问联系人姓名是什么？",
        "phone": "请问联系电话是多少？",
    }
    return questions.get(field, f"请补充{field}。")


async def build_missing_info_question(state: AgentState) -> str:
    missing_info = state.get("missing_info", [])
    if not missing_info:
        return build_missing_info_fallback_question(missing_info)
    if missing_info[0] == "expected_start_time":
        return build_missing_info_fallback_question(missing_info)
    if missing_info[0] == "goods_arrival_status":
        return build_missing_info_fallback_question(missing_info)

    prompt = render_prompt(
        "ask/missing_info.md",
        order_info=state.get("order_info", {}),
        missing_info=missing_info,
        asked_questions=get_asked_questions(state.get("messages", [])),
        last_user_message=get_last_human_message(state.get("messages", [])),
    )
    question = await stream_llm_text([SystemMessage(content=prompt)], step="ask_node")
    return question or build_missing_info_fallback_question(missing_info)


async def build_topic_boundary_response(state: AgentState) -> str:
    missing_info = state.get("missing_info", [])
    active_order = has_active_order(state)
    next_question = build_missing_info_fallback_question(missing_info) if active_order else ""
    if active_order and not missing_info and not state.get("order_info"):
        next_question = "请说房号和故障。"
    prompt = render_prompt(
        "ask/off_topic.md",
        last_user_message=get_last_human_message(state.get("messages", [])),
        active_order=active_order,
        status=state.get("phase") or PHASE_IDLE,
        order_info=state.get("order_info", {}) if active_order else {},
        last_order=state.get("last_order", {}),
        missing_info=missing_info,
        next_question=next_question,
        off_topic_count=state.get("off_topic_count", 0) + 1,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    answer = await stream_llm_text([SystemMessage(content=prompt)], step="ask_node")
    return answer or render_prompt(
        "ask/unknown_fallback.md",
        next_question=next_question or "如果需要继续报修，请告诉我房号和故障。",
    )


async def build_ask_response(
    state: AgentState,
    *,
    product_search_feedback: str | None = None,
) -> AskResponse:
    missing_info = state.get("missing_info", [])
    retry_count = state.get("retry_count", 0)
    off_topic_count = state.get("off_topic_count", 0)
    is_topic_deviation = state.get("intent") in {"unknown", "smalltalk"}
    products = state.get("products") or []
    selected_product = get_selected_product(products, state.get("selected_product_code"), default_to_first=False)
    last_user_message = get_last_human_message(state.get("messages", []))
    selected_by_text = parse_product_selection(last_user_message) in {1, 2, 3}

    if state.get("product_selection_rejected"):
        return AskResponse(
            question="好的，请您再详细描述商品和故障现象，我再帮您推荐服务商品。",
            off_topic_count=off_topic_count,
            is_topic_deviation=is_topic_deviation,
            should_emit=True,
        )
    if products and not selected_product:
        return AskResponse(
            question=build_product_recommendation_text(products),
            off_topic_count=off_topic_count,
            is_topic_deviation=is_topic_deviation,
            should_emit=True,
        )
    if selected_product and selected_by_text and missing_info:
        prefix = build_selected_product_text(selected_product)
        return AskResponse(
            question=f"{prefix}\n{build_missing_info_fallback_question(missing_info)}",
            off_topic_count=off_topic_count,
            is_topic_deviation=is_topic_deviation,
            should_emit=True,
        )
    if is_topic_deviation:
        return AskResponse(
            question=await build_topic_boundary_response(state),
            off_topic_count=off_topic_count + 1,
            is_topic_deviation=is_topic_deviation,
        )
    if retry_count > MAX_RETRY_COUNT:
        return AskResponse(
            question=render_prompt(
                "ask/missing_info_retry.md",
                missing_info=", ".join(missing_info),
            ),
            off_topic_count=off_topic_count,
            is_topic_deviation=is_topic_deviation,
            should_emit=True,
        )
    if product_search_feedback and missing_info:
        return AskResponse(
            question=f"{product_search_feedback}\n{build_missing_info_fallback_question(missing_info)}",
            off_topic_count=off_topic_count,
            is_topic_deviation=is_topic_deviation,
            should_emit=True,
        )
    return AskResponse(
        question=await build_missing_info_question(state),
        off_topic_count=off_topic_count,
        is_topic_deviation=is_topic_deviation,
    )
