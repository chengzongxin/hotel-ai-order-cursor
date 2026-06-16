from langchain_core.messages import AIMessage, HumanMessage

from graph import builder
from workflow.messages import format_messages, get_asked_questions, get_last_human_message, get_latest_ai_message
from workflow.questions import build_missing_info_fallback_question


def test_message_helpers_extract_history_parts():
    messages = [
        HumanMessage(content="1208房间空调不制冷"),
        AIMessage(content="请问具体什么时间？"),
        HumanMessage(content="明天上午"),
        AIMessage(content="已生成预下单页面。"),
    ]

    assert format_messages(messages).splitlines()[0] == "human: 1208房间空调不制冷"
    assert get_last_human_message(messages) == "明天上午"
    assert get_asked_questions(messages) == ["请问具体什么时间？"]
    assert get_latest_ai_message(messages).content == "已生成预下单页面。"


def test_question_helper_keeps_builder_compatibility_export():
    assert build_missing_info_fallback_question(["phone"]) == "请问联系电话是多少？"
    assert builder.build_missing_info_fallback_question(["phone"]) == "请问联系电话是多少？"
