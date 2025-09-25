"""Runtime service registry used to orchestrate interpreter dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, Iterable, Tuple

Provider = Callable[..., Any]


@dataclass(frozen=True)
class _ProviderSpec:
    provider: Provider
    singleton: bool = False


class ServiceRegistry:
    """Light-weight dependency injection container.

    The registry stores callables that construct services on demand. Providers
    can be registered either as factories (default) or as singletons. The
    registry is intentionally minimalistic but powerful enough to coordinate
    the new modular architecture without introducing an external dependency.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, _ProviderSpec] = {}
        self._singletons: Dict[str, Any] = {}
        self._lock = RLock()

    def register(
        self,
        name: str,
        provider: Provider,
        *,
        singleton: bool = False,
        override: bool = False,
    ) -> None:
        """Register a provider.

        Args:
            name: Canonical service identifier.
            provider: Callable returning an instance of the service.
            singleton: Whether the service should be cached after the first
                creation.
            override: Whether existing providers can be replaced.
        """

        with self._lock:
            if not override and name in self._providers:
                raise ValueError(f"Service '{name}' is already registered")

            self._providers[name] = _ProviderSpec(provider=provider, singleton=singleton)
            if override:
                self._singletons.pop(name, None)

    def override(
        self,
        name: str,
        provider: Provider,
        *,
        singleton: bool = False,
    ) -> None:
        """Replace an existing provider."""

        self.register(name, provider, singleton=singleton, override=True)

    def unregister(self, name: str) -> None:
        """Remove a provider from the registry."""

        with self._lock:
            self._providers.pop(name, None)
            self._singletons.pop(name, None)

    def get(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Return an instance from the registry."""

        with self._lock:
            if name not in self._providers:
                raise KeyError(f"Service '{name}' is not registered")

            spec = self._providers[name]

        if spec.singleton:
            with self._lock:
                if name not in self._singletons:
                    self._singletons[name] = spec.provider(*args, **kwargs)
                return self._singletons[name]

        return spec.provider(*args, **kwargs)

    def ensure(self, names: Iterable[str]) -> None:
        """Validate that multiple services are available."""

        missing = [name for name in names if name not in self._providers]
        if missing:
            raise KeyError(f"Missing service registrations: {', '.join(missing)}")

    def available_services(self) -> Tuple[str, ...]:
        """Return a snapshot of all registered service names."""

        with self._lock:
            return tuple(sorted(self._providers.keys()))

    def copy(self, *, include_singletons: bool = True) -> "ServiceRegistry":
        """Create a shallow copy of the registry configuration."""

        clone = ServiceRegistry()
        with self._lock:
            clone._providers = dict(self._providers)
            if include_singletons:
                clone._singletons = dict(self._singletons)
        return clone

    @contextmanager
    def temporary_override(
        self,
        overrides: Mapping[str, Provider | Tuple[Provider, bool]],
    ):
        """Temporarily override providers within a context manager."""

        normalized: Dict[str, _ProviderSpec] = {}
        for name, value in overrides.items():
            if isinstance(value, tuple):
                provider, singleton = value
            else:
                provider, singleton = value, False
            normalized[name] = _ProviderSpec(provider=provider, singleton=singleton)

        with self._lock:
            previous: Dict[str, _ProviderSpec | None] = {
                name: self._providers.get(name) for name in normalized
            }
            previous_singletons = {name: self._singletons.pop(name, None) for name in normalized}
            self._providers.update(normalized)

        try:
            yield
        finally:
            with self._lock:
                for name, spec in normalized.items():
                    original = previous[name]
                    if original is None:
                        self._providers.pop(name, None)
                    else:
                        self._providers[name] = original
                    if previous_singletons[name] is not None:
                        self._singletons[name] = previous_singletons[name]
                    else:
                        self._singletons.pop(name, None)


__all__ = ["ServiceRegistry"]
