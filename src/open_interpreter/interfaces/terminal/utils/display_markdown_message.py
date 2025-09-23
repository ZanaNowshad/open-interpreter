"""Compatibility shim for terminal markdown rendering."""

from __future__ import annotations

from open_interpreter.interfaces.terminal.display import (
    display_markdown_message as _display_markdown_message,
)

__all__ = ["display_markdown_message"]


def display_markdown_message(message):
    """Delegate to the modular terminal display helper."""

    return _display_markdown_message(message)
