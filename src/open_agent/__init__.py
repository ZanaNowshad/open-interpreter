"""Agent naming facade for the Open Interpreter runtime."""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Iterable

from open_interpreter import (
    AsyncInterpreter,
    OpenInterpreter,
    bootstrap_registry,
    get_global_registry,
    ServiceKeys,
)

from .runtime import AsyncAgent, OpenAgent, agent, computer

# Sub-packages exposed by ``open_interpreter`` that we mirror for the
# ``open_agent`` namespace. Importing them eagerly ensures ``import
# open_agent.<module>`` behaves exactly the same as the interpreter naming
# scheme while we complete the terminology migration.
_ALIAS_PACKAGES: tuple[str, ...] = (
    "capabilities",
    "core",
    "infrastructure",
    "interfaces",
    "platform",
    "services",
)


def _install_aliases(packages: Iterable[str]) -> None:
    """Register alias modules so the Agent namespace mirrors Interpreter."""

    for package in packages:
        new_name = f"{__name__}.{package}"
        if new_name in sys.modules:
            # The alias might already exist when running in reload scenarios.
            continue

        module = import_module(f"open_interpreter.{package}")
        sys.modules[new_name] = module


_install_aliases(_ALIAS_PACKAGES)

__all__ = [
    "OpenAgent",
    "AsyncAgent",
    "agent",
    "computer",
    "bootstrap_registry",
    "get_global_registry",
    "ServiceKeys",
    "OpenInterpreter",
    "AsyncInterpreter",
]
