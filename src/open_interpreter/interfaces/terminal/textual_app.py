"""Experimental Textual TUI with explicit focus management for accessibility."""

from __future__ import annotations

from typing import Iterable

try:  # pragma: no cover - optional dependency
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal
    from textual.events import Mount
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Button, Footer, Input, Static
except Exception:  # pragma: no cover - textual might not be installed
    App = object  # type: ignore[misc,assignment]

    def ComposeResult(*args, **kwargs):  # type: ignore[func-returns-value]
        return ()

    class Binding:  # type: ignore[too-few-public-methods]
        def __init__(self, *_, **__):
            pass

    Container = Horizontal = Widget = Button = Footer = Input = Static = object  # type: ignore[assignment]
    Mount = object  # type: ignore[assignment]

    def reactive(value):  # type: ignore[misc]
        return value

from .components.theme_tokens import ThemeTokens, get_theme
from .strings import StringRegistry


class FocusablePane(Static):
    """Base widget that renders a focus outline using theme tokens."""

    can_focus = True
    theme: ThemeTokens

    def __init__(self, theme: ThemeTokens, *children, **kwargs):
        super().__init__(*children, **kwargs)
        self.theme = theme

    def on_mount(self) -> None:  # pragma: no cover - Textual runtime only
        self.set_class(True, "focusable")

    def watch_has_focus(self, has_focus: bool) -> None:  # pragma: no cover
        outline = self.theme.focus_border_style if has_focus else self.theme.message_border_style
        self.styles.border = ("heavy" if has_focus else "round", outline)


class ChatHistoryPane(FocusablePane):
    pass


class InputPane(FocusablePane):
    input_value = reactive("")

    def compose(self) -> ComposeResult:  # pragma: no cover
        yield Input(placeholder="Type a message…", id="chat-input")

    def on_input_changed(self, event: Input.Changed) -> None:  # pragma: no cover
        self.input_value = event.value


class PalettePane(FocusablePane):
    def __init__(self, theme: ThemeTokens, options: Iterable[str]):
        super().__init__(theme)
        self._options = list(options)

    def compose(self) -> ComposeResult:  # pragma: no cover
        for label in self._options:
            yield Button(label=label, variant="primary")


class SkipLinkBar(Horizontal):
    def __init__(self, theme: ThemeTokens, strings: StringRegistry):
        super().__init__()
        self.theme = theme
        self.strings = strings

    def compose(self) -> ComposeResult:  # pragma: no cover
        yield Button(self.strings.get("skip_link_history"), id="skip-history")
        yield Button(self.strings.get("skip_link_input"), id="skip-input")
        yield Button(self.strings.get("skip_link_palette"), id="skip-palette")


class AccessibleChatApp(App):  # pragma: no cover - UI only
    CSS = """
    Screen {
        align: center middle;
    }

    SkipLinkBar {
        padding: 1;
        dock: top;
    }

    .focusable {
        padding: 1 2;
        border: round transparent;
    }

    #chat-layout {
        height: 1fr;
        width: 80%;
    }

    ChatHistoryPane {
        height: 3fr;
    }

    InputPane {
        height: 1fr;
    }

    PalettePane {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+h", "focus_history", "History"),
        Binding("ctrl+i", "focus_input", "Input"),
        Binding("ctrl+p", "focus_palette", "Palette"),
    ]

    def __init__(self, theme: str | ThemeTokens = "default", strings: StringRegistry | None = None):
        super().__init__()
        self.theme_tokens = get_theme(theme)
        self.strings = strings or StringRegistry()

    def compose(self) -> ComposeResult:
        theme = self.theme_tokens
        skip_links = SkipLinkBar(theme, self.strings)
        chat_history = ChatHistoryPane(theme, id="chat-history")
        input_pane = InputPane(theme, id="chat-input-pane")
        palette = PalettePane(theme, ["/run", "/undo", "/export"], id="palette-pane")

        layout = Container(chat_history, input_pane, palette, id="chat-layout")

        yield skip_links
        yield layout
        yield Footer()

    def on_mount(self, event: Mount) -> None:
        self.query_one("#chat-input", Input).focus()

        self.query_one("#skip-history", Button).pressed.connect(
            lambda _: self.set_focus("#chat-history")
        )
        self.query_one("#skip-input", Button).pressed.connect(
            lambda _: self.set_focus("#chat-input-pane")
        )
        self.query_one("#skip-palette", Button).pressed.connect(
            lambda _: self.set_focus("#palette-pane")
        )

    def action_focus_history(self) -> None:
        self.set_focus("#chat-history")

    def action_focus_input(self) -> None:
        self.set_focus("#chat-input-pane")

    def action_focus_palette(self) -> None:
        self.set_focus("#palette-pane")

    def set_focus(self, selector: str) -> None:
        target: Widget | None = self.query_one(selector, expect_type=Widget)
        if target:
            target.focus()


__all__ = ["AccessibleChatApp"]

