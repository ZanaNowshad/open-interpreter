"""Utilities for rendering the terminal session header."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def _format_temperature(value: Any) -> str:
    if value is None:
        return "default"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _format_source(source: str | None) -> str:
    mapping = {
        "default": "default",
        "user": "custom",
        "remote": "remote",
        "custom": "custom",
    }
    return mapping.get(source or "", source or "unknown")


def _collect_session_metadata(interpreter: Any) -> dict[str, Any]:
    profile_meta = getattr(interpreter, "profile_metadata", {}) or {}
    temperature = getattr(getattr(interpreter, "llm", object()), "temperature", None)

    return {
        "profile_name": profile_meta.get("name", "default.yaml"),
        "profile_source": profile_meta.get("source"),
        "profile_version": profile_meta.get("version"),
        "profile_path": profile_meta.get("path"),
        "model": getattr(getattr(interpreter, "llm", object()), "model", "unknown"),
        "temperature": _format_temperature(temperature),
        "auto_run": "on" if getattr(interpreter, "auto_run", False) else "off",
        "safe_mode": getattr(interpreter, "safe_mode", "off"),
        "custom_instructions": bool(getattr(interpreter, "custom_instructions", "")),
        "plain_text": getattr(interpreter, "plain_text_display", False),
        "palette_enabled": getattr(interpreter, "_command_palette_enabled", True),
    }


def display_session_header(interpreter: Any) -> None:
    """Render the session header with active profile metadata."""

    metadata = _collect_session_metadata(interpreter)

    profile_label = _format_source(metadata["profile_source"])
    version_label = metadata["profile_version"]
    profile_path = metadata["profile_path"]

    if metadata["plain_text"]:
        print(
            f"Session profile: {metadata['profile_name']} ({profile_label})"
            + (f" v{version_label}" if version_label else "")
        )
        if profile_path:
            print(f"Path: {profile_path}")
        print(
            "Model: {model} | Temp: {temp} | Auto-run: {auto} | Safe mode: {safe}".format(
                model=metadata["model"],
                temp=metadata["temperature"],
                auto=metadata["auto_run"],
                safe=metadata["safe_mode"],
            )
        )
        if metadata["custom_instructions"]:
            print("Custom instructions: enabled")
        if metadata["palette_enabled"]:
            print("Hint: type '::' during the session to open the command palette.")
        print("")
        return

    profile_line = Text()
    profile_line.append(metadata["profile_name"], style="bold cyan")
    profile_line.append(f" • {profile_label}", style="dim")
    if version_label:
        profile_line.append(f" • v{version_label}", style="dim")
    if profile_path:
        profile_line.append(f"\n{profile_path}", style="dim")

    model_line = Text()
    model_line.append(metadata["model"], style="bold white")
    model_line.append(
        f" • temp {metadata['temperature']} • auto-run {metadata['auto_run']} • safe mode {metadata['safe_mode']}",
        style="dim",
    )

    details_line = Text()
    details_line.append(
        "Custom instructions: ",
        style="dim",
    )
    details_line.append(
        "enabled" if metadata["custom_instructions"] else "disabled",
        style="bold",
    )
    if metadata["palette_enabled"]:
        details_line.append(
            " • type '::' to open the command palette",
            style="dim",
        )

    body = Text()
    body.append(profile_line)
    body.append("\n")
    body.append(model_line)
    body.append("\n")
    body.append(details_line)

    panel = Panel(body, border_style="cyan", title="Session")
    console.print(panel)
