"""Modular architecture for Open Interpreter."""

from .services.defaults import bootstrap_registry, get_global_registry
from .services.keys import ServiceKeys

__all__ = [
    "bootstrap_registry",
    "get_global_registry",
    "ServiceKeys",
]
