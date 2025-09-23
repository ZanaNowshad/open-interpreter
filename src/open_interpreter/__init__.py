"""Modular architecture for Open Interpreter."""

from .runtime import AsyncInterpreter, OpenInterpreter, computer, interpreter
from .services.defaults import bootstrap_registry, get_global_registry
from .services.keys import ServiceKeys

__all__ = [
    "AsyncInterpreter",
    "OpenInterpreter",
    "bootstrap_registry",
    "computer",
    "get_global_registry",
    "interpreter",
    "ServiceKeys",
]
