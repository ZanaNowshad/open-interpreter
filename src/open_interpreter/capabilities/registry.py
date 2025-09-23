"""Capability registry consolidating disparate tool metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass
class CapabilityDescriptor:
    """Metadata describing a capability or tool."""

    name: str
    provider: Any
    description: str = ""
    version: str = "1.0"
    permissions: Optional[Iterable[str]] = None


class CapabilityRegistry:
    """Central registry for discoverable capabilities."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDescriptor] = {}

    def register(self, descriptor: CapabilityDescriptor) -> None:
        self._capabilities[descriptor.name] = descriptor

    def register_tool(
        self,
        name: str,
        provider: Any,
        *,
        description: str = "",
        version: str = "1.0",
        permissions: Optional[Iterable[str]] = None,
    ) -> None:
        descriptor = CapabilityDescriptor(
            name=name,
            provider=provider,
            description=description,
            version=version,
            permissions=permissions,
        )
        self.register(descriptor)

    def get(self, name: str) -> CapabilityDescriptor:
        if name not in self._capabilities:
            raise KeyError(f"Capability '{name}' is not registered")
        return self._capabilities[name]

    def all(self) -> Dict[str, CapabilityDescriptor]:
        return dict(self._capabilities)


capability_registry = CapabilityRegistry()

__all__ = ["CapabilityDescriptor", "CapabilityRegistry", "capability_registry"]
