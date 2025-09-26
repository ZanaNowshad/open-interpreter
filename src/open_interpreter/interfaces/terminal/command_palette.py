"""Interactive command palette utilities for the terminal interface."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from .profiles.profiles import list_available_profiles, profile
from .utils.cli_overrides import apply_cli_overrides
from .utils.session_header import display_session_header

console = Console()


def open_command_palette(interpreter: Any) -> None:
    """Launch the command palette for runtime actions."""

    if not getattr(interpreter, "_command_palette_enabled", True):
        console.print("\n[yellow]Command palette is not available in this mode.[/yellow]\n")
        return

    options = [
        ("Switch profile", _handle_switch_profile),
        ("Show active profile", _handle_show_profile),
        ("Cancel", None),
    ]

    console.print("\n[bold cyan]Command Palette[/bold cyan]")
    table = Table(show_header=False, box=None, padding=(0, 1))

    for index, (label, _) in enumerate(options, start=1):
        table.add_row(f"[cyan]{index}[/cyan]", label)

    console.print(table)

    valid_choices = [str(index) for index in range(1, len(options) + 1)] + ["q"]
    selection = Prompt.ask("Select an action", choices=valid_choices, default="q")

    if selection == "q":
        console.print("")
        return

    handler = options[int(selection) - 1][1]
    if handler:
        handler(interpreter)

    console.print("")


def _handle_switch_profile(interpreter: Any) -> None:
    profiles = list_available_profiles()
    if not profiles:
        console.print("[yellow]No profiles were found to switch to.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Profile")
    table.add_column("Source", style="dim")
    table.add_column("Format", style="dim")

    for index, item in enumerate(profiles, start=1):
        source = item.get("source", "unknown")
        table.add_row(
            str(index),
            item.get("name", ""),
            source,
            item.get("format", ""),
        )

    console.print(table)

    valid_choices = [str(index) for index in range(1, len(profiles) + 1)] + ["q"]
    selection = Prompt.ask("Switch to", choices=valid_choices, default="q")

    if selection == "q":
        return

    chosen_profile = profiles[int(selection) - 1]
    profile(interpreter, chosen_profile["identifier"])
    apply_cli_overrides(interpreter)
    console.print(
        Text(
            f"Switched to profile '{chosen_profile['name']}'",
            style="green",
        )
    )
    display_session_header(interpreter)


def _handle_show_profile(interpreter: Any) -> None:
    display_session_header(interpreter)
