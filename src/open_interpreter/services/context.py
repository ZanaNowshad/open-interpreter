"""Typed runtime context utilities for service resolution."""

from __future__ import annotations

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
) -> ServiceContext:
    """Construct a :class:`ServiceContext` from the registry."""

    resolved_registry = bootstrap_registry(registry)

    state = resolved_registry.get(ServiceKeys.CONVERSATION_STATE)
    history = resolved_registry.get(ServiceKeys.CONVERSATION_HISTORY)
    renderer = message_renderer or resolved_registry.get(
        ServiceKeys.MESSAGE_RENDERER, interpreter=interpreter
    )
    manager = resolved_registry.get(
        ServiceKeys.CONVERSATION_MANAGER,
        state=state,
        history=history,
        renderer=renderer,
    )
    execution = resolved_registry.get(
        ServiceKeys.EXECUTION_ORCHESTRATOR, interpreter=interpreter
    )
    capability_store = resolved_registry.get(ServiceKeys.CAPABILITY_REGISTRY)
    telemetry = resolved_registry.get(ServiceKeys.TELEMETRY, interpreter=interpreter)

    computer_service = computer or resolved_registry.get(
        ServiceKeys.COMPUTER, interpreter=interpreter
    )
    llm_service = llm or resolved_registry.get(
        ServiceKeys.LLM, interpreter=interpreter
    )

    return ServiceContext(
        registry=resolved_registry,
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
