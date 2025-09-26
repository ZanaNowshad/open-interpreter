"""Shared terminal UI helpers for branded output and iconography."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Dict

BRAND_GLYPH = "🟠"
"""Glyph used to visually identify Open Interpreter output."""

ROLE_ICONS: Dict[str, str] = {
    "user": "🙋",  # Person asking for help
    "assistant": "🤖",  # LLM assistant persona
    "computer": "🖥️",  # Local computer actions
}
"""Icons representing the primary actors in transcripts."""

STATUS_ICONS: Dict[str, str] = {
    "info": "💡",
    "pending": "⏳",
    "success": "✅",
    "warning": "⚠️",
    "error": "❌",
}
"""Icons representing high-level status states."""


def _resolve_version() -> str:
    """Return the installed Open Interpreter version or ``dev`` when unavailable."""

    try:
        return pkg_version("open-interpreter")
    except PackageNotFoundError:
        return "dev"


def _normalize_profile(profile: str | None) -> str:
    """Normalise the profile label for display purposes."""

    if not profile:
        return "default"

    # Remove any directory information to keep the label compact
    label = profile.split("/")[-1]
    if label.endswith(".yaml") or label.endswith(".py"):
        label = label.rsplit(".", 1)[0]
    return label or "default"


def icon_for_role(role: str) -> str:
    """Return the representative icon for a transcript role."""

    return ROLE_ICONS.get(role, "•")


def icon_for_status(status: str | None) -> str:
    """Return the icon associated with a status string."""

    if status is None:
        return STATUS_ICONS["info"]

    return STATUS_ICONS.get(status, STATUS_ICONS["info"])


def render_brand_header(profile: str | None = None) -> str:
    """Produce a branded header with the glyph, version, and profile name."""

    version = _resolve_version()
    profile_label = _normalize_profile(profile)

    header_lines = [
        f"{BRAND_GLYPH} **Open Interpreter**",
        f"{STATUS_ICONS['info']} Version `{version}` · {ROLE_ICONS['assistant']} Profile `{profile_label}`",
        "",
    ]
    return "\n".join(header_lines)


def apply_brand_header(body: str, profile: str | None = None) -> str:
    """Attach the brand header above ``body`` content."""

    header = render_brand_header(profile=profile)
    body = body.strip()

    if not body:
        return header

    return f"{header}{body}\n"


def format_notification(text: str, status: str | None = None) -> str:
    """Prefix notification text with consistent role and status iconography."""

    status_icon = icon_for_status(status)
    return f"{ROLE_ICONS['computer']} {status_icon} {text}"


__all__ = [
    "BRAND_GLYPH",
    "ROLE_ICONS",
    "STATUS_ICONS",
    "apply_brand_header",
    "format_notification",
    "icon_for_role",
    "icon_for_status",
    "render_brand_header",
]
