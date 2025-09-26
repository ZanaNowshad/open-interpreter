"""Localization scaffolding for terminal user-facing strings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, MutableMapping


DEFAULT_STRINGS: Dict[str, str] = {
    "help_intro": "> **Available Commands:**\n\n",
    "help_footer": "\n\nFor further assistance, please join our community Discord or consider contributing to the project's development.",
    "help_command_shell": "Run commands in system shell",
    "help_command_verbose": "Toggle verbose mode. Without arguments or with 'true', it enters verbose mode. With 'false', it exits verbose mode.",
    "help_command_reset": "Resets the current session.",
    "help_command_undo": "Remove previous messages and its response from the message history.",
    "help_command_save": "Saves messages to a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
    "help_command_load": "Loads messages from a specified JSON path. If no path is provided, it defaults to 'messages.json'.",
    "help_command_tokens": "EXPERIMENTAL: Calculate the tokens used by the next request and estimate the cost.",
    "help_command_help": "Show this help message.",
    "help_command_info": "Show system and interpreter information.",
    "help_command_jupyter": "Export the conversation to a Jupyter notebook file.",
    "help_command_markdown": "Export the conversation to a specified Markdown path.",
    "help_command_theme": "Switch between accessible colour themes (default, dyslexia, monochrome).",
    "help_command_transcript": "Export an ARIA-friendly transcript as JSON for screen readers.",
    "help_command_auto_run": "Toggle auto_run mode.",
    "help_command_debug": "Toggle debug mode.",
    "theme_changed": "> Theme changed to {theme}",
    "theme_available": "> Available themes: {available}",
    "theme_invalid": "> Unknown theme '{theme}'. Available themes: {available}",
    "transcript_export_success": "> Accessible transcript exported to {path}",
    "transcript_export_failure": "> Unable to export transcript: {reason}",
    "transcript_empty": "> No messages to export.",
    "transcript_spoken_fallback": "{role_label}: {content}",
    "transcript_role_user": "User",
    "transcript_role_assistant": "Assistant",
    "transcript_role_system": "System",
    "transcript_role_other": "Participant",
    "skip_link_history": "Skip to chat history",
    "skip_link_input": "Skip to message input",
    "skip_link_palette": "Skip to action palette",
}


@dataclass
class StringRegistry:
    """A lightweight registry for UI strings with optional overrides."""

    overrides: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        merged: Dict[str, str] = dict(DEFAULT_STRINGS)
        if self.overrides:
            merged.update(dict(self.overrides))
        self._strings: MutableMapping[str, str] = merged

    def get(self, key: str, **kwargs) -> str:
        template = self._strings.get(key, DEFAULT_STRINGS.get(key, ""))
        return template.format(**kwargs)

    def items(self):  # pragma: no cover - convenience helper
        return self._strings.items()


__all__ = ["DEFAULT_STRINGS", "StringRegistry"]

