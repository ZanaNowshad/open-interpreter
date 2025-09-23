"""Telemetry dispatch abstractions."""

from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping


class TelemetryDispatcher:
    """Facade around the legacy telemetry sender.

    The dispatcher normalises access to the underlying ``send_telemetry``
    helper used throughout the legacy codebase while fitting the
    registry-oriented architecture.  It behaves as a callable for
    backwards compatibility but also exposes an explicit :meth:`send`
    helper for clarity inside the new modules.
    """

    def __init__(self, sender: Callable[[str, MutableMapping[str, Any] | None], Any]) -> None:
        self._sender = sender

    def send(self, event: str, *, properties: Mapping[str, Any] | None = None) -> Any:
        """Dispatch an event to the underlying telemetry implementation."""

        # ``send_telemetry`` mutates the provided mapping in place by adding the
        # project version, so we coerce the mapping to a mutable structure when
        # needed to preserve that behaviour.
        payload: MutableMapping[str, Any] | None
        if properties is None or isinstance(properties, MutableMapping):
            payload = properties
        else:
            payload = dict(properties)
        return self._sender(event, payload)

    def __call__(self, event: str, *, properties: Mapping[str, Any] | None = None) -> Any:
        """Allow instances to be used as plain callables."""

        return self.send(event, properties=properties)

    @property
    def sender(self) -> Callable[[str, MutableMapping[str, Any] | None], Any]:
        """Expose the wrapped callable for advanced scenarios."""

        return self._sender


__all__ = ["TelemetryDispatcher"]
