"""Backward-compatible imports for the renamed core package."""

from __future__ import annotations

import importlib
import sys

_MODULES = ("database", "settings")

for _name in _MODULES:
    _module = importlib.import_module(f"core.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
