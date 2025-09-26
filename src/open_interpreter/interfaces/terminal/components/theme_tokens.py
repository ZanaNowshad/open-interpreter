"""Accessible theme tokens for terminal UI components.

The legacy terminal interface does not rely on a global theming system, which
made it difficult to guarantee accessible colour contrast.  This module
introduces a minimal token-based theme catalogue that individual components can
consume to ensure consistent styling.  The palettes here were manually checked
against the WCAG 2.2 AA contrast ratio requirements using colour contrast tools
outside of the codebase.

Two additional variants are provided:

``dyslexia``
    Uses off-white backgrounds, dark navy foreground text, and toned-down
    accent colours chosen to reduce visual crowding and letter swapping.

``monochrome``
    High-contrast greyscale palette that avoids any reliance on colour to
    convey information.

Components can resolve tokens through :func:`get_theme`, which accepts either a
``ThemeTokens`` instance or a case-insensitive string key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping


@dataclass(frozen=True)
class ThemeTokens:
    """Container for style primitives consumed by terminal components."""

    name: str
    message_panel_style: str
    message_border_style: str
    message_text_style: str
    focus_border_style: str
    code_panel_style: str
    code_border_style: str
    code_output_style: str
    code_active_line_style: str
    code_active_line_theme: str
    code_default_theme: str
    skip_link_style: str


def _build_themes() -> Mapping[str, ThemeTokens]:
    """Create the built-in theme catalogue."""

    default = ThemeTokens(
        name="default",
        message_panel_style="on #0b0d17",
        message_border_style="#58a6ff",
        message_text_style="#f7fafc",
        focus_border_style="#ffd166",
        code_panel_style="on #050608",
        code_border_style="#58a6ff",
        code_output_style="#050608 on #f7fafc",
        code_active_line_style="#050608 on #f1fa8c",
        code_active_line_theme="stata-dark",
        code_default_theme="material",
        skip_link_style="bold #050608 on #ffd166",
    )

    dyslexia = ThemeTokens(
        name="dyslexia",
        message_panel_style="on #fef7e0",
        message_border_style="#1d3557",
        message_text_style="#1d3557",
        focus_border_style="#e76f51",
        code_panel_style="on #fefaf0",
        code_border_style="#1d3557",
        code_output_style="#1d3557 on #f1faee",
        code_active_line_style="#1d3557 on #ffd166",
        code_active_line_theme="solarized-light",
        code_default_theme="github-light",
        skip_link_style="bold #1d3557 on #f4a261",
    )

    monochrome = ThemeTokens(
        name="monochrome",
        message_panel_style="on #0f0f0f",
        message_border_style="#d1d5db",
        message_text_style="#f9fafb",
        focus_border_style="#f9fafb",
        code_panel_style="on #000000",
        code_border_style="#d1d5db",
        code_output_style="#111827 on #f9fafb",
        code_active_line_style="#111827 on #e5e7eb",
        code_active_line_theme="bw",
        code_default_theme="bw",
        skip_link_style="bold #000000 on #e5e7eb",
    )

    return {
        default.name: default,
        dyslexia.name: dyslexia,
        monochrome.name: monochrome,
    }


THEMES: Dict[str, ThemeTokens] = dict(_build_themes())


def available_themes() -> Iterable[str]:
    """Return the available theme identifiers."""

    return THEMES.keys()


def get_theme(theme: str | ThemeTokens | None) -> ThemeTokens:
    """Resolve a user-specified theme value into concrete tokens.

    Parameters
    ----------
    theme:
        Either a :class:`ThemeTokens` instance or a case-insensitive string key.
        ``None`` falls back to the ``default`` theme.
    """

    if isinstance(theme, ThemeTokens):
        return theme

    if theme is None:
        theme_key = "default"
    else:
        theme_key = str(theme).lower()

    if theme_key not in THEMES:
        raise KeyError(f"Unknown theme '{theme_key}'. Available: {', '.join(THEMES)}")

    return THEMES[theme_key]


__all__ = ["ThemeTokens", "THEMES", "available_themes", "get_theme"]

