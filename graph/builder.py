from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import AliasChoices, BaseModel, Field

from config.logging import trace_event
from config.settings import settings
from graph.state import AgentState
from memory.postgres_log import save_conversation_log
from memory.sqlite_memory import SQLiteChatMemory

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "system.md"
MAX_RETRY_COUNT = 2

REQUIRED_FIELDS_BY_ORDER_TYPE: dict[str, list[str]] = {
    "repair_order": ["room_number", "product", "fault", "area"],
}


class IntentResult(BaseModel):
    current_intent: str = Field(
        description="用户当前意图",
        validation_alias=AliasChoices("current_intent", "intent"),
    )
    current_order_type: str | None = Field(
        default=None,
        description="订单类型",
        validation_alias=AliasChoices("current_order_type", "order_type"),
    )


class ExtractedFieldsResult(BaseModel):
    room_number: str | None = None
    product: str | None = Field(
        default=None,
        validation_alias=AliasChoices("product", "item", "equipment"),
    )
    fault: str | None = Field(
        default=None,
        validation_alias=AliasChoices("fault", "fault_description", "problem"),
    )
    area: str | None = None
    urgency: str | None = None
    user_confirmed: bool = False


@lru_cache
def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache
def get_llm() -> BaseChatModel:
    return init_chat_model(
        model=settings.openai_model,
        model_provider="openai",
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
    )


def format_messages(messages: list[BaseMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.type
        lines.append(f"{role}: {message.content}")
    return "\n".join(lines)


def get_last_human_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


async def intent_node(state: AgentState) -> dict[str, str | None]:
    """识别用户当前维修意图和订单类型。"""

    trace_event(
        "node.intent.input",
        last_user_message=get_last_human_message(state["messages"]),
        message_count=len(state["messages"]),
    )
    llm = get_llm().with_structured_output(IntentResult)
    result = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "你是酒店 AI 维修下单系统的意图识别器。\n"
                    "请输出 JSON object，且只能输出符合 schema 的 JSON。\n"
                    "请把用户意图归类为：create_repair_order、confirm_repair_order、cancel_repair_order、smalltalk、unknown。\n"
                    "只要用户提到维修、报修、设备坏了、漏水、不亮、不制冷、打不开、堵塞等，都属于 create_repair_order。\n"
                    "如果是维修相关请求，current_order_type 必须返回 repair_order。\n"
                    "如果只是闲聊或完全无关，current_order_type 返回 null。"
                )
            ),
            HumanMessage(content=format_messages(state["messages"])),
        ]
    )

    output = {
        "current_intent": result.current_intent,
        "current_order_type": result.current_order_type
        or ("repair_order" if result.current_intent in {"create_repair_order", "confirm_repair_order"} else None),
        "current_step": "intent_node",
        "last_user_message": get_last_human_message(state["messages"]),
    }
    trace_event("node.intent.output", **output)
    return output


async def extractor_node(state: AgentState) -> dict[str, object]:
    """从多轮对话中提取维修下单需要的结构化字段。"""

    trace_event(
        "node.extractor.input",
        current_intent=state.get("current_intent"),
        current_order_type=state.get("current_order_type"),
        last_user_message=get_last_human_message(state["messages"]),
    )
    llm = get_llm().with_structured_output(ExtractedFieldsResult)
    result = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "你是酒店维修下单字段提取器。\n"
                    "请输出 JSON object，且只能输出符合 schema 的 JSON。\n"
                    "请只从对话中提取已经明确出现的信息，不要猜测。\n"
                    "需要提取：room_number 房号、product 维修商品或设备、fault 故障、area 区域、urgency 紧急度。\n"
                    "如果用户说厕所、浴室、洗手间，area 可以归一为卫生间。\n"
                    "如果用户说空调不制冷，product 是空调，fault 是不制冷。\n"
                    "如果用户说水龙头漏水，product 是水龙头，fault 是漏水。\n"
                    "urgency 只能是 low、medium、high、urgent 或 null。\n"
                    "如果用户明确表示确认订单，把 user_confirmed 设置为 true。"
                )
            ),
            HumanMessage(content=format_messages(state["messages"])),
        ]
    )

    fields = result.model_dump()
    output = {
        "extracted_fields": fields,
        "current_step": "extractor_node",
    }
    trace_event("node.extractor.output", **output)
    return output


async def missing_field_node(state: AgentState) -> dict[str, object]:
    """根据维修订单类型检查缺失字段，并记录重试次数。"""

    order_type = state.get("current_order_type")
    required_fields = REQUIRED_FIELDS_BY_ORDER_TYPE.get(order_type or "", [])
    extracted_fields = state.get("extracted_fields", {})
    missing_fields = [
        field
        for field in required_fields
        if not extracted_fields.get(field)
    ]

    retry_count = state.get("retry_count", 0)
    if missing_fields:
        retry_count += 1

    output = {
        "missing_fields": missing_fields,
        "retry_count": retry_count,
        "current_step": "missing_field_node",
    }
    trace_event(
        "node.missing_field.output",
        current_order_type=order_type,
        extracted_fields=extracted_fields,
        **output,
    )
    return output


def build_missing_field_question(missing_fields: list[str]) -> str:
    if not missing_fields:
        return "请确认是否提交维修单？"

    field = missing_fields[0]
    questions = {
        "room_number": "请问您住哪个房间？",
        "product": "是哪样东西坏了？",
        "fault": "具体是什么故障呢？",
        "area": "是在房间哪里呢？",
        "urgency": "这个情况着急吗？",
    }
    return questions.get(field, f"请补充{field}。")


async def ask_user_node(state: AgentState) -> dict[str, object]:
    """暂停图执行，等待用户补充缺失信息。"""

    missing_fields = state.get("missing_fields", [])
    retry_count = state.get("retry_count", 0)

    if state.get("current_intent") in {"unknown", "smalltalk"}:
        question = "我可以帮您报修，请说房号和故障。"
    elif retry_count > MAX_RETRY_COUNT:
        question = (
            "我还缺少关键信息，请补充："
            f"{', '.join(missing_fields)}。"
        )
    else:
        question = build_missing_field_question(missing_fields)

    trace_event(
        "node.ask_user.output",
        question=question,
        missing_fields=missing_fields,
        retry_count=retry_count,
        current_intent=state.get("current_intent"),
    )

    interrupt(
        {
            "reason": "missing_required_fields",
            "question": question,
            "missing_fields": missing_fields,
            "retry_count": retry_count,
        }
    )

    return {
        "messages": [AIMessage(content=question)],
        "current_step": "ask_user_node",
    }


async def confirm_node(state: AgentState) -> dict[str, object]:
    """让用户确认维修订单信息。"""

    extracted_fields = state.get("extracted_fields", {})
    order_type = state.get("current_order_type")

    if extracted_fields.get("user_confirmed"):
        trace_event("node.confirm.skip", reason="user_confirmed")
        return {
            "current_step": "confirm_node",
        }

    confirmation_text = (
        "请确认维修单信息：\n"
        f"- 订单类型：{order_type}\n"
        f"- 房号：{extracted_fields.get('room_number')}\n"
        f"- 商品/设备：{extracted_fields.get('product')}\n"
        f"- 故障：{extracted_fields.get('fault')}\n"
        f"- 区域：{extracted_fields.get('area')}\n"
        f"- 紧急度：{extracted_fields.get('urgency') or 'medium'}\n"
        "如果无误，请回复“确认”；如果需要修改，请直接说明要改哪里。"
    )

    trace_event(
        "node.confirm.output",
        confirmation_text=confirmation_text,
        extracted_fields=extracted_fields,
    )

    interrupt(
        {
            "reason": "confirm_order",
            "question": confirmation_text,
            "extracted_fields": extracted_fields,
        }
    )

    return {
        "messages": [AIMessage(content=confirmation_text)],
        "current_step": "confirm_node",
    }


async def submit_order_node(state: AgentState) -> dict[str, object]:
    """提交订单。

    真实项目中这里通常会调用维修工单系统 API。
    当前骨架先返回一个稳定的订单号，方便本地直接运行和测试流程。
    """

    order_id = f"ORDER-{uuid4().hex[:8].upper()}"
    answer = (
        "维修单已提交成功。\n"
        f"维修单号：{order_id}\n"
        f"订单类型：{state.get('current_order_type')}\n"
        f"维修单信息：{state.get('extracted_fields', {})}"
    )

    output = {
        "messages": [AIMessage(content=answer)],
        "current_step": "submit_order_node",
    }
    trace_event(
        "node.submit_order.output",
        answer=answer,
        extracted_fields=state.get("extracted_fields", {}),
    )
    return output


def route_after_intent(state: AgentState) -> str:
    intent = state.get("current_intent")
    if intent in {"create_repair_order", "confirm_repair_order", "create_order", "confirm_order"}:
        return "extractor_node"
    return "ask_user_node"


def route_after_missing_field_check(state: AgentState) -> str:
    if state.get("missing_fields"):
        return "ask_user_node"
    return "confirm_node"


def route_after_confirm(state: AgentState) -> str:
    extracted_fields = state.get("extracted_fields", {})
    if extracted_fields.get("user_confirmed"):
        return "submit_order_node"
    return END


def build_graph(checkpointer: AsyncSqliteSaver | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("intent_node", intent_node)
    graph.add_node("extractor_node", extractor_node)
    graph.add_node("missing_field_node", missing_field_node)
    graph.add_node("ask_user_node", ask_user_node)
    graph.add_node("confirm_node", confirm_node)
    graph.add_node("submit_order_node", submit_order_node)

    graph.add_edge(START, "intent_node")
    graph.add_conditional_edges(
        "intent_node",
        route_after_intent,
        {
            "extractor_node": "extractor_node",
            "ask_user_node": "ask_user_node",
        },
    )
    graph.add_edge("extractor_node", "missing_field_node")
    graph.add_conditional_edges(
        "missing_field_node",
        route_after_missing_field_check,
        {
            "ask_user_node": "ask_user_node",
            "confirm_node": "confirm_node",
        },
    )
    graph.add_conditional_edges(
        "confirm_node",
        route_after_confirm,
        {
            "submit_order_node": "submit_order_node",
            END: END,
        },
    )
    graph.add_edge("ask_user_node", END)
    graph.add_edge("submit_order_node", END)

    if checkpointer is None:
        return graph.compile()

    return graph.compile(checkpointer=checkpointer)


def get_interrupt_answer(result: dict[str, object]) -> str | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None

    first_interrupt = interrupts[0]
    payload = getattr(first_interrupt, "value", first_interrupt)
    if isinstance(payload, dict):
        question = payload.get("question")
        return str(question) if question else None

    return str(payload)


async def run_agent(
    user_message: str,
    session_id: str | None,
    memory: SQLiteChatMemory,
) -> dict[str, str]:
    active_session_id = session_id or str(uuid4())
    await memory.init()

    history = await memory.get_langchain_messages(active_session_id)
    conversation_summary = await memory.maybe_update_summary(active_session_id)

    trace_event(
        "agent.run.start",
        session_id=active_session_id,
        user_message=user_message,
        history_count=len(history),
        has_conversation_summary=bool(conversation_summary),
    )

    initial_state: AgentState = {
        "conversation_id": active_session_id,
        "messages": [*history, HumanMessage(content=user_message)],
        "last_user_message": user_message,
        "retry_count": 0,
        "deviation_count": 0,
        "conversation_summary": conversation_summary,
    }

    db_path = Path(settings.sqlite_memory_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        await checkpointer.setup()
        result = await build_graph(checkpointer).ainvoke(
            initial_state,
            config={
                "configurable": {"thread_id": active_session_id},
                "run_name": "repair_order_graph",
                "tags": [
                    "hotel-ai-order",
                    "repair-order",
                    settings.app_env,
                ],
                "metadata": {
                    "session_id": active_session_id,
                    "app_env": settings.app_env,
                    "message_count": len(initial_state["messages"]),
                    "has_conversation_summary": bool(conversation_summary),
                },
            },
        )
    answer = get_interrupt_answer(result) or result["messages"][-1].content
    trace_event(
        "agent.run.end",
        session_id=active_session_id,
        answer=answer,
        current_step=result.get("current_step"),
        current_intent=result.get("current_intent"),
        current_order_type=result.get("current_order_type"),
        extracted_fields=result.get("extracted_fields"),
        missing_fields=result.get("missing_fields"),
    )

    await memory.append_message(active_session_id, "human", user_message)
    await memory.append_message(active_session_id, "ai", answer)
    await memory.maybe_update_summary(active_session_id)
    await save_conversation_log(active_session_id, "human", user_message)
    await save_conversation_log(active_session_id, "ai", answer)

    return {
        "session_id": active_session_id,
        "conversation_id": active_session_id,
        "answer": answer,
    }
