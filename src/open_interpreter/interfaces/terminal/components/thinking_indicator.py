from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


@dataclass
class IndicatorState:
    """Mutable state shared between the animation thread and the caller."""

    label: str
    frame_index: int = 0
    active: bool = False


class ThinkingIndicator:
    """Rich-powered animated indicator for assistant thinking/typing states."""

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, *, interval: float = 0.12):
        self._interval = interval
        self._console = Console()
        self._live: Optional[Live] = None
        self._lock = threading.Lock()
        self._state = IndicatorState(label="")
        self._thread: Optional[threading.Thread] = None

    def start(self, label: str) -> None:
        """Start the indicator with the provided label."""

        with self._lock:
            self._state.label = label
            self._state.frame_index = 0
            if self._state.active:
                return
            self._state.active = True

        self._live = Live(
            auto_refresh=False,
            console=self._console,
            transient=True,
            vertical_overflow="visible",
        )
        self._live.start()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        self._refresh()

    def update_label(self, label: str) -> None:
        with self._lock:
            if not self._state.active:
                return
            self._state.label = label
        self._refresh()

    def stop(self) -> None:
        thread: Optional[threading.Thread]
        with self._lock:
            if not self._state.active:
                return
            self._state.active = False
            thread = self._thread
            self._thread = None
        if thread:
            thread.join(timeout=self._interval * 2)
        if self._live:
            try:
                self._live.stop()
            finally:
                self._live = None

    def _animate(self) -> None:
        while True:
            with self._lock:
                if not self._state.active:
                    break
                self._state.frame_index = (self._state.frame_index + 1) % len(
                    self._FRAMES
                )
            self._refresh()
            time.sleep(self._interval)

    def _refresh(self) -> None:
        live = self._live
        if not live:
            return
        with self._lock:
            label = self._state.label
            frame = self._FRAMES[self._state.frame_index]
        text = Text(f"{frame} {label}", style="dim italic")
        panel = Panel(text, border_style="grey37", padding=(0, 1))
        live.update(panel)
        live.refresh()
