"""Runtime entrypoints for the Agent naming facade."""

from __future__ import annotations

from open_interpreter.runtime import (
    AsyncInterpreter,
    OpenInterpreter,
    computer as _computer,
    interpreter as _interpreter,
)

AsyncAgent = AsyncInterpreter
OpenAgent = OpenInterpreter

# ``open_interpreter`` exposes module-level singletons. Re-export them so the
# agent terminology stays in lock-step with the existing runtime behaviour.
agent = _interpreter
computer = _computer

__all__ = ["OpenAgent", "AsyncAgent", "agent", "computer"]
