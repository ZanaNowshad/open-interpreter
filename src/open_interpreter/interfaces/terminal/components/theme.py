"""Shared visual tokens for the terminal interface components.

The palette is inspired by Material 3's dark theme so that code and
message blocks share a consistent visual language regardless of where
they are rendered.
"""
from __future__ import annotations

from typing import Dict

MATERIAL_TOKENS: Dict[str, str] = {
    "surface": "#1C1B1F",
    "surface_variant": "#2A2734",
    "on_surface": "#E6E1E5",
    "on_surface_variant": "#CAC4D0",
    "outline": "#49454F",
    "outline_variant": "#625B71",
    "primary": "#D0BCFF",
    "on_primary": "#381E72",
    "code_surface": "#1F1A2B",
    "code_border": "#4A4458",
    "output_surface": "#221F2F",
    "output_border": "#4A4458",
    "accent": "#D0BCFF",
    "warning": "#F2B8B5",
    "info": "#80CBC4",
    "success": "#C5E1A5",
}

MATERIAL_SYNTAX_THEME = "material"

STANDARD_MARGIN = (1, 0, 0, 0)


_CALLOUT_COLOR_MAP = {
    "note": MATERIAL_TOKENS["accent"],
    "info": MATERIAL_TOKENS["info"],
    "tip": MATERIAL_TOKENS["success"],
    "success": MATERIAL_TOKENS["success"],
    "warning": MATERIAL_TOKENS["warning"],
    "important": MATERIAL_TOKENS["warning"],
    "caution": MATERIAL_TOKENS["warning"],
}


def callout_accent(callout_type: str) -> str:
    """Return the accent color for a callout."""
    return _CALLOUT_COLOR_MAP.get(callout_type.lower(), MATERIAL_TOKENS["outline_variant"])
