"""Compatibility shim for telemetry helpers."""

from __future__ import annotations

from open_interpreter.core.telemetry.sender import (  # noqa: F401
    get_or_create_uuid,
    send_telemetry,
    user_id,
)

__all__ = ["get_or_create_uuid", "send_telemetry", "user_id"]
