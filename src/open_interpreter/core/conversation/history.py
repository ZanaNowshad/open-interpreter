"""Conversation history persistence utilities."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Mapping, MutableMapping

Message = Mapping[str, object]
MutableMessage = MutableMapping[str, object]


@dataclass
class ConversationHistoryManager:
    """Coordinates persistence of conversations to disk."""

    storage_path_resolver: Callable[[str], str] | None = None

    def ensure_directory(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def _generate_filename(self, first_message: MutableMessage) -> str:
        content = str(first_message.get("content", ""))
        first_few_words_list = content[:25].split(" ")
        if len(first_few_words_list) >= 2:
            first_few_words = "_".join(first_few_words_list[:-1])
        else:
            first_few_words = content[:15]
        for char in '<>:"/\\|?*!\n':
            first_few_words = first_few_words.replace(char, "")

        date = datetime.now().strftime("%B_%d_%Y_%H-%M-%S")
        return "__".join([first_few_words, date]) + ".json"

    def persist(
        self,
        interpreter: object,
        messages: Iterable[Message],
    ) -> None:
        """Persist the provided conversation messages to disk."""

        if not getattr(interpreter, "conversation_history", False):
            return

        messages = list(messages)
        if not messages:
            return

        history_path = getattr(interpreter, "conversation_history_path", None)
        if not history_path and self.storage_path_resolver is not None:
            history_path = self.storage_path_resolver("conversations")
            setattr(interpreter, "conversation_history_path", history_path)

        if not history_path:
            return

        self.ensure_directory(history_path)

        filename = getattr(interpreter, "conversation_filename", None)
        if not filename:
            filename = self._generate_filename(messages[0].copy())
            setattr(interpreter, "conversation_filename", filename)

        with open(os.path.join(history_path, filename), "w", encoding="utf-8") as handle:
            json.dump(messages, handle)


__all__ = ["ConversationHistoryManager"]
