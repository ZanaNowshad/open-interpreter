"""Shared Markdown rendering helpers used by terminal UI and docs tooling."""

from __future__ import annotations

import re

from rich.markdown import Markdown

__all__ = [
    "normalize_markdown_code_blocks",
    "render_markdown",
    "render_markdown_text",
]


_CODE_BLOCK_PATTERN = re.compile(r"^```(\w*)$")


def normalize_markdown_code_blocks(text: str) -> str:
    """Normalise fenced code blocks to ``text`` for consistent theming."""

    replacement = "```text"
    lines = text.split("\n")
    inside_code_block = False

    for index, line in enumerate(lines):
        if _CODE_BLOCK_PATTERN.match(line.strip()):
            inside_code_block = not inside_code_block
            if inside_code_block:
                lines[index] = replacement

    return "\n".join(lines)


def render_markdown_text(message: str, *, cursor: bool = False) -> str:
    """Return themed Markdown text ready for rendering."""

    content = normalize_markdown_code_blocks(message)
    if cursor:
        content += "●"
    return content.strip()


def render_markdown(message: str, *, cursor: bool = False) -> Markdown:
    """Return a ``rich`` Markdown object for the provided message."""

    return Markdown(render_markdown_text(message, cursor=cursor))
