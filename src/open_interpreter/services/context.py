"""Typed runtime context utilities for service resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Callable

from .defaults import bootstrap_registry
from .keys import ServiceKeys
from .registry import ServiceRegistry
from ..capabilities import CapabilityRegistry
from ..core.conversation import (
    ConversationHistoryManager,
    ConversationManager,
    ConversationState,
)
from ..core.execution import ExecutionOrchestrator
from ..core.telemetry import TelemetryDispatcher


@dataclass(frozen=True)
class ServiceContext:
    """Aggregated view of the interpreter runtime services."""

    registry: ServiceRegistry
    conversation_state: ConversationState
    conversation_history: ConversationHistoryManager
    conversation_manager: ConversationManager
    execution: ExecutionOrchestrator
    message_renderer: Callable[..., Any]
    computer: Any
    llm: Any
    capability_registry: CapabilityRegistry
    telemetry: TelemetryDispatcher | Callable[..., Any]

    def clone(self, **overrides: Any) -> "ServiceContext":
        """Create a modified copy of the context."""

        return replace(self, **overrides)


def build_service_context(
    *,
    interpreter: Any,
    registry: ServiceRegistry | None = None,
    computer: Any | None = None,
    llm: Any | None = None,
    message_renderer: Callable[..., Any] | None = None,
    overrides: Mapping[
        str, Callable[..., Any] | tuple[Callable[..., Any], bool]
    ]
    | None = None,
) -> ServiceContext:
    """Construct a :class:`ServiceContext` from the registry."""

    resolved_registry = bootstrap_registry(registry)
    active_registry = resolved_registry

    if overrides:
        if registry is None:
            active_registry = resolved_registry.copy()

        for name, provider in overrides.items():
            if isinstance(provider, tuple):
                override_provider, singleton = provider
            else:
                override_provider, singleton = provider, False

            active_registry.override(
                name,
                override_provider,
                singleton=singleton,
            )

    state = active_registry.get(ServiceKeys.CONVERSATION_STATE)
    history = active_registry.get(ServiceKeys.CONVERSATION_HISTORY)
    renderer = message_renderer or active_registry.get(
        ServiceKeys.MESSAGE_RENDERER, interpreter=interpreter
    )
    manager = active_registry.get(
        ServiceKeys.CONVERSATION_MANAGER,
        state=state,
        history=history,
        renderer=renderer,
    )
    execution = active_registry.get(
        ServiceKeys.EXECUTION_ORCHESTRATOR, interpreter=interpreter
    )
    capability_store = active_registry.get(ServiceKeys.CAPABILITY_REGISTRY)
    telemetry = active_registry.get(ServiceKeys.TELEMETRY, interpreter=interpreter)

    computer_service = computer or active_registry.get(
        ServiceKeys.COMPUTER, interpreter=interpreter
    )
    llm_service = llm or active_registry.get(
        ServiceKeys.LLM, interpreter=interpreter
    )

    return ServiceContext(
        registry=active_registry,
        conversation_state=state,
        conversation_history=history,
        conversation_manager=manager,
        execution=execution,
        message_renderer=renderer,
        computer=computer_service,
        llm=llm_service,
        capability_registry=capability_store,
        telemetry=telemetry,
    )


__all__ = ["ServiceContext", "build_service_context"]
