"""Backward-compatible imports for the renamed workflow package."""

from __future__ import annotations

import importlib
import sys

_MODULES = (
    "agent",
    "builder",
    "checkpoint",
    "confirmation_policy",
    "constants",
    "coverage_policy",
    "expected_time",
    "intent_policy",
    "llm",
    "llm_callbacks",
    "messages",
    "middleware",
    "order_context_loader",
    "order_defaults",
    "order_fields",
    "order_validation_policy",
    "preview",
    "products",
    "prompts",
    "questions",
    "routes",
    "session_access",
    "session_actions",
    "state",
    "streaming",
    "studio",
    "submission",
    "text_parsing",
)

for _name in _MODULES:
    _module = importlib.import_module(f"workflow.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
