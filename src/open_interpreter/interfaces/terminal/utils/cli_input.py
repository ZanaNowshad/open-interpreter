from __future__ import annotations

from typing import Dict, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings

from ..components.command_palette import CommandPalette

_SESSIONS: Dict[int, PromptSession] = {}


def _toolbar(interpreter: object) -> HTML:
    multi_line = "ON" if getattr(interpreter, "multi_line", False) else "OFF"
    voice = "ON" if getattr(interpreter, "speak_messages", False) else "OFF"
    safe_mode = getattr(interpreter, "safe_mode", "off") or "off"
    auto_run = "AUTO" if getattr(interpreter, "auto_run", False) else "PROMPT"

    return HTML(
        " <b>Ctrl+K</b> Palette"
        f" | <b>F2</b> Multi-line: <b>{multi_line}</b>"
        f" | <b>F3</b> Voice: <b>{voice}</b>"
        f" | <b>F4</b> Safe Mode: <b>{str(safe_mode).upper()}</b>"
        f" | <b>F5</b> Auto Run: <b>{auto_run}</b>"
    )


def _build_key_bindings(
    interpreter: object, command_palette: Optional[CommandPalette]
) -> KeyBindings:
    bindings = KeyBindings()

    if command_palette is not None:

        @bindings.add("c-k")
        def _show_palette(event) -> None:
            selection = command_palette.open()
            if selection:
                buffer = event.app.current_buffer
                buffer.text = selection
                buffer.cursor_position = len(buffer.text)

    @bindings.add("f2")
    def _toggle_multiline(event) -> None:
        interpreter.multi_line = not getattr(interpreter, "multi_line", False)
        get_app().invalidate()

    @bindings.add("f3")
    def _toggle_voice(event) -> None:
        interpreter.speak_messages = not getattr(
            interpreter, "speak_messages", False
        )
        get_app().invalidate()

    @bindings.add("f4")
    def _cycle_safe_mode(event) -> None:
        safe_mode_sequence = ["ask", "auto", "off"]
        current = str(getattr(interpreter, "safe_mode", "off") or "off").lower()
        if current not in safe_mode_sequence:
            next_mode = safe_mode_sequence[0]
        else:
            idx = safe_mode_sequence.index(current)
            next_mode = safe_mode_sequence[(idx + 1) % len(safe_mode_sequence)]
        interpreter.safe_mode = next_mode
        get_app().invalidate()

    @bindings.add("f5")
    def _toggle_auto_run(event) -> None:
        interpreter.auto_run = not getattr(interpreter, "auto_run", False)
        get_app().invalidate()

    return bindings


def _get_session(
    interpreter: object, command_palette: Optional[CommandPalette]
) -> PromptSession:
    key = id(interpreter)
    if key not in _SESSIONS:
        bindings = _build_key_bindings(interpreter, command_palette)
        _SESSIONS[key] = PromptSession(
            history=InMemoryHistory(),
            key_bindings=bindings,
            bottom_toolbar=lambda: _toolbar(interpreter),
        )
    return _SESSIONS[key]


def _legacy_cli_input(prompt: str = "") -> str:
    start_marker = '"""'
    end_marker = '"""'
    message = input(prompt)

    if start_marker in message:
        lines = [message]
        while True:
            line = input()
            lines.append(line)
            if end_marker in line:
                break
        return "\n".join(lines)

    return message


def cli_input(
    prompt: str = "",
    interpreter: Optional[object] = None,
    command_palette: Optional[CommandPalette] = None,
) -> str:
    if interpreter is None:
        return _legacy_cli_input(prompt)

    session = _get_session(interpreter, command_palette)

    start_marker = '"""'
    end_marker = '"""'
    message = session.prompt(prompt)

    if getattr(interpreter, "multi_line", False) and start_marker in message:
        lines = [message]
        while True:
            line = session.prompt("")
            lines.append(line)
            if end_marker in line:
                break
        return "\n".join(lines)

    return message

