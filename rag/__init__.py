"""Backward-compatible imports for the renamed repositories package."""

from __future__ import annotations

import importlib
import sys

_MODULES = ("product_store", "qwen_embedding", "spu_loader")

for _name in _MODULES:
    _module = importlib.import_module(f"repositories.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
