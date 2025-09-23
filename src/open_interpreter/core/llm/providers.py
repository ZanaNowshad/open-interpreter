"""LLM service providers."""

from __future__ import annotations

from typing import Any

from .llm import Llm


def create_llm(interpreter: Any):
    """Construct the LLM wrapper."""

    return Llm(interpreter)


__all__ = ["create_llm"]
