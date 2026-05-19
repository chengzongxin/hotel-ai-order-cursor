import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypeVar


class ToolStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    FALLBACK = "fallback"


class ToolErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    FALLBACK_USED = "FALLBACK_USED"


JsonDict = dict[str, Any]
ToolResult = dict[str, Any]
T = TypeVar("T")


def success_response(data: JsonDict, message: str = "ok") -> ToolResult:
    return {
        "status": ToolStatus.SUCCESS,
        "error_code": None,
        "message": message,
        "data": data,
        "fallback": None,
    }


def error_response(error_code: ToolErrorCode, message: str, data: JsonDict | None = None) -> ToolResult:
    return {
        "status": ToolStatus.ERROR,
        "error_code": error_code,
        "message": message,
        "data": data or {},
        "fallback": None,
    }


def fallback_response(message: str, fallback: JsonDict, data: JsonDict | None = None) -> ToolResult:
    return {
        "status": ToolStatus.FALLBACK,
        "error_code": ToolErrorCode.FALLBACK_USED,
        "message": message,
        "data": data or {},
        "fallback": fallback,
    }


async def run_with_timeout(
    action: Callable[[], Awaitable[T]],
    timeout_seconds: float,
    fallback: Callable[[], ToolResult] | None = None,
) -> T | ToolResult:
    """统一处理 Tool 超时。

    action 是真正要执行的异步业务逻辑；如果超时，并且提供了 fallback，
    就返回 fallback 结果，否则返回标准错误 JSON。
    """

    try:
        return await asyncio.wait_for(action(), timeout=timeout_seconds)
    except TimeoutError:
        if fallback is not None:
            return fallback()
        return error_response(
            error_code=ToolErrorCode.TIMEOUT,
            message=f"tool execution timed out after {timeout_seconds} seconds",
        )
