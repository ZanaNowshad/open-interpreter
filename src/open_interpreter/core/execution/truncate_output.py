"""Utilities for managing execution output."""

from __future__ import annotations

__all__ = ["truncate_output"]


def truncate_output(data: str, max_output_chars: int = 2800, add_scrollbars: bool = False) -> str:
    """Truncate console output to a maximum length."""

    needs_truncation = False

    message = (
        f"Output truncated. Showing the last {max_output_chars} characters. "
        "You should try again and use computer.ai.summarize(output) over the output, "
        "or break it down into smaller steps.\n\n"
    )

    if add_scrollbars:
        message = (
            message.strip()
            + f" Run `get_last_output()[0:{max_output_chars}]` to see the first page.\n\n"
        )

    if data.startswith(message):
        data = data[len(message) :]
        needs_truncation = True

    if len(data) > max_output_chars or needs_truncation:
        data = message + data[-max_output_chars:]

    return data
