"""Execution orchestration bridging the legacy respond loop."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Callable, Dict


class ExecutionOrchestrator:
    """Wraps the legacy ``respond`` generator behind a service interface."""

    def __init__(self, responder: Callable[[Any], Generator[Dict[str, Any], None, None]]) -> None:
        self._responder = responder

    def stream(self, interpreter: Any):
        """Yield execution chunks for the provided interpreter."""

        yield from self._responder(interpreter)


__all__ = ["ExecutionOrchestrator"]
