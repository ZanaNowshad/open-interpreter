"""Compatibility shim for the modular asynchronous interpreter."""

from __future__ import annotations

from open_interpreter.core.async_core import *  # noqa: F401,F403

__all__ = ["AsyncInterpreter"]
