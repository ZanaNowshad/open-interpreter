"""Canonical service identifiers used by the registry."""

class ServiceKeys:
    CONVERSATION_STATE = "conversation.state"
    CONVERSATION_HISTORY = "conversation.history"
    CONVERSATION_MANAGER = "conversation.manager"
    EXECUTION_ORCHESTRATOR = "execution.orchestrator"
    MESSAGE_RENDERER = "conversation.renderer"
    COMPUTER = "capability.computer"
    LLM = "llm.gateway"
    CAPABILITY_REGISTRY = "capabilities.registry"
    TELEMETRY = "telemetry.dispatch"


__all__ = ["ServiceKeys"]
