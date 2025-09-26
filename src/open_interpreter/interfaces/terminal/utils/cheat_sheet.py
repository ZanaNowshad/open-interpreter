from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .shortcut_registry import shortcuts_for_contexts


def show_cheat_sheet(contexts: Iterable[str]) -> None:
    entries = shortcuts_for_contexts(contexts)
    console = Console()

    if not entries:
        console.print("[bold]No shortcuts available for this context.[/bold]")
        input("Press Enter to continue...")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Shortcut", style="bold")
    table.add_column("Description", style="white")
    table.add_column("Context", style="dim")

    for entry in entries:
        context_label = ", ".join(sorted(entry.contexts - {"global"})) or "Global"
        table.add_row(entry.keys, entry.description, context_label)

    panel = Panel(table, title="Shortcut Cheat Sheet", border_style="cyan")
    console.print(panel)
    input("Press Enter to return to the conversation...")
