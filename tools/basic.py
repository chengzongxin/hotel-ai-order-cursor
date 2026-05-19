from datetime import UTC, datetime

from langchain_core.tools import tool


@tool
def current_time() -> str:
    """获取当前 UTC 时间。"""

    return datetime.now(UTC).isoformat()


@tool
def echo(text: str) -> str:
    """原样返回输入文本，适合测试工具调用链路。"""

    return text
