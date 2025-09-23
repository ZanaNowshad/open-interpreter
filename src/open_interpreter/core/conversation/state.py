"""Conversation state abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ConversationState:
    """Represents the mutable state of a conversation."""

    messages: List[Dict[str, Any]] = field(default_factory=list)
    responding: bool = False
    last_messages_count: int = 0

    def reset(self) -> None:
        self.messages = []
        self.responding = False
        self.last_messages_count = 0

    def update_messages(self, messages: Iterable[Dict[str, Any]]) -> None:
        self.messages = list(messages)
        self.last_messages_count = len(self.messages)

    def append_message(self, message: Dict[str, Any]) -> None:
        self.messages.append(message)

    def extend_messages(self, messages: Iterable[Dict[str, Any]]) -> None:
        self.messages.extend(messages)


__all__ = ["ConversationState"]
