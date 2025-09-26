"""Interactive UI components for the terminal interface."""

from __future__ import annotations

import atexit
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


def _read_key() -> str:
    """Read a single keypress from stdin."""

    # Windows support via msvcrt
    if sys.platform.startswith("win"):
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch += msvcrt.getwch()
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1b":
            # Read potential escape sequences
            try:
                ch += sys.stdin.read(2)
            except Exception:
                pass
            return ch
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _normalize_keypress(key: str) -> str:
    """Translate raw key sequences into normalized identifiers."""

    if key in {"\r", "\n"}:
        return "enter"
    if key == "\t":
        return "next"
    if key == "\x1b[Z":
        return "previous"
    if key in {"\x1b[A", "\x1b[D", "\xe0K", "\xe0H"}:
        return "previous"
    if key in {"\x1b[B", "\x1b[C", "\xe0M", "\xe0P"}:
        return "next"
    if key.lower() in {"a", "e", "s", "q", "g", "d"}:
        return key.lower()
    if key == " ":
        return "enter"
    if key == "\x04":  # Ctrl+D
        return "skip"
    return key


@dataclass
class ReviewAction:
    name: str
    label: str
    description: str
    shortcut: str


@dataclass
class ReviewDecision:
    action: str
    scan_enabled: bool
    default_action: Optional[str] = None


class StatusBar:
    """Render persistent terminal preferences in a status bar."""

    def __init__(self) -> None:
        self.console = Console()
        self._live = Live(console=self.console, auto_refresh=False, transient=False)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._live.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._live.stop()
            self._started = False

    def update(self, preferences: Dict[str, object], safe_mode: str) -> None:
        """Update the status bar with the latest preferences."""

        segments: List[str] = []
        segments.append(f"[bold]Safe[/]: {safe_mode}")
        scan_state = "On" if preferences.get("scan", False) else "Off"
        segments.append(f"[bold cyan]Scan[/]: {scan_state}")
        default_action = preferences.get("default_action", "approve").title()
        segments.append(f"[bold magenta]Default[/]: {default_action}")
        last_decision = preferences.get("last_decision")
        if last_decision:
            segments.append(f"[bold green]Last[/]: {last_decision}")
        last_scan = preferences.get("last_scan_status")
        if last_scan:
            segments.append(f"[bold yellow]Scan Result[/]: {last_scan}")

        text = Text("  ".join(segments))
        panel = Panel(Align.center(text), box=ROUNDED, style="white on #333333")

        self.start()
        self._live.update(panel)
        self._live.refresh()


status_bar = StatusBar()


@atexit.register
def _shutdown_status_bar() -> None:
    status_bar.stop()


class ReviewPanel:
    """Interactive approval panel built with Rich."""

    def __init__(
        self,
        *,
        code_origin: str,
        diff_summary: str,
        risk_level: str,
        runtime_estimate: str,
        scan_enabled: bool,
        default_action: str,
        preferences: Dict[str, str],
        safe_mode: str,
        status_callback: Optional[Callable[[], None]] = None,
        console: Optional[Console] = None,
    ) -> None:
        self.console = console or Console()
        self.code_origin = code_origin
        self.diff_summary = diff_summary
        self.risk_level = risk_level
        self.runtime_estimate = runtime_estimate
        self.scan_enabled = scan_enabled
        self.preferences = preferences
        self.safe_mode = safe_mode
        self.status_callback = status_callback

        self.actions: List[ReviewAction] = [
            ReviewAction("approve", "Approve & Run", "Execute the proposed code.", "a"),
            ReviewAction(
                "edit",
                "Edit & Run",
                "Open $EDITOR to review and modify before running.",
                "e",
            ),
            ReviewAction("skip", "Skip", "Decline this execution.", "s"),
        ]

        self.focus_index = next(
            (i for i, action in enumerate(self.actions) if action.name == default_action),
            0,
        )
        self.message: Optional[str] = None
        self.selected_default: Optional[str] = None

    def _render_summary(self) -> Table:
        table = Table.grid(expand=True)
        table.add_column(style="bold cyan", width=16)
        table.add_column(ratio=1)
        table.add_row("Origin", self.code_origin)
        table.add_row("Risk", self.risk_level)
        table.add_row("Est. Runtime", self.runtime_estimate)
        scan_state = "Enabled" if self.scan_enabled else "Disabled"
        table.add_row("Code Scan", scan_state)
        return table

    def _render_diff(self) -> Panel:
        diff_text = self.diff_summary or "No previous executions to diff against."
        syntax = Syntax(diff_text, "diff", word_wrap=True)
        return Panel(syntax, title="Diff vs last run", border_style="blue", box=ROUNDED)

    def _render_actions(self) -> Table:
        table = Table.grid(padding=(0, 1), expand=True)
        for index, action in enumerate(self.actions):
            is_focus = index == self.focus_index
            base_style = "bold black on #4fc3f7" if is_focus else "white"
            secondary_style = "black on #4fc3f7" if is_focus else "dim"
            shortcut = action.shortcut.upper()
            label = Text(f"[{shortcut}] {action.label}", style=base_style)
            description = Text(action.description, style=secondary_style)
            table.add_row(label, description)
        return table

    def _render_footer(self) -> Align:
        hints = Text()
        hints.append("⏎ Select", style="bold")
        hints.append("  •  ")
        hints.append("[G] Toggle scan", style="bold")
        hints.append("  •  ")
        hints.append("[D] Set default", style="bold")
        hints.append("  •  ")
        hints.append("[Q] Skip", style="bold")
        if self.message:
            hints.append(f"\n{self.message}", style="yellow")
        return Align.center(hints)

    def _render(self) -> Panel:
        group = Group(self._render_summary(), self._render_diff(), self._render_actions(), self._render_footer())
        return Panel(group, title="Execution Review", border_style="cyan", box=ROUNDED)

    def _update_status_bar(self) -> None:
        if self.status_callback:
            self.status_callback()

    def prompt(self) -> ReviewDecision:
        with Live(self._render(), console=self.console, transient=True, auto_refresh=False) as live:
            while True:
                key = _normalize_keypress(_read_key())

                if key in ("enter",):
                    break

                if key == "next":
                    self.focus_index = (self.focus_index + 1) % len(self.actions)
                elif key == "previous":
                    self.focus_index = (self.focus_index - 1) % len(self.actions)
                elif key == "a":
                    self.focus_index = 0
                    break
                elif key == "e":
                    self.focus_index = 1
                    break
                elif key in {"s", "q", "skip"}:
                    self.focus_index = 2
                    break
                elif key == "g":
                    self.scan_enabled = not self.scan_enabled
                    self.preferences["scan"] = self.scan_enabled
                    self.message = (
                        "Code scanning enabled." if self.scan_enabled else "Code scanning disabled."
                    )
                    self._update_status_bar()
                elif key == "d":
                    default_name = self.actions[self.focus_index].name
                    self.preferences["default_action"] = default_name
                    self.selected_default = default_name
                    self.message = f"Default action set to {self.actions[self.focus_index].label}."
                    self._update_status_bar()

                live.update(self._render())
                live.refresh()

        action = self.actions[self.focus_index].name
        decision = ReviewDecision(action=action, scan_enabled=self.scan_enabled, default_action=self.selected_default)
        return decision
