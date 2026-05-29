import inspect
import time
from typing import Any

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
    wrap_model_call,
    wrap_tool_call,
)

from config.logging import trace_event


@wrap_model_call
async def log_model_call(request: Any, handler: Any) -> Any:
    start = time.perf_counter()
    trace_event(
        "agent.middleware.llm.before",
        message_count=len(request.messages),
        tool_count=len(request.tools or []),
    )
    try:
        result = handler(request)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        trace_event("agent.middleware.llm.error", error=repr(exc))
        raise

    trace_event(
        "agent.middleware.llm.after",
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
        result_preview=str(result)[:1000],
    )
    return result


@wrap_tool_call
async def log_tool_call(request: Any, handler: Any) -> Any:
    start = time.perf_counter()
    tool_call = request.tool_call or {}
    trace_event(
        "agent.middleware.tool.before",
        tool_name=tool_call.get("name"),
        tool_args=tool_call.get("args"),
    )
    try:
        result = handler(request)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        trace_event(
            "agent.middleware.tool.error",
            tool_name=tool_call.get("name"),
            error=repr(exc),
        )
        raise

    trace_event(
        "agent.middleware.tool.after",
        tool_name=tool_call.get("name"),
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
        result_preview=str(result)[:1000],
    )
    return result


AGENT_MIDDLEWARE = [
    log_model_call,
    log_tool_call,
    ModelRetryMiddleware(max_retries=1),
    ToolRetryMiddleware(max_retries=1),
    ModelCallLimitMiddleware(run_limit=3, exit_behavior="end"),
    ToolCallLimitMiddleware(run_limit=3, exit_behavior="continue"),
]
