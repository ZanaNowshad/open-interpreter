from rich.box import MINIMAL
from rich.panel import Panel

from .base_block import BaseBlock
from ..utils.markdown_pipeline import render_markdown


class MessageBlock(BaseBlock):
    def __init__(self):
        super().__init__()

        self.type = "message"
        self.message = ""

    def refresh(self, cursor=True):
        # De-stylize any code blocks in markdown,
        # to differentiate from our Code Blocks
        markdown = render_markdown(self.message, cursor=cursor)
        panel = Panel(markdown, box=MINIMAL)
        self.live.update(panel)
        self.live.refresh()
