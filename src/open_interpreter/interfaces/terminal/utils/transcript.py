"""Utilities for exporting conversations with screen-reader friendly metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from ..strings import StringRegistry


ARIA_ROLE_MAP = {
    "user": "textbox",
    "assistant": "status",
    "system": "note",
}


@dataclass
class TranscriptEntry:
    identifier: str
    role: str
    message_type: str
    aria_role: str
    content: str
    spoken_text: str

    def to_dict(self) -> dict:
        return {
            "id": self.identifier,
            "role": self.role,
            "type": self.message_type,
            "ariaRole": self.aria_role,
            "content": self.content,
            "spokenText": self.spoken_text,
        }


def _role_label(role: str, strings: StringRegistry) -> str:
    role_key = {
        "user": "transcript_role_user",
        "assistant": "transcript_role_assistant",
        "system": "transcript_role_system",
    }.get(role, "transcript_role_other")
    return strings.get(role_key)


def messages_to_transcript(
    messages: Sequence[Mapping[str, str]],
    strings: StringRegistry,
) -> dict:
    """Transform interpreter messages into an accessible transcript structure."""

    entries: list[TranscriptEntry] = []
    now = datetime.utcnow().isoformat()

    for index, message in enumerate(messages):
        role = message.get("role", "assistant")
        message_type = message.get("type", "message")
        aria_role = ARIA_ROLE_MAP.get(role, "article")
        content = str(message.get("content", "")).strip()

        spoken_text = strings.get(
            "transcript_spoken_fallback",
            role_label=_role_label(role, strings),
            content=content,
        )

        entries.append(
            TranscriptEntry(
                identifier=f"msg-{index}",
                role=role,
                message_type=message_type,
                aria_role=aria_role,
                content=content,
                spoken_text=spoken_text,
            )
        )

    return {
        "version": "1.0",
        "generatedAt": now,
        "ariaLandmark": "main",
        "entries": [entry.to_dict() for entry in entries],
    }


def export_transcript(
    messages: Sequence[Mapping[str, str]],
    export_path: Path,
    strings: StringRegistry,
) -> Path:
    """Persist the accessible transcript to disk."""

    export_path = export_path.with_suffix(".json")
    export_path.parent.mkdir(parents=True, exist_ok=True)

    transcript_payload = messages_to_transcript(messages, strings)
    export_path.write_text(
        json.dumps(transcript_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return export_path


__all__ = ["messages_to_transcript", "export_transcript"]

