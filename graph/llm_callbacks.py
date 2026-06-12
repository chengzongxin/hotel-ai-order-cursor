from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from utils.logger_handler import get_logger

_llm_trace_logger = get_logger("agent.llm")

_SENSITIVE_KEYS = {"openai_api_key", "api_key"}


def _message_to_dict(message: BaseMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": message.__class__.__name__,
        "content": message.content,
    }
    if getattr(message, "name", None):
        payload["name"] = message.name
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = tool_calls
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if additional_kwargs:
        payload["additional_kwargs"] = additional_kwargs
    return payload


def _sanitize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if key in _SENSITIVE_KEYS:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_mapping(value)
        else:
            sanitized[key] = value
    return sanitized


def log_llm_call_params(**payload: Any) -> None:
    _llm_trace_logger.info(
        "llm.call.payload %s",
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def log_llm_call_response(**payload: Any) -> None:
    _llm_trace_logger.info(
        "llm.call.response %s",
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def _generations_to_messages(response: LLMResult) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for generation_batch in response.generations:
        for generation in generation_batch:
            message = getattr(generation, "message", None)
            if message is not None:
                messages.append(_message_to_dict(message))
                continue
            text = getattr(generation, "text", None)
            if text:
                messages.append({"type": "AIMessage", "content": text})
    return messages


class LLMCallTraceHandler(BaseCallbackHandler):
    """记录每次 Chat Model 调用的完整参数。"""

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        flat_messages = [_message_to_dict(message) for batch in messages for message in batch]
        log_llm_call_params(
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            tags=tags or [],
            metadata=metadata or {},
            model=serialized.get("name"),
            model_id=serialized.get("id"),
            model_config=_sanitize_mapping(serialized.get("kwargs", {})),
            invocation_params=kwargs.get("invocation_params"),
            options=kwargs.get("options"),
            batch_size=kwargs.get("batch_size"),
            name=kwargs.get("name"),
            messages=flat_messages,
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> Any:
        log_llm_call_response(
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            tags=tags or [],
            llm_output=response.llm_output or {},
            messages=_generations_to_messages(response),
        )


_handler: LLMCallTraceHandler | None = None


def get_llm_trace_handler() -> LLMCallTraceHandler:
    global _handler
    if _handler is None:
        _handler = LLMCallTraceHandler()
    return _handler
