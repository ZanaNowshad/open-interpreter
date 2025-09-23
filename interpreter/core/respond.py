"""Compatibility shim delegating to the modular execution loop."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Dict

from open_interpreter.core.execution.loop import respond as _modular_respond


def respond(interpreter) -> Generator[Dict[str, Any], None, None]:
    """Yield execution chunks via the modular execution loop."""

    yield from _modular_respond(interpreter)


__all__ = ["respond"]
