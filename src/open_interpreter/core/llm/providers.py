"""LLM service providers."""

from __future__ import annotations

from typing import Any


def create_llm(interpreter: Any):
    """Construct the legacy LLM wrapper."""

    from interpreter.core.llm.llm import Llm  # Lazy import to avoid cycles

    return Llm(interpreter)


__all__ = ["create_llm"]
