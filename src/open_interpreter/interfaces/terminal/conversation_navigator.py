"""Interactive conversation browser for the terminal interface."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

from .render_past_conversation import render_past_conversation
from .theme import TERMINAL_THEME
from .utils.export_to_markdown import (
    export_to_json,
    export_to_markdown,
    export_to_notebook,
)
from .utils.local_storage_path import get_storage_path
from .magic_commands import get_downloads_path


@dataclass(slots=True)
class ConversationRecord:
    filename: str
    path: Path
    title: str
    modified: datetime
    message_count: int
    has_code: bool
    has_console: bool
    tags: tuple[str, ...]
    roles: tuple[str, ...]
    preview: str
    search_blob: str
    messages: list[dict]

    @property
    def metadata_chips(self) -> tuple[str, ...]:
        base = [
            self.modified.strftime("%b %d %Y %H:%M"),
            f"{self.message_count} msgs",
        ]
        return tuple(base + list(self.tags))


class ConversationListItem(ListItem):
    """List item representing a conversation entry."""

    def __init__(self, record: ConversationRecord) -> None:
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        chips = [Static(chip, classes="chip") for chip in self.record.metadata_chips]
        if self.record.roles:
            chips.append(
                Static(
                    "/".join(role.title() for role in self.record.roles),
                    classes="chip",
                )
            )
        preview_text = self.record.preview or "No assistant response captured."
        yield Vertical(
            Static(self.record.title, classes="item-title"),
            Horizontal(*chips, classes="chip-row"),
            Static(preview_text, classes="item-preview"),
        )


class ConversationBrowserApp(App[dict | None]):
    """Textual application used to browse and manage conversations."""

    BINDINGS = [
        ("q", "cancel", "Quit"),
        ("escape", "cancel", "Quit"),
        ("enter", "resume", "Resume"),
        ("m", "export_markdown", "Export Markdown"),
        ("n", "export_notebook", "Export Notebook"),
        ("j", "export_json", "Export JSON"),
        ("o", "open_folder", "Open Folder"),
    ]

    CSS = f"""
    Screen {{
        background: {TERMINAL_THEME.surface};
        color: {TERMINAL_THEME.message_text};
    }}

    #toolbar {{
        layout: horizontal;
        padding: 1 2;
        height: auto;
        background: {TERMINAL_THEME.surface};
        gap: 1;
    }}

    Input#search {{
        width: 1fr;
    }}

    Button.filter {{
        border: round {TERMINAL_THEME.chip_border};
    }}

    Button.filter.active {{
        background: {TERMINAL_THEME.accent};
        color: black;
    }}

    #conversation-list {{
        height: 1fr;
        border: round {TERMINAL_THEME.message_border};
        margin: 1 2;
    }}

    .chip {{
        background: {TERMINAL_THEME.chip_background};
        color: {TERMINAL_THEME.chip_text};
        border: round {TERMINAL_THEME.chip_border};
        padding: 0 1;
        height: auto;
    }}

    .chip-row {{
        gap: 1;
        margin: 0 0 1 0;
    }}

    .item-title {{
        color: {TERMINAL_THEME.message_text};
        text-style: bold;
    }}

    .item-preview {{
        color: {TERMINAL_THEME.message_text};
        opacity: 0.7;
    }}

    #actions {{
        layout: horizontal;
        padding: 1 2;
        gap: 1;
    }}

    Button#resume {{
        background: {TERMINAL_THEME.accent};
        color: black;
    }}

    Button#cancel {{
        border: round {TERMINAL_THEME.chip_border};
    }}

    .empty {{
        padding: 1;
        opacity: 0.7;
    }}
    """

    def __init__(self, records: Sequence[ConversationRecord], conversations_dir: Path) -> None:
        super().__init__()
        self.records = list(records)
        self.filtered_records = list(records)
        self.selected: ConversationRecord | None = records[0] if records else None
        self.conversations_dir = conversations_dir
        self.search_text = ""
        self.filter_code = False
        self.filter_console = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="toolbar"):
            yield Input(placeholder="Search conversations...", id="search")
            yield Button("Has Code", id="filter-code", classes="filter")
            yield Button("Has Console", id="filter-console", classes="filter")
            yield Button("Open Folder", id="open-folder")
        yield ListView(id="conversation-list")
        with Container(id="actions"):
            yield Button("Resume", id="resume")
            yield Button("Markdown", id="export-markdown")
            yield Button("Notebook", id="export-notebook")
            yield Button("JSON", id="export-json")
            yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.search_text = event.value.strip()
            self._refresh_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "filter-code":
            self.filter_code = not self.filter_code
            event.button.set_class(self.filter_code, "active")
            self._refresh_list()
        elif button_id == "filter-console":
            self.filter_console = not self.filter_console
            event.button.set_class(self.filter_console, "active")
            self._refresh_list()
        elif button_id == "open-folder":
            self.action_open_folder()
        elif button_id == "resume":
            self.action_resume()
        elif button_id == "export-markdown":
            self.action_export_markdown()
        elif button_id == "export-notebook":
            self.action_export_notebook()
        elif button_id == "export-json":
            self.action_export_json()
        elif button_id == "cancel":
            self.action_cancel()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, ConversationListItem):
            self.selected = item.record

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ConversationListItem):
            self.selected = item.record
            self.action_resume()

    def action_resume(self) -> None:
        if self.selected:
            self.exit({"action": "resume", "record": self.selected})

    def action_export_markdown(self) -> None:
        if self.selected:
            self.exit({"action": "export_markdown", "record": self.selected})

    def action_export_notebook(self) -> None:
        if self.selected:
            self.exit({"action": "export_notebook", "record": self.selected})

    def action_export_json(self) -> None:
        if self.selected:
            self.exit({"action": "export_json", "record": self.selected})

    def action_open_folder(self) -> None:
        self.exit({"action": "open_folder"})

    def action_cancel(self) -> None:
        self.exit(None)

    def _refresh_list(self) -> None:
        list_view = self.query_one(ListView)
        list_view.clear()
        records = self._filtered_records()
        self.filtered_records = records
        if not records:
            list_view.append(ListItem(Static("No conversations match your filters.", classes="empty")))
            self.selected = None
            return
        for record in records:
            list_view.append(ConversationListItem(record))
        list_view.index = 0
        self.selected = records[0]

    def _filtered_records(self) -> list[ConversationRecord]:
        records: Iterable[ConversationRecord] = self.records
        if self.filter_code:
            records = [record for record in records if record.has_code]
        if self.filter_console:
            records = [record for record in records if record.has_console]
        if self.search_text:
            query = self.search_text.lower()
            records = [record for record in records if query in record.search_blob]
        return list(records)


def conversation_navigator(interpreter) -> None:
    conversations_dir = Path(get_storage_path("conversations"))

    interpreter.display_message(
        f"""> Conversations are stored in "`{conversations_dir}`".\n\nSelect a conversation to resume or export."""
    )

    if not conversations_dir.exists():
        print(f"No conversations found in {conversations_dir}")
        return None

    records = _load_records(conversations_dir)
    if not records:
        print(f"No conversations found in {conversations_dir}")
        return None

    app = ConversationBrowserApp(records, conversations_dir)
    result = app.run()

    if not result:
        return None

    action = result.get("action")
    record: ConversationRecord | None = result.get("record")

    if action == "open_folder":
        open_folder(str(conversations_dir))
        return None

    if record is None:
        return None

    if action == "resume":
        render_past_conversation(record.messages)
        interpreter.messages = record.messages
        interpreter.conversation_filename = record.filename
        interpreter.chat()
        return None

    downloads = Path(get_downloads_path())
    downloads.mkdir(parents=True, exist_ok=True)

    try:
        if action == "export_markdown":
            export_to_markdown(record.messages, str(downloads / f"{record.path.stem}.md"))
        elif action == "export_notebook":
            export_to_notebook(record.messages, str(downloads / f"{record.path.stem}.ipynb"))
        elif action == "export_json":
            export_to_json(record.messages, str(downloads / record.filename))
    except RuntimeError as exc:
        interpreter.display_message(str(exc))


def _load_records(conversations_dir: Path) -> list[ConversationRecord]:
    records: list[ConversationRecord] = []
    for path in sorted(conversations_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with path.open("r", encoding="utf-8") as handle:
                messages = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(messages, list):
            continue

        message_count = len(messages)
        roles = tuple(sorted({str(msg.get("role", "")) for msg in messages if msg.get("role")}))
        has_code = any(msg.get("type") == "code" for msg in messages)
        has_console = any(msg.get("type") == "console" for msg in messages)
        tags = []
        if has_code:
            tags.append("Code")
        if has_console:
            tags.append("Console")
        if any(msg.get("type") == "image" for msg in messages):
            tags.append("Images")

        first_user = next(
            (msg.get("content", "") for msg in messages if msg.get("role") == "user" and msg.get("content")),
            "",
        )
        title = _title_from_filename(path.stem, first_user)
        preview = next(
            (
                msg.get("content", "")
                for msg in messages
                if msg.get("role") == "assistant" and msg.get("content")
            ),
            "",
        )
        preview = preview.replace("\n", " ").strip()[:160]
        search_blob = " ".join(
            [
                title,
                path.stem,
                preview,
                " ".join(tags),
                " ".join(roles),
            ]
        ).lower()

        records.append(
            ConversationRecord(
                filename=path.name,
                path=path,
                title=title,
                modified=datetime.fromtimestamp(path.stat().st_mtime),
                message_count=message_count,
                has_code=has_code,
                has_console=has_console,
                tags=tuple(tags),
                roles=roles,
                preview=preview,
                search_blob=search_blob,
                messages=messages,
            )
        )

    return records


def _title_from_filename(stem: str, first_user_message: str) -> str:
    candidate = first_user_message.strip().splitlines()[0][:80] if first_user_message else ""
    if candidate:
        return candidate
    return stem.replace("__", " ").replace("_", " ").strip() or stem


def open_folder(path: str) -> None:
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


__all__ = ["conversation_navigator"]
