"""Backward-compatible imports for the renamed services package."""

from __future__ import annotations

import importlib
import sys

_MODULES = ("order_policy", "service_types")

for _name in _MODULES:
    _module = importlib.import_module(f"services.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
