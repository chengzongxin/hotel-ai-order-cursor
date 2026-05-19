import json
import logging
from typing import Any

from config.settings import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def trace_event(event: str, **payload: Any) -> None:
    if not settings.debug_trace_enabled:
        return

    logging.getLogger("agent.trace").info(
        "%s %s",
        event,
        json.dumps(payload, ensure_ascii=False, default=str),
    )
