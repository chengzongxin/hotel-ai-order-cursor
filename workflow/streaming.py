"""流式事件与 LLM token 输出辅助。"""

from __future__ import annotations

import asyncio

from langchain_core.messages import BaseMessage
from langgraph.config import get_stream_writer

from workflow.llm import get_llm, get_llm_run_config


def get_optional_stream_writer():
    try:
        return get_stream_writer()
    except RuntimeError:
        return None


def emit_status(step: str, message: str) -> None:
    writer = get_optional_stream_writer()
    if writer:
        writer({"type": "status", "step": step, "message": message})


def message_chunk_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


async def emit_token_text(text: str, step: str, chunk_size: int = 4, delay_seconds: float = 0.015) -> None:
    writer = get_optional_stream_writer()
    if not writer:
        return

    for index in range(0, len(text), chunk_size):
        token = text[index : index + chunk_size]
        if token:
            writer({"type": "token", "step": step, "content": token})
            await asyncio.sleep(delay_seconds)


async def stream_llm_text(messages: list[BaseMessage], step: str) -> str:
    parts: list[str] = []
    async for chunk in get_llm().astream(messages, config=get_llm_run_config()):
        token = message_chunk_to_text(getattr(chunk, "content", ""))
        if not token:
            continue
        parts.append(token)
        await emit_token_text(token, step=step, chunk_size=4, delay_seconds=0)
    return "".join(parts).strip()
