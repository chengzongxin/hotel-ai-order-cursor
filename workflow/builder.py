import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

from workflow.llm import get_llm, get_llm_run_config
from workflow.prompts import PROMPTS_DIR, render_prompt
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from utils.logger_handler import trace_logger
from core.settings import settings
from workflow.agent import get_assist_agent
from workflow.confirmation_policy import build_confirmation_text
from workflow.coverage_policy import build_checked_coverage_output, decide_coverage_action
from workflow.expected_time import infer_expected_start_time_from_message
from workflow.intent_policy import apply_intent_policy, build_detected_order_fields
from workflow.intent_policy import get_extractor_history
from workflow.messages import (
    get_last_human_message,
    get_latest_ai_message,
)
from workflow.order_fields import normalize_order_card_update
from workflow.order_context_loader import load_order_context
from workflow.order_defaults import normalize_order_defaults
from workflow.products import (
    apply_product_selection_policy,
    build_product_search_feedback_from_state,
    build_product_search_output,
    build_product_search_query,
    get_selected_product,
)
from workflow.order_validation_policy import build_prepare_order_context_output, build_validate_order_output
from workflow.preview import build_order_preview, get_interrupt_answer
from workflow.questions import (
    build_missing_info_fallback_question,
    build_ask_response,
)
from workflow.routes import (
    has_active_order,
    route_after_confirm,
    route_after_intent,
    route_after_search_product,
    route_after_validation,
)
from workflow.session_access import ensure_session_access
from workflow.state import AgentState
from workflow.submission import empty_submission, get_effective_service_type, submit_order_from_state
from memory.postgres_log import save_conversation_log
from schemas.user import (
    SessionAccessError,
    UserContext,
    build_thread_id,
    require_user,
    user_from_runtime_config,
)
from workflow.checkpoint import (
    checkpoint_path,
    clear_checkpoint_session,
    get_checkpoint_messages,
    get_checkpoint_state,
    get_graph_config,
    message_to_item,
)
from workflow.constants import (
    ACTIVE_ORDER_PHASES,
    PHASE_CANCELLED,
    PHASE_COLLECTING,
    PHASE_IDLE,
    PHASE_PRE_ORDER,
    PHASE_SUBMITTED,
)
from workflow.streaming import emit_status, emit_token_text, message_chunk_to_text
from workflow.text_parsing import (
    is_cancel_request,
)
from tools.hosting_coverage import check_hosting_product_coverage
from tools.product_search import search_product_tool


class IntentResult(BaseModel):
    intent: str
    room_number: str | None = None
    product: str | None = None
    fault: str | None = None
    area: str | None = None
    urgency: str | None = None
    expected_start_time: str | None = None
    goods_arrival_status: str | None = None
    contacts: str | None = None
    phone: str | None = None
    managed_repair_scope: str | None = None
    user_confirmed: bool = False
    user_cancelled: bool = False


async def intent_node(state: AgentState) -> dict[str, object]:
    """一次性完成意图识别和订单信息抽取。"""

    emit_status("intent_node", "正在理解您的需求...")
    trace_logger(
        "node.intent.input",
        last_user_message=get_last_human_message(state["messages"]),
        message_count=len(state["messages"]),
        phase=state.get("phase"),
    )
    emit_status("intent_node", "正在识别意图并提取订单信息...")
    llm = get_llm().with_structured_output(IntentResult)
    result = await llm.ainvoke(
        [
            SystemMessage(
                content=render_prompt(
                    "intent/intent.md",
                    conversation_history=get_extractor_history(state),
                    user_input=get_last_human_message(state["messages"]),
                    status=state.get("phase") or PHASE_IDLE,
                    last_order=state.get("last_order", {}),
                )
            ),
        ],
        config=get_llm_run_config(),
    )

    last_user_message = get_last_human_message(state["messages"])
    user_cancelled = result.user_cancelled or (has_active_order(state) and is_cancel_request(last_user_message))
    intent = "cancel_order" if user_cancelled else result.intent
    emit_status("intent_node", f"已识别意图：{intent}")

    current_phase = state.get("phase")
    if intent in {"create_order", "confirm_order"}:
        emit_status("intent_node", "正在整理订单信息...")
    elif intent in {"smalltalk", "unknown"} and not has_active_order(state):
        emit_status("intent_node", "正在准备辅助回复...")
    elif intent == "cancel_order":
        emit_status("intent_node", "已收到取消请求...")

    active_order = has_active_order(state)
    existing_order_info = state.get("order_info", {}) if active_order else {}
    policy_result = apply_intent_policy(
        intent=intent,
        current_phase=current_phase,
        has_active_order=active_order,
        existing_order_info=existing_order_info,
        detected_fields=build_detected_order_fields(result, user_cancelled),
        inferred_expected_start_time=infer_expected_start_time_from_message(last_user_message),
    )
    output: dict[str, object] = {
        "intent": intent,
        "phase": policy_result.phase,
        "order_info": policy_result.order_info,
        "step": "intent_node",
        "last_user_message": last_user_message,
    }
    if intent in {"create_order", "confirm_order"} and state.get("phase") == PHASE_SUBMITTED:
        output.update(
            {
                "products": [],
                "selected_product_code": None,
                "submission": empty_submission(),
                "effective_service_type": None,
                "coverage_result": {},
                "order_submit_route": None,
                "order_context": {},
                "order_card_fields": [],
                "submitted_order": {},
                "product_selection_rejected": False,
            }
        )
    elif intent in {"smalltalk", "unknown"} and state.get("phase") == PHASE_SUBMITTED:
        output.update(
            {
                "submission": empty_submission(),
                "submitted_order": {},
            }
        )
    trace_logger("node.intent.output", **output)
    if intent in {"create_order", "confirm_order"}:
        emit_status("intent_node", "已完成需求理解，准备匹配商品...")
    return output


async def search_product_node(state: AgentState) -> dict[str, object]:
    """根据已抽取的商品和问题，尽早匹配真实可下单商品。"""

    last_msg = state.get("last_user_message", "")
    selection_decision = apply_product_selection_policy(state)
    if selection_decision.action == "reject":
        trace_logger("node.search_product.rejected", **selection_decision.output)
        return selection_decision.output

    if selection_decision.action == "select":
        trace_logger(
            "node.search_product.selected_by_text",
            selection=selection_decision.selection,
            **selection_decision.output,
        )
        return selection_decision.output

    if selection_decision.action == "skip_confirm":
        trace_logger(
            "node.search_product.skip",
            reason="confirm_with_existing_products",
            selected_product_code=state.get("selected_product_code"),
            product_count=len(state.get("products") or []),
        )
        return selection_decision.output

    order_info = state.get("order_info", {})
    fault = order_info.get("fault")

    # 无故障时从用户原始消息中补充服务意图关键词（如"安装"），辅助找到正确商品类型
    search_query = build_product_search_query(order_info, last_msg)
    if not search_query:
        output = {
            "products": [],
            "selected_product_code": None,
            "step": "search_product_node",
        }
        trace_logger("node.search_product.skipped", **output)
        return output

    result = await asyncio.to_thread(
        search_product_tool.invoke,
        {
            "query": search_query,
            "top_k": 3,
            "threshold": None,
            "has_fault": bool(fault),
        },
    )
    search_policy_result = build_product_search_output(
        tool_result=result,
        order_info=order_info,
        selected_product_code=state.get("selected_product_code"),
        last_user_message=state.get("last_user_message", ""),
    )
    service_type = search_policy_result.service_type
    if service_type:
        emit_status("search_product_node", f"已确定服务类型：{service_type}")
    trace_logger(
        "node.search_product.output",
        tool_status=result.get("status"),
        tool_error_code=result.get("error_code"),
        tool_message=result.get("message"),
        search_status=search_policy_result.search_status,
        **search_policy_result.output,
    )
    return search_policy_result.output


async def coverage_node(state: AgentState) -> dict[str, object]:
    """托管维修商品下单前，校验当前用户维保卡是否覆盖该商品。"""

    decision = decide_coverage_action(state)
    if decision.output is not None:
        return decision.output

    emit_status("coverage_node", "正在校验维保卡范围...")
    coverage_result = await check_hosting_product_coverage(
        order_info=state.get("order_info") or {},
        matched_product=decision.selected_product,
        user=user_from_runtime_config(),
    )
    coverage_data = coverage_result.get("data") or {}
    output = build_checked_coverage_output(
        coverage_data=coverage_data,
        fallback_service_type=str(decision.service_type),
        order_info=state.get("order_info", {}),
        last_user_message=state.get("last_user_message", ""),
    )

    if output.get("effective_service_type") != decision.service_type:
        emit_status("coverage_node", "该商品不在维保范围内，将按单次维修继续下单。")
    else:
        emit_status("coverage_node", "该商品在维保范围内，可继续托管维修下单。")
    trace_logger(
        "node.coverage.output",
        tool_status=coverage_result.get("status"),
        tool_error_code=coverage_result.get("error_code"),
        service_type=decision.service_type,
        **output,
    )
    return output


async def prepare_order_context_node(state: AgentState) -> dict[str, object]:
    """选择商品后，准备预下单卡片所需的默认值和展示字段。"""

    order_context = await load_order_context(user_from_runtime_config())
    result = build_prepare_order_context_output(state=state, order_context=order_context)
    trace_logger("node.prepare_order_context.output", service_type=result.service_type, **result.output)
    return result.output


async def validate_order_node(state: AgentState) -> dict[str, object]:
    """按订单类型检查缺失字段，并记录重试次数。"""

    result = build_validate_order_output(state)
    trace_logger(
        "node.validate_order.output",
        service_type=result.service_type,
        required_fields=result.required_fields,
        **result.output,
    )
    return result.output


async def ask_node(state: AgentState) -> dict[str, object]:
    """返回追问，让本轮语音对话自然结束。"""

    missing_info = state.get("missing_info", [])
    retry_count = state.get("retry_count", 0)
    ask_response = await build_ask_response(
        state,
        product_search_feedback=build_product_search_feedback_from_state(state),
    )
    if ask_response.should_emit:
        await emit_token_text(ask_response.question, step="ask_node")

    trace_logger(
        "node.ask.output",
        question=ask_response.question,
        missing_info=missing_info,
        retry_count=retry_count,
        off_topic_count=ask_response.off_topic_count,
        intent=state.get("intent"),
    )

    output = {
        "messages": [AIMessage(content=ask_response.question)],
        "step": "ask_node",
        "phase": state.get("phase") or PHASE_IDLE,
        "off_topic_count": ask_response.off_topic_count,
    }
    if ask_response.is_topic_deviation and not has_active_order(state):
        output.update(
            {
                "service_type": None,
                "order_info": {},
                "missing_info": [],
                "retry_count": 0,
            }
        )
    return output


async def assist_node(state: AgentState) -> dict[str, object]:
    """使用 LangChain 官方 create_agent middleware 处理非主下单咨询。"""

    trace_logger(
        "node.assist.input",
        message_count=len(state.get("messages", [])),
        intent=state.get("intent"),
        phase=state.get("phase"),
    )
    answer_parts: list[str] = []
    latest_messages: list[BaseMessage] = []
    async for part in get_assist_agent().astream(
        {"messages": state.get("messages", [])},
        config=get_llm_run_config(),
        stream_mode=["messages", "updates"],
        version="v2",
    ):
        part_type = part.get("type")
        data = part.get("data")
        if part_type == "messages" and isinstance(data, tuple):
            message_chunk, _metadata = data
            token = message_chunk_to_text(getattr(message_chunk, "content", ""))
            if token:
                answer_parts.append(token)
                await emit_token_text(token, step="assist_node", chunk_size=4, delay_seconds=0)
        elif part_type == "updates" and isinstance(data, dict):
            for node_update in data.values():
                if isinstance(node_update, dict) and isinstance(node_update.get("messages"), list):
                    latest_messages = node_update["messages"]

    answer = "".join(answer_parts).strip()
    if not answer:
        answer_message = get_latest_ai_message(latest_messages)
        answer = str(answer_message.content) if answer_message else "如果需要下单，请告诉我房号、商品和问题。"
        await emit_token_text(answer, step="assist_node")

    trace_logger(
        "node.assist.output",
        answer=str(answer),
        message_count=len(latest_messages),
    )
    return {
        "messages": [AIMessage(content=str(answer))],
        "step": "assist_node",
        "phase": state.get("phase") or PHASE_IDLE,
    }


async def confirm_node(state: AgentState) -> dict[str, object]:
    """让用户确认订单信息。"""

    order_info = state.get("order_info", {})
    if order_info.get("user_confirmed"):
        trace_logger("node.confirm.skip", reason="user_confirmed")
        return {
            "step": "confirm_node",
        }

    confirmation_text = build_confirmation_text(
        state,
        product_search_feedback=build_product_search_feedback_from_state(state),
    )
    await emit_token_text(confirmation_text, step="confirm_node")

    trace_logger(
        "node.confirm.output",
        confirmation_text=confirmation_text,
        order_info=order_info,
    )

    return {
        "messages": [AIMessage(content=confirmation_text)],
        "step": "confirm_node",
        "phase": PHASE_PRE_ORDER,
    }


async def cancel_node(state: AgentState) -> dict[str, object]:
    """取消当前预下单，避免旧订单继续参与后续对话。"""

    answer = render_prompt("cancel/cancel.md")
    await emit_token_text(answer, step="cancel_node")
    output = {
        "messages": [AIMessage(content=answer)],
        "step": "cancel_node",
        "intent": "cancel_order",
        "service_type": None,
        "effective_service_type": None,
        "coverage_result": {},
        "order_submit_route": None,
        "order_context": {},
        "order_card_fields": [],
        "phase": PHASE_CANCELLED,
        "order_info": {},
        "products": [],
        "selected_product_code": None,
        "missing_info": [],
        "submission": empty_submission(),
        "retry_count": 0,
        "off_topic_count": 0,
    }
    trace_logger(
        "node.cancel.output",
        answer=answer,
        previous_phase=state.get("phase"),
        previous_order_info=state.get("order_info", {}),
    )
    return output


async def submit_node(state: AgentState) -> dict[str, object]:
    """LangGraph 提交节点，从运行时配置读取当前用户上下文。"""

    return await submit_order_from_state(
        state,
        user_from_runtime_config(),
        emit=True,
        emit_token_text=emit_token_text,
    )


def build_graph(checkpointer: AsyncSqliteSaver | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("intent_node", intent_node)
    graph.add_node("search_product_node", search_product_node)
    graph.add_node("coverage_node", coverage_node)
    graph.add_node("prepare_order_context_node", prepare_order_context_node)
    graph.add_node("validate_order_node", validate_order_node)
    graph.add_node("ask_node", ask_node)
    graph.add_node("assist_node", assist_node)
    graph.add_node("confirm_node", confirm_node)
    graph.add_node("cancel_node", cancel_node)
    graph.add_node("submit_node", submit_node)

    graph.add_edge(START, "intent_node")
    graph.add_conditional_edges(
        "intent_node",
        route_after_intent,
        {
            "cancel_node": "cancel_node",
            "search_product_node": "search_product_node",
            "assist_node": "assist_node",
            "ask_node": "ask_node",
        },
    )
    graph.add_conditional_edges(
        "search_product_node",
        route_after_search_product,
        {
            "ask_node": "ask_node",
            "coverage_node": "coverage_node",
        },
    )
    graph.add_edge("coverage_node", "prepare_order_context_node")
    graph.add_edge("prepare_order_context_node", "validate_order_node")
    graph.add_conditional_edges(
        "validate_order_node",
        route_after_validation,
        {
            "ask_node": "ask_node",
            "confirm_node": "confirm_node",
        },
    )
    graph.add_conditional_edges(
        "confirm_node",
        route_after_confirm,
        {
            "submit_node": "submit_node",
            END: END,
        },
    )
    graph.add_edge("ask_node", END)
    graph.add_edge("assist_node", END)
    graph.add_edge("cancel_node", END)
    graph.add_edge("submit_node", END)

    if checkpointer is None:
        return graph.compile()

    return graph.compile(checkpointer=checkpointer)


from workflow.session_actions import (  # noqa: E402
    confirm_order_in_session,
    select_product_in_session,
    update_order_info_in_session,
)


NODE_STATUS_MESSAGES = {
    "intent_node": "正在理解您的需求并提取订单信息...",
    "search_product_node": "正在匹配可下单的标准商品...",
    "coverage_node": "正在校验商品是否在维保范围内...",
    "prepare_order_context_node": "正在读取下单默认信息...",
    "validate_order_node": "正在检查订单信息是否完整...",
    "ask_node": "正在生成追问问题...",
    "confirm_node": "正在整理订单确认信息...",
    "submit_node": "正在提交订单...",
    "cancel_node": "正在取消当前订单...",
    "assist_node": "正在调用辅助智能体处理问题...",
}

STREAMABLE_TOKEN_NODES: set[str] = set()


async def stream_agent_events(
    user_message: str,
    session_id: str | None,
    user: UserContext,
) -> AsyncIterator[dict[str, object]]:
    active_user = require_user(user)
    active_session_id = session_id or str(uuid4())

    trace_logger(
        "agent.stream.start",
        session_id=active_session_id,
        user_id=active_user.user_id,
        user_message=user_message,
    )
    yield {
        "type": "session",
        "session_id": active_session_id,
    }
    yield {
        "type": "status",
        "step": "intent_node",
        "message": NODE_STATUS_MESSAGES["intent_node"],
    }

    initial_state: AgentState = {
        "user_id": active_user.user_id,
        "messages": [HumanMessage(content=user_message)],
        "last_user_message": user_message,
    }

    try:
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path())) as checkpointer:
            await checkpointer.setup()
            graph = build_graph(checkpointer)
            config = get_graph_config(active_user, active_session_id)
            existing_snapshot = await graph.aget_state(config)
            if existing_snapshot.values:
                ensure_session_access(existing_snapshot.values, active_user)

            latest_state: dict[str, object] = dict(initial_state)
            emitted_token = False
            async for part in graph.astream(
                initial_state,
                config=config,
                stream_mode=["updates", "messages", "custom"],
                version="v2",
            ):
                part_type = part.get("type")
                data = part.get("data")

                if part_type == "updates" and isinstance(data, dict):
                    for node_name, node_update in data.items():
                        if not isinstance(node_update, dict):
                            continue

                        latest_state.update(node_update)
                        yield {
                            "type": "status",
                            "step": node_name,
                            "message": NODE_STATUS_MESSAGES.get(node_name, "正在处理您的请求..."),
                        }

                        order_preview = build_order_preview(latest_state)
                        if order_preview:
                            yield {
                                "type": "preview",
                                "step": node_name,
                                "order_preview": order_preview,
                            }

                if part_type == "messages" and isinstance(data, tuple):
                    message_chunk, metadata = data
                    if not isinstance(metadata, dict):
                        continue

                    node_name = metadata.get("langgraph_node")
                    if node_name not in STREAMABLE_TOKEN_NODES:
                        continue

                    token = message_chunk_to_text(getattr(message_chunk, "content", ""))
                    if not token:
                        continue

                    if not emitted_token:
                        emitted_token = True
                        yield {
                            "type": "status",
                            "step": node_name,
                            "message": "正在输出回复...",
                        }

                    yield {
                        "type": "token",
                        "step": node_name,
                        "content": token,
                    }

                if part_type == "custom":
                    if isinstance(data, dict) and data.get("type") in {"status", "token", "preview"}:
                        yield data
                    else:
                        yield {
                            "type": "status",
                            "message": str(data),
                        }

            snapshot = await graph.aget_state(config)
            final_state = snapshot.values or latest_state
            answer = get_interrupt_answer(final_state) or final_state["messages"][-1].content
            state_messages = final_state.get("messages", [])
            last_message = state_messages[-1] if state_messages else None
            if not isinstance(last_message, AIMessage) or last_message.content != answer:
                await graph.aupdate_state(
                    config,
                    {"messages": [AIMessage(content=answer)]},
                    as_node="ask_node",
                )

        trace_logger(
            "agent.stream.end",
            session_id=active_session_id,
            answer=answer,
            step=final_state.get("step"),
            intent=final_state.get("intent"),
            service_type=final_state.get("service_type"),
            order_info=final_state.get("order_info"),
            missing_info=final_state.get("missing_info"),
        )

        await save_conversation_log(active_session_id, "human", user_message)
        await save_conversation_log(active_session_id, "ai", str(answer))

        yield {
            "type": "final",
            "session_id": active_session_id,
            "answer": str(answer),
            "order_preview": build_order_preview(final_state),
        }
    except SessionAccessError:
        raise
    except Exception as exc:
        trace_logger(
            "agent.stream.error",
            session_id=active_session_id,
            error=repr(exc),
        )
        yield {
            "type": "error",
            "message": f"智能体处理失败：{exc}",
        }


async def run_agent(
    user_message: str,
    session_id: str | None,
    user: UserContext,
) -> dict[str, object]:
    active_user = require_user(user)
    active_session_id = session_id or str(uuid4())

    trace_logger(
        "agent.run.start",
        session_id=active_session_id,
        user_id=active_user.user_id,
        user_message=user_message,
    )

    initial_state: AgentState = {
        "user_id": active_user.user_id,
        "messages": [HumanMessage(content=user_message)],
        "last_user_message": user_message,
    }

    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path())) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        config = get_graph_config(active_user, active_session_id)
        existing_snapshot = await graph.aget_state(config)
        if existing_snapshot.values:
            ensure_session_access(existing_snapshot.values, active_user)
        result = await graph.ainvoke(
            initial_state,
            config=config,
        )
        answer = get_interrupt_answer(result) or result["messages"][-1].content
        state_messages = result.get("messages", [])
        last_message = state_messages[-1] if state_messages else None
        if not isinstance(last_message, AIMessage) or last_message.content != answer:
            await graph.aupdate_state(
                config,
                {"messages": [AIMessage(content=answer)]},
                as_node="ask_node",
            )

    trace_logger(
        "agent.run.end",
        session_id=active_session_id,
        answer=answer,
        step=result.get("step"),
        intent=result.get("intent"),
        service_type=result.get("service_type"),
        order_info=result.get("order_info"),
        missing_info=result.get("missing_info"),
    )

    await save_conversation_log(active_session_id, "human", user_message)
    await save_conversation_log(active_session_id, "ai", answer)

    return {
        "session_id": active_session_id,
        "answer": answer,
        "order_preview": build_order_preview(result),
    }
