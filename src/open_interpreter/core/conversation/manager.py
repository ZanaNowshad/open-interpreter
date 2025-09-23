"""Conversation management service coordinating state and history."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Mapping

from .history import ConversationHistoryManager
from .state import ConversationState

Message = Mapping[str, Any]


class ConversationManager:
    """Facade around conversation state, history, and rendering concerns."""

    def __init__(
        self,
        *,
        state: ConversationState,
        history_manager: ConversationHistoryManager,
        renderer: Callable[..., Any] | None = None,
    ) -> None:
        self._state = state
        self._history_manager = history_manager
        self._renderer = renderer

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------
    @property
    def messages(self) -> List[Mapping[str, Any]]:
        """Return the current message list."""

        return self._state.messages

    @messages.setter
    def messages(self, value: Iterable[Message]) -> None:
        self._state.update_messages(value)

    def append(self, message: Message) -> None:
        """Append a new message to the state."""

        self._state.append_message(message)

    def extend(self, messages: Iterable[Message]) -> None:
        """Extend the state with multiple messages."""

        self._state.extend_messages(messages)

    @property
    def responding(self) -> bool:
        """Return whether the interpreter is currently responding."""

        return self._state.responding

    @responding.setter
    def responding(self, value: bool) -> None:
        self._state.responding = bool(value)

    @property
    def last_messages_count(self) -> int:
        """Return the index of the last acknowledged message."""

        return self._state.last_messages_count

    @last_messages_count.setter
    def last_messages_count(self, value: int) -> None:
        self._state.last_messages_count = int(value)

    def mark_checkpoint(self) -> None:
        """Store the current message count for delta retrieval."""

        self._state.last_messages_count = len(self._state.messages)

    def new_messages(self) -> List[Mapping[str, Any]]:
        """Return messages added after the last checkpoint."""

        start = self._state.last_messages_count
        return self._state.messages[start:]

    def reset(self) -> None:
        """Reset the underlying conversation state."""

        self._state.reset()

    # ------------------------------------------------------------------
    # History / rendering coordination
    # ------------------------------------------------------------------
    def persist_history(self, interpreter: object) -> None:
        """Persist conversation history using the configured history manager."""

        self._history_manager.persist(interpreter, self._state.messages)

    def attach_renderer(self, renderer: Callable[..., Any]) -> None:
        """Attach a renderer used for formatting messages."""

        self._renderer = renderer

    def render(self, *args: Any, **kwargs: Any) -> Any:
        """Render a message via the configured renderer."""

        if self._renderer is None:
            raise RuntimeError("No message renderer configured")
        return self._renderer(*args, **kwargs)


__all__ = ["ConversationManager"]
