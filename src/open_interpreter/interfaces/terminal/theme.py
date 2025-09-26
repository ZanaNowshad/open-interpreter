"""Shared design tokens for the terminal interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TerminalTheme:
    """Design tokens that define terminal colours and accents."""

    syntax_theme: str = "monokai"
    syntax_theme_muted: str = "bw"
    code_background: str = "#272722"
    code_cursor: str = "#f8f8f2"
    console_background: str = "#3b3b37"
    console_text: str = "#ffffff"
    message_border: str = "#3b3b37"
    message_background: str = "#1f1f1b"
    message_text: str = "#f5f5f5"
    surface: str = "#11110f"
    accent: str = "#ffb454"
    chip_background: str = "#2f2f2a"
    chip_text: str = "#ffb454"
    chip_border: str = "#3b3b37"

    def to_css_variables(self) -> dict[str, str]:
        """Return a mapping of CSS variable names for Textual layouts."""

        return {
            "--oi-surface": self.surface,
            "--oi-accent": self.accent,
            "--oi-chip-bg": self.chip_background,
            "--oi-chip-fg": self.chip_text,
            "--oi-chip-border": self.chip_border,
            "--oi-message-bg": self.message_background,
            "--oi-message-fg": self.message_text,
            "--oi-message-border": self.message_border,
        }


TERMINAL_THEME = TerminalTheme()

__all__ = ["TerminalTheme", "TERMINAL_THEME"]
