from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from core.settings import settings
from utils.path_tools import get_abs_path

LOG_ROOT = get_abs_path("logs")
os.makedirs(LOG_ROOT, exist_ok=True)

DEFAULT_LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def mask_sensitive_data(text: str) -> str:
    if not isinstance(text, str):
        return text

    text = re.sub(r"sk-\w+", "sk-******", text)
    text = re.sub(r"1[3-9]\d{9}", "1**********", text)
    text = re.sub(r"(\w+)@(\w+)\.(\w+)", r"\1****@\2.\3", text)
    text = re.sub(r"(password|key|secret)=[^& ]+", r"\1=******", text)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            record.args = tuple(mask_sensitive_data(str(arg)) for arg in record.args)
        return True


def get_logger(
    name: str = "agent",
    console_level: int | None = None,
    file_level: int = logging.DEBUG,
    log_file: Optional[str] = None,
) -> logging.Logger:
    resolved_console_level = console_level
    if resolved_console_level is None:
        resolved_console_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.addFilter(SensitiveDataFilter())

    if log.handlers:
        return log

    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    log.addHandler(console_handler)

    if not log_file:
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    log.addHandler(file_handler)

    return log


class TraceLogger:
    """结构化追踪日志：trace_logger("event.name", key=value, ...)"""

    def __init__(self, name: str = "agent.trace") -> None:
        self._logger = get_logger(name)
        self.disabled = not settings.debug_trace_enabled

    def __call__(self, event: str, **payload: Any) -> None:
        if self.disabled:
            return
        self._logger.info(
            "%s %s",
            event,
            json.dumps(payload, ensure_ascii=False, default=str),
        )


logger = get_logger("agent")
trace_logger = TraceLogger()
