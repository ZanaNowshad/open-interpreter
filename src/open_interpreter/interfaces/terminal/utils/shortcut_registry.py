from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set


@dataclass(frozen=True)
class ShortcutEntry:
    keys: str
    description: str
    contexts: Set[str]
    category: str = "General"
    command: str | None = None


SHORTCUT_REGISTRY: Sequence[ShortcutEntry] = (
    ShortcutEntry(
        keys="Ctrl+?",
        description="Show the shortcut cheat sheet",
        contexts={"global"},
        category="Navigation",
    ),
    ShortcutEntry(
        keys="%help",
        description="List magic commands",
        contexts={"global"},
        category="Commands",
        command="%help",
    ),
    ShortcutEntry(
        keys="%undo",
        description="Undo the last approval or message edit",
        contexts={"global", "history"},
        category="History",
        command="%undo",
    ),
    ShortcutEntry(
        keys="%redo",
        description="Redo the last undone approval or edit",
        contexts={"global", "history"},
        category="History",
        command="%redo",
    ),
    ShortcutEntry(
        keys="y / n / e",
        description="Approve, decline, or edit pending code",
        contexts={"approval"},
        category="Approvals",
    ),
    ShortcutEntry(
        keys="\"\"\"",
        description="Toggle multi-line input mode",
        contexts={"input"},
        category="Input",
    ),
    ShortcutEntry(
        keys="Ctrl+C",
        description="Cancel streaming or exit the prompt",
        contexts={"global"},
        category="Navigation",
    ),
    ShortcutEntry(
        keys="Ctrl+D",
        description="Exit when the prompt is empty",
        contexts={"input"},
        category="Navigation",
    ),
    ShortcutEntry(
        keys="%info",
        description="Show system and interpreter information",
        contexts={"global"},
        category="Commands",
        command="%info",
    ),
)


def resolve_contexts(interpreter, *extra: str) -> Set[str]:
    contexts: Set[str] = {"global"}
    contexts.update(extra)
    if getattr(interpreter, "os", False):
        contexts.add("os")
    if getattr(getattr(interpreter, "llm", None), "supports_vision", False):
        contexts.add("vision")
    return contexts


def shortcuts_for_contexts(contexts: Iterable[str]) -> List[ShortcutEntry]:
    context_set = set(contexts)
    results: List[ShortcutEntry] = []
    for entry in SHORTCUT_REGISTRY:
        if entry.contexts & context_set:
            results.append(entry)
    return sorted(results, key=lambda item: (item.category, item.keys))


# Placeholder exported name for future command palette reuse.
COMMAND_PALETTE_ITEMS = SHORTCUT_REGISTRY
