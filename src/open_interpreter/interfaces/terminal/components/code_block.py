from rich.box import MINIMAL
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .base_block import BaseBlock


class CodeBlock(BaseBlock):
    """
    Code Blocks display code and outputs in different languages. You can also set the active_line!
    """

    def __init__(self, interpreter=None):
        super().__init__()

        self.type = "code"
        self.highlight_active_line = (
            interpreter.highlight_active_line if interpreter else None
        )

        # A shared cache used for pre-rendered syntax objects. This is optional
        # and is primarily populated by utilities that replay past
        # conversations.
        self.syntax_cache = None

        # Define these for IDE auto-completion
        self.language = ""
        self.output = ""
        self.code = ""
        self.active_line = None
        self.margin_top = True

    def end(self):
        self.active_line = None
        self.refresh(cursor=False)
        super().end()

    def refresh(self, cursor=True):
        if not self.code and not self.output:
            return

        # Get code
        code = self.code

        # Create a table for the code
        code_table = Table(
            show_header=False, show_footer=False, box=None, padding=0, expand=True
        )
        code_table.add_column()

        # Add cursor only if active line highliting is true
        if cursor and (
            self.highlight_active_line
            if self.highlight_active_line is not None
            else True
        ):
            code += "●"

        # Add each line of code to the table
        code_lines = code.strip().split("\n")
        for i, line in enumerate(code_lines, start=1):
            is_active_line = (
                i == self.active_line
                and (
                    self.highlight_active_line
                    if self.highlight_active_line is not None
                    else True
                )
            )

            theme = "bw" if is_active_line else "monokai"
            cache_key = None

            if self.syntax_cache is not None:
                cache_key = (self.language, line, theme)
                syntax = self.syntax_cache.get(cache_key)
            else:
                syntax = None

            if syntax is None:
                syntax = Syntax(
                    line,
                    self.language,
                    theme=theme,
                    line_numbers=False,
                    word_wrap=True,
                )

                if cache_key and self.syntax_cache is not None:
                    self.syntax_cache[cache_key] = syntax

            if is_active_line:
                code_table.add_row(syntax, style="black on white")
            else:
                code_table.add_row(syntax)

        # Create a panel for the code
        code_panel = Panel(code_table, box=MINIMAL, style="on #272722")

        # Create a panel for the output (if there is any)
        if self.output == "" or self.output == "None":
            output_panel = ""
        else:
            output_panel = Panel(self.output, box=MINIMAL, style="#FFFFFF on #3b3b37")

        # Create a group with the code table and output panel
        group_items = [code_panel, output_panel]
        if self.margin_top:
            # This adds some space at the top. Just looks good!
            group_items = [""] + group_items
        group = Group(*group_items)

        # Update the live display
        self.live.update(group)
        self.live.refresh()
