from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.styles import Style

from ..magic_commands import CommandMetadata


@dataclass
class PaletteEntry:
    """Flattened representation of a palette row."""

    metadata: CommandMetadata

    @property
    def search_blob(self) -> str:
        parts = [
            self.metadata.name,
            self.metadata.syntax,
            self.metadata.description,
            self.metadata.category,
        ]
        if self.metadata.shortcut:
            parts.append(self.metadata.shortcut)
        return " ".join(parts).lower()


class CommandPalette:
    """Interactive command palette rendered with prompt_toolkit."""

    def __init__(self, metadata_provider: Callable[[], Iterable[CommandMetadata]]):
        self._metadata_provider = metadata_provider
        self._style = Style.from_dict(
            {
                "title": "bold",
                "category": "fg:#8be9fd",
                "command": "fg:#f8f8f2",
                "selected": "reverse",
                "details": "fg:#bd93f9",
                "shortcut": "fg:#50fa7b",
                "state": "fg:#ffb86c",
                "empty": "fg:#6272a4",
            }
        )
        self._entries: List[PaletteEntry] = []
        self._visible_entries: List[PaletteEntry] = []
        self._selection_index: int = 0

    def open(self) -> Optional[str]:
        metadata_items = list(self._metadata_provider())
        if not metadata_items:
            return None

        self._entries = [PaletteEntry(item) for item in metadata_items]
        self._entries.sort(key=lambda entry: (entry.metadata.category, entry.metadata.name))
        self._visible_entries = list(self._entries)
        self._selection_index = 0

        search_buffer = Buffer()

        def refresh() -> None:
            query = search_buffer.text.lower().strip()
            if not query:
                self._visible_entries = list(self._entries)
            else:
                tokens = [token for token in query.split(" ") if token]

                def matches(entry: PaletteEntry) -> bool:
                    return all(token in entry.search_blob for token in tokens)

                self._visible_entries = [
                    entry for entry in self._entries if matches(entry)
                ]

            if self._visible_entries:
                self._selection_index = min(self._selection_index, len(self._visible_entries) - 1)
            else:
                self._selection_index = 0
            get_app().invalidate()

        search_buffer.on_text_changed += lambda _: refresh()

        list_control = FormattedTextControl(self._render)
        search_control = BufferControl(buffer=search_buffer)

        layout = Layout(
            HSplit(
                [
                    Window(
                        height=1,
                        content=FormattedTextControl(self._render_title),
                        style="class:title",
                    ),
                    Window(height=1, content=search_control, style="class:command"),
                    Window(content=list_control, always_hide_cursor=True),
                ],
                padding=1,
            ),
            focused_element=search_control,
        )

        bindings = self._build_key_bindings()

        application = Application(
            layout=layout,
            key_bindings=bindings,
            style=self._style,
            mouse_support=False,
            full_screen=False,
        )

        result = application.run()
        return result

    def _render_title(self) -> List[tuple[str, str]]:
        return [("class:title", " Command Palette (type to filter, Enter to select, Esc to close)")]

    def _render(self) -> List[tuple[str, str]]:
        fragments: List[tuple[str, str]] = []

        if not self._visible_entries:
            fragments.append(("class:empty", " No matching commands\n"))
            return fragments

        current_category = None
        selected_entry = self._visible_entries[self._selection_index]

        for entry in self._visible_entries:
            metadata = entry.metadata
            if metadata.category != current_category:
                current_category = metadata.category
                fragments.append(("class:category", f" {metadata.icon} {metadata.category}\n"))

            is_selected = entry is selected_entry
            line_style = "class:selected" if is_selected else "class:command"
            caret = "➤" if is_selected else " "
            fragments.append(
                (
                    line_style,
                    f" {caret} {metadata.syntax}",
                )
            )

            if metadata.state:
                fragments.append(("class:state", f"  [{metadata.state}]"))
            if metadata.shortcut:
                fragments.append(("class:shortcut", f"  {metadata.shortcut}"))

            fragments.append((line_style, "\n"))
            fragments.append(("class:details", f"    {metadata.description}\n"))

        return fragments

    def _build_key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()

        @bindings.add("up")
        def _go_up(event) -> None:
            if not self._visible_entries:
                return
            self._selection_index = (self._selection_index - 1) % len(self._visible_entries)
            event.app.invalidate()

        @bindings.add("down")
        def _go_down(event) -> None:
            if not self._visible_entries:
                return
            self._selection_index = (self._selection_index + 1) % len(self._visible_entries)
            event.app.invalidate()

        @bindings.add("enter")
        def _accept(event) -> None:
            event.app.exit(result=self._selected_snippet())

        @bindings.add("escape")
        def _cancel(event) -> None:
            event.app.exit(result=None)

        return bindings

    def _selected_snippet(self) -> Optional[str]:
        if not self._visible_entries:
            return None
        metadata = self._visible_entries[self._selection_index].metadata
        if not metadata.insertable:
            return None
        return metadata.palette_snippet or metadata.syntax

