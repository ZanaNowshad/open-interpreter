"""Reusable helpers for rendering interpreter history."""

from __future__ import annotations

from typing import Iterable, Mapping

from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from ..core.utils.truncate_output import truncate_output

Message = Mapping[str, object]


class ConversationHistoryRenderer:
    """Render conversation chunks using shared terminal components."""

    def __init__(
        self,
        interpreter=None,
        plain_text: bool = False,
        max_output: int | None = None,
    ) -> None:
        self.interpreter = interpreter
        self.plain_text = plain_text
        self.max_output = max_output
        self.active_block: CodeBlock | MessageBlock | None = None
        self.render_cursor = False
        self.ran_code_block = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render_messages(self, messages: Iterable[Message]) -> None:
        """Render an entire list of messages."""

        for message in messages:
            self.process_chunk(message)
        self.finalize()

    def process_chunk(self, chunk: Mapping[str, object]) -> None:
        """Process a single chunk from the live stream."""

        if self.plain_text:
            self._handle_plain_text(chunk)
            return

        role = chunk.get("role")
        chunk_type = chunk.get("type")
        start = chunk.get("start") is not None
        end = chunk.get("end") is not None

        # Stored conversations are full messages without start/end markers.
        streaming = start or end

        if role == "user" and chunk_type == "message" and not streaming:
            self._flush_active_block()
            content = chunk.get("content") or ""
            print(">", content)
            return

        if chunk_type == "message":
            self._ensure_message_block()
            content = chunk.get("content")
            if content:
                self.active_block.message += content
            self.render_cursor = True
            if end or not streaming:
                self._finalize_message_block()

        elif chunk_type == "code":
            self._ensure_code_block()
            if "format" in chunk and chunk["format"]:
                self.active_block.language = chunk["format"]
            content = chunk.get("content")
            if content:
                self.active_block.code += content
            if "active_line" in chunk and chunk["active_line"] is not None:
                self.active_block.active_line = chunk["active_line"]
            self.render_cursor = True

        elif chunk_type == "console":
            if start and (not self.active_block or self.active_block.type != "code"):
                self._ensure_code_block()
            self.render_cursor = False
            self.ran_code_block = True
            fmt = chunk.get("format")
            if fmt == "output":
                content = chunk.get("content") or ""
                self._ensure_code_block()
                self.active_block.output += "\n" + content
                self.active_block.output = self.active_block.output.strip()
                if self.max_output:
                    self.active_block.output = truncate_output(
                        self.active_block.output,
                        self.max_output,
                        add_scrollbars=False,
                    )
            if fmt == "active_line":
                self._ensure_code_block()
                self.active_block.active_line = chunk.get("content")
                self._notify_os_action()
            if end:
                self._finalize_code_block()

        if end and chunk_type == "message":
            self._finalize_message_block()

        self._refresh_active_block()

    def attach_block(self, block: CodeBlock | MessageBlock) -> None:
        """Attach an externally created block (used by safety prompts)."""

        if self.active_block and self.active_block is not block:
            self.active_block.end()
        self.active_block = block
        self.render_cursor = False
        self.ran_code_block = False
        self._refresh_active_block()

    def finalize(self) -> None:
        if self.active_block:
            self.active_block.end()
            self.active_block = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _handle_plain_text(self, chunk: Mapping[str, object]) -> None:
        if chunk.get("start") or chunk.get("end"):
            print("")
        chunk_type = chunk.get("type")
        fmt = chunk.get("format")
        if chunk_type in {"code", "console"} and fmt:
            if chunk.get("start"):
                print(f"```{fmt}", flush=True)
            if chunk.get("end"):
                print("```", flush=True)
        if fmt != "active_line":
            content = chunk.get("content", "")
            if content:
                print(content, end="", flush=True)

    def _ensure_message_block(self) -> None:
        if not isinstance(self.active_block, MessageBlock):
            self._flush_active_block()
            self.active_block = MessageBlock()
            self.ran_code_block = False

    def _ensure_code_block(self) -> None:
        if not isinstance(self.active_block, CodeBlock) or self.ran_code_block:
            self._flush_active_block()
            self.active_block = CodeBlock(self.interpreter)
            self.active_block.margin_top = True
        self.ran_code_block = False

    def _finalize_message_block(self) -> None:
        if isinstance(self.active_block, MessageBlock):
            self.active_block.refresh(cursor=False)
            self.active_block.end()
            self.active_block = None
            self.render_cursor = False

    def _finalize_code_block(self) -> None:
        if isinstance(self.active_block, CodeBlock):
            self.active_block.refresh(cursor=False)
            self.active_block.end()
            self.active_block = None
            self.render_cursor = False
            self.ran_code_block = False

    def _refresh_active_block(self) -> None:
        if self.active_block:
            self.active_block.refresh(cursor=self.render_cursor)

    def _flush_active_block(self) -> None:
        if self.active_block:
            self.active_block.refresh(cursor=False)
            self.active_block.end()
            self.active_block = None
            self.render_cursor = False
            self.ran_code_block = False

    def _notify_os_action(self) -> None:
        if not self.interpreter or not getattr(self.interpreter, "os", False):
            return
        active_line = getattr(self.active_block, "active_line", None)
        code = getattr(self.active_block, "code", "")
        if active_line is None:
            return
        code_lines = code.split("\n")
        if active_line >= len(code_lines):
            return
        action = code_lines[active_line].strip()
        if not action.startswith("computer"):
            return
        description = None
        start_index = action.find("(")
        end_index = action.rfind(")")
        arguments = None
        if start_index != -1 and end_index != -1:
            arguments = action[start_index + 1 : end_index]
        if any(
            action.startswith(text)
            for text in [
                "computer.screenshot",
                "computer.display.screenshot",
                "computer.display.view",
                "computer.view",
            ]
        ):
            description = "Viewing screen..."
        elif action == "computer.mouse.click()":
            description = "Clicking..."
        elif action.startswith("computer.mouse.click("):
            text_or_icon = "icon" if arguments and "icon=" in arguments else "text"
            description = f"Clicking {text_or_icon}..."
        elif action.startswith("computer.mouse.move("):
            text_or_icon = "icon" if arguments and "icon=" in arguments else "text"
            if "click" in code:
                description = f"Clicking {text_or_icon}..."
            else:
                description = f"Mousing over {text_or_icon}..."
        elif action.startswith("computer.keyboard.write("):
            description = f"Typing {arguments}."
        elif action.startswith("computer.keyboard.hotkey("):
            description = f"Pressing {arguments}."
        elif action.startswith("computer.keyboard.press("):
            description = f"Pressing {arguments}."
        elif action == "computer.os.get_selected_text()":
            description = "Getting selected text."
        if description:
            self.interpreter.computer.os.notify(description)


__all__ = ["ConversationHistoryRenderer"]
