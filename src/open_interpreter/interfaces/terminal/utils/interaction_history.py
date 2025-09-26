from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class HistoryAction:
    action_type: str
    description: str
    before: List[dict]
    after: List[dict]
    severity: str = "info"
    allow_update: bool = False


class SessionHistory:
    """Manage undo/redo stacks for terminal interactions."""

    def __init__(self):
        self._undo_stack: List[HistoryAction] = []
        self._redo_stack: List[HistoryAction] = []
        self._needs_update: bool = False

    def record_action(
        self,
        *,
        action_type: str,
        description: str,
        before: List[dict],
        after: List[dict],
        severity: str = "info",
        allow_future_updates: bool = False,
    ) -> HistoryAction:
        action = HistoryAction(
            action_type=action_type,
            description=description,
            before=deepcopy(before),
            after=deepcopy(after),
            severity=severity,
            allow_update=allow_future_updates,
        )
        self._undo_stack.append(action)
        self._redo_stack.clear()
        self._needs_update = allow_future_updates
        return action

    def update_latest(self, messages: List[dict]) -> None:
        if self._needs_update and self._undo_stack:
            self._undo_stack[-1].after = deepcopy(messages)

    def finalize_latest(self) -> None:
        self._needs_update = False
        if self._undo_stack:
            self._undo_stack[-1].allow_update = False

    def undo(self, interpreter) -> Optional[HistoryAction]:
        if not self._undo_stack:
            return None
        action = self._undo_stack.pop()
        interpreter.messages = deepcopy(action.before)
        self._redo_stack.append(action)
        self._needs_update = False
        return action

    def redo(self, interpreter) -> Optional[HistoryAction]:
        if not self._redo_stack:
            return None
        action = self._redo_stack.pop()
        interpreter.messages = deepcopy(action.after)
        self._undo_stack.append(action)
        self._needs_update = False
        return action

    @property
    def has_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def has_redo(self) -> bool:
        return bool(self._redo_stack)
