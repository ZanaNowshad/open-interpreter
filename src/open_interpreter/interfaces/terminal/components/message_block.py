import re

from rich.box import MINIMAL
from rich.markdown import Markdown
from rich.panel import Panel

from .base_block import BaseBlock
from .theme_tokens import ThemeTokens, get_theme


class MessageBlock(BaseBlock):
    def __init__(self, theme: str | ThemeTokens | None = None):
        super().__init__(theme)

        self.type = "message"
        self.message = ""

    def refresh(self, cursor=True, theme: str | ThemeTokens | None = None):
        if theme is not None:
            self._theme = get_theme(theme)

        # De-stylize any code blocks in markdown,
        # to differentiate from our Code Blocks
        content = textify_markdown_code_blocks(self.message)

        if cursor:
            content += "●"

        markdown = Markdown(content.strip(), style=self.theme.message_text_style)
        border_style = (
            self.theme.focus_border_style if cursor or self.focused else self.theme.message_border_style
        )
        panel = Panel(
            markdown,
            box=MINIMAL,
            style=self.theme.message_panel_style,
            border_style=border_style,
        )
        self.live.update(panel)
        self.live.refresh()


def textify_markdown_code_blocks(text):
    """
    To distinguish CodeBlocks from markdown code, we simply turn all markdown code
    (like '```python...') into text code blocks ('```text') which makes the code black and white.
    """
    replacement = "```text"
    lines = text.split("\n")
    inside_code_block = False

    for i in range(len(lines)):
        # If the line matches ``` followed by optional language specifier
        if re.match(r"^```(\w*)$", lines[i].strip()):
            inside_code_block = not inside_code_block

            # If we just entered a code block, replace the marker
            if inside_code_block:
                lines[i] = replacement

    return "\n".join(lines)
