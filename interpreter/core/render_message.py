"""Compatibility shim for the modular terminal renderer."""

from __future__ import annotations

from open_interpreter.interfaces.terminal.render import render_message as _render_message

__all__ = ["render_message"]


def render_message(interpreter, message):
    """Proxy to the modular renderer while preserving legacy imports."""

    return _render_message(interpreter, message)
