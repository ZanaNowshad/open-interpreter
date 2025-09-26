from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional

from rich.box import MINIMAL
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.padding import Padding
from rich.syntax import Syntax
from rich.text import Text

from .base_block import BaseBlock
from .theme import MATERIAL_SYNTAX_THEME, MATERIAL_TOKENS, STANDARD_MARGIN, callout_accent

__all__ = [
    "MessageBlock",
    "CalloutMetadata",
    "MessageSegment",
    "parse_message_segments",
]


@dataclass
class CalloutMetadata:
    callout_type: str
    title: str
    body: str


@dataclass
class MessageSegment:
    kind: Literal["markdown", "code", "callout"]
    text: str
    language: Optional[str] = None
    callout: Optional[CalloutMetadata] = None


class MessageBlock(BaseBlock):
    def __init__(self):
        super().__init__()

        self.type = "message"
        self.message = ""
        self.margin_top = False

    def refresh(self, cursor=True):
        segments = parse_message_segments(self.message)
        renderables = list(_render_segments(segments))

        if cursor:
            renderables.append(Text("●", style=MATERIAL_TOKENS["accent"]))

        if not renderables:
            renderables = [Text("")]

        body = Group(*renderables) if len(renderables) > 1 else renderables[0]
        panel = Panel(
            body,
            box=MINIMAL,
            padding=(1, 2),
            border_style=MATERIAL_TOKENS["outline"],
            style=f"on {MATERIAL_TOKENS['surface']}",
        )

        renderable = panel
        if self.margin_top:
            renderable = Padding(panel, STANDARD_MARGIN)

        self.live.update(renderable)
        self.live.refresh()


def parse_message_segments(text: str) -> List[MessageSegment]:
    """Split a message into semantic segments for rendering and exports."""

    lines = text.splitlines()
    segments: List[MessageSegment] = []
    buffer: List[str] = []
    i = 0

    def flush_buffer():
        if buffer:
            segments.append(MessageSegment("markdown", "\n".join(buffer)))
            buffer.clear()

    while i < len(lines):
        line = lines[i]

        stripped = line.strip()

        if stripped.startswith("```"):
            flush_buffer()
            language = stripped[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].strip().startswith("```"):
                i += 1
            segments.append(
                MessageSegment(
                    "code",
                    "\n".join(code_lines),
                    language=language or None,
                )
            )
            continue

        if stripped.startswith(">"):
            flush_buffer()
            callout_lines: List[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                callout_lines.append(lines[i])
                i += 1
            segments.append(
                MessageSegment(
                    "callout",
                    "\n".join(callout_lines),
                    callout=_parse_callout(callout_lines),
                )
            )
            continue

        buffer.append(line)
        i += 1

    flush_buffer()
    return segments


def _render_segments(segments: Iterable[MessageSegment]):
    for segment in segments:
        if segment.kind == "markdown":
            content = segment.text.strip("\n")
            if content:
                yield Markdown(content, code_theme=MATERIAL_SYNTAX_THEME)
            continue

        if segment.kind == "code":
            language = segment.language or "text"
            label = Text(
                f"Code snippet ({language})",
                style=MATERIAL_TOKENS["on_surface_variant"],
            )
            syntax = Syntax(
                segment.text,
                language,
                theme=MATERIAL_SYNTAX_THEME,
                line_numbers=False,
                word_wrap=True,
            )
            yield Panel(
                Group(label, syntax),
                box=MINIMAL,
                padding=(1, 2),
                border_style=MATERIAL_TOKENS["outline_variant"],
                style=f"on {MATERIAL_TOKENS['surface_variant']}",
            )
            continue

        if segment.kind == "callout" and segment.callout:
            meta = segment.callout
            heading = meta.title or meta.callout_type
            label = Text(
                f"{meta.callout_type} callout",
                style=callout_accent(meta.callout_type),
            )
            body_text = meta.body.strip()
            body_renderable = (
                Markdown(body_text, code_theme=MATERIAL_SYNTAX_THEME)
                if body_text
                else Text("")
            )
            yield Panel(
                Group(label, body_renderable),
                title=heading,
                title_align="left",
                box=MINIMAL,
                padding=(1, 2),
                border_style=callout_accent(meta.callout_type),
                style=f"on {MATERIAL_TOKENS['surface_variant']}",
            )
            continue


def _parse_callout(lines: Iterable[str]) -> CalloutMetadata:
    cleaned = [re.sub(r"^>+\s?", "", line).rstrip() for line in lines]
    if not cleaned:
        return CalloutMetadata(callout_type="Note", title="", body="")

    first_line = cleaned[0]
    match = re.match(r"\[!(?P<type>[\w-]+)\]\s*(?P<title>.*)", first_line)
    callout_type = "Note"
    title = ""
    body_lines = cleaned

    if match:
        callout_type = match.group("type").title()
        title = match.group("title").strip()
        body_lines = cleaned[1:]

    body = "\n".join(body_lines).strip()
    return CalloutMetadata(callout_type=callout_type or "Note", title=title, body=body)
