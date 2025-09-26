from __future__ import annotations

from rich.console import Console
from rich.live import Live

from .theme_tokens import ThemeTokens, get_theme


class BaseBlock:
    """
    a visual "block" on the terminal.
    """

    def __init__(self, theme: str | ThemeTokens | None = None):
        self.live = Live(
            auto_refresh=False, console=Console(), vertical_overflow="visible"
        )
        self.live.start()
        self._theme: ThemeTokens = get_theme(theme)
        self.focused = False

    @property
    def theme(self) -> ThemeTokens:
        return self._theme

    def set_theme(self, theme: str | ThemeTokens | None) -> None:
        """Update the block's theme tokens and trigger a repaint."""

        self._theme = get_theme(theme)
        self.refresh(cursor=self.focused)

    def set_focus(self, focused: bool) -> None:
        """Track focus state so components can expose visual outlines."""

        self.focused = focused
        self.refresh(cursor=focused)

    def update_from_message(self, message):
        raise NotImplementedError("Subclasses must implement this method")

    def end(self):
        self.refresh(cursor=False)
        self.live.stop()

    def refresh(self, cursor=True):
        raise NotImplementedError("Subclasses must implement this method")
