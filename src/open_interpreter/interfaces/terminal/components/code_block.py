from rich.box import MINIMAL
from rich.console import Group
from rich.panel import Panel
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .base_block import BaseBlock
from .theme import MATERIAL_SYNTAX_THEME, MATERIAL_TOKENS, STANDARD_MARGIN


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
            show_header=False,
            show_footer=False,
            box=None,
            padding=(0, 0),
            expand=True,
            pad_edge=False,
        )
        code_table.add_column(no_wrap=True)

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
            if i == self.active_line and (
                self.highlight_active_line
                if self.highlight_active_line is not None
                else True
            ):
                # This is the active line, print it with a white background
                syntax = Syntax(
                    line,
                    self.language,
                    theme=MATERIAL_SYNTAX_THEME,
                    line_numbers=False,
                    word_wrap=True,
                )
                highlight_style = (
                    f"{MATERIAL_TOKENS['on_primary']} on {MATERIAL_TOKENS['primary']}"
                )
                code_table.add_row(syntax, style=highlight_style)
            else:
                # This is not the active line, print it normally
                syntax = Syntax(
                    line,
                    self.language,
                    theme=MATERIAL_SYNTAX_THEME,
                    line_numbers=False,
                    word_wrap=True,
                )
                code_table.add_row(syntax)

        # Create a panel for the code
        code_panel = Panel(
            code_table,
            box=MINIMAL,
            style=f"on {MATERIAL_TOKENS['code_surface']}",
            border_style=MATERIAL_TOKENS["code_border"],
            padding=(1, 2),
        )

        # Create a panel for the output (if there is any)
        if self.output == "" or self.output == "None":
            output_panel = None
        else:
            output_text = Text(
                self.output,
                style=f"{MATERIAL_TOKENS['on_surface']} on {MATERIAL_TOKENS['output_surface']}",
            )
            output_panel = Panel(
                output_text,
                box=MINIMAL,
                style=f"on {MATERIAL_TOKENS['output_surface']}",
                border_style=MATERIAL_TOKENS["output_border"],
                padding=(1, 2),
                title="Console output",
                title_align="left",
            )

        # Create a group with the code table and output panel
        group_items = [code_panel]
        if output_panel:
            group_items.append(output_panel)

        group = Group(*group_items)

        if self.margin_top:
            group = Padding(group, STANDARD_MARGIN)

        # Update the live display
        self.live.update(group)
        self.live.refresh()
