"""Runtime entrypoints for Open Interpreter."""

from __future__ import annotations

from open_interpreter.core.async_core import AsyncInterpreter
from open_interpreter.core.runtime import OpenInterpreter

__all__ = ["OpenInterpreter", "AsyncInterpreter", "interpreter", "computer"]

interpreter = OpenInterpreter()
computer = interpreter.computer
