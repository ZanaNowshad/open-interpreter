"""Terminal display helpers for the modular interface layer."""

from __future__ import annotations

from rich import print as rich_print
from rich.markdown import Markdown
from rich.rule import Rule


def display_markdown_message(message: str) -> None:
    """Render a markdown message using ``rich`` with legacy semantics."""

    for line in message.split("\n"):
        line = line.strip()
        if line == "":
            print("")
        elif line == "---":
            rich_print(Rule(style="white"))
        else:
            try:
                rich_print(Markdown(line))
            except UnicodeEncodeError:
                print("Error displaying line:", line)

    if "\n" not in message and message.startswith(">"):
        print("")


__all__ = ["display_markdown_message"]
