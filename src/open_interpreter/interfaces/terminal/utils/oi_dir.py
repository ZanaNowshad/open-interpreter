"""Compatibility shim exposing the interpreter configuration directory."""

from __future__ import annotations

from open_interpreter.infrastructure.storage import OI_CONFIG_DIR as oi_dir

__all__ = ["oi_dir"]
