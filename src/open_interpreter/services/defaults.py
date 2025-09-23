"""Default service wiring for the modular architecture."""

from __future__ import annotations

from typing import Any, Callable, Optional

from .keys import ServiceKeys
from .registry import ServiceRegistry
from ..capabilities import capability_registry
from ..core.conversation import (
    ConversationHistoryManager,
    ConversationManager,
    ConversationState,
)
from ..core.execution import ExecutionOrchestrator
from ..core.llm import create_llm
from ..core.telemetry import TelemetryDispatcher

_global_registry = ServiceRegistry()
_bootstrapped = False


def _register_if_missing(
    registry: ServiceRegistry,
    name: str,
    provider: Callable[..., Any],
    *,
    singleton: bool = False,
) -> None:
    try:
        registry.register(name, provider, singleton=singleton)
    except ValueError:
        # Respect existing customisations.
        pass


def _create_computer(interpreter: Any):
    from open_interpreter.core.computer.computer import Computer

    return Computer(interpreter)


def _create_execution_orchestrator(interpreter: Any):
    from open_interpreter.core.execution.loop import respond

    return ExecutionOrchestrator(responder=respond)


def _create_renderer(interpreter: Any | None = None):  # noqa: D401 - signature parity
    from open_interpreter.interfaces.terminal.render import render_message

    return render_message


def _create_history_manager():
    from open_interpreter.infrastructure.storage import get_storage_path

    return ConversationHistoryManager(storage_path_resolver=get_storage_path)


def _create_conversation_manager(
    *,
    state: ConversationState,
    history: ConversationHistoryManager,
    renderer: Callable[..., Any] | None = None,
) -> ConversationManager:
    manager = ConversationManager(state=state, history_manager=history)
    if renderer is not None:
        manager.attach_renderer(renderer)
    return manager


def _create_telemetry_dispatcher(interpreter: Any | None = None):
    from open_interpreter.core.telemetry.sender import send_telemetry

    return TelemetryDispatcher(send_telemetry)


def _register_defaults(registry: ServiceRegistry) -> None:
    _register_if_missing(
        registry,
        ServiceKeys.CAPABILITY_REGISTRY,
        lambda: capability_registry,
        singleton=True,
    )
    _register_if_missing(registry, ServiceKeys.CONVERSATION_STATE, lambda: ConversationState())
    _register_if_missing(registry, ServiceKeys.CONVERSATION_HISTORY, _create_history_manager, singleton=True)
    _register_if_missing(registry, ServiceKeys.CONVERSATION_MANAGER, _create_conversation_manager)
    _register_if_missing(registry, ServiceKeys.EXECUTION_ORCHESTRATOR, _create_execution_orchestrator)
    _register_if_missing(registry, ServiceKeys.MESSAGE_RENDERER, _create_renderer)
    _register_if_missing(registry, ServiceKeys.COMPUTER, _create_computer)
    _register_if_missing(registry, ServiceKeys.LLM, create_llm)
    _register_if_missing(registry, ServiceKeys.TELEMETRY, _create_telemetry_dispatcher)


def bootstrap_registry(registry: Optional[ServiceRegistry] = None) -> ServiceRegistry:
    """Ensure the default registry is configured and return it."""

    global _bootstrapped

    target = registry or _global_registry
    if target is _global_registry and _bootstrapped:
        return target

    _register_defaults(target)

    if target is _global_registry:
        _bootstrapped = True

    return target


def get_global_registry() -> ServiceRegistry:
    """Return the singleton registry configured with default providers."""

    return bootstrap_registry(_global_registry)


__all__ = ["bootstrap_registry", "get_global_registry"]
