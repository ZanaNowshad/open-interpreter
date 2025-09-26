from typing import Optional

from rich.box import MINIMAL
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .base_block import BaseBlock
from .theme_tokens import ThemeTokens, get_theme


class CodeBlock(BaseBlock):
    """
    Code Blocks display code and outputs in different languages. You can also set the active_line!
    """

    def __init__(
        self,
        interpreter=None,
        theme: Optional[str | ThemeTokens] = None,
    ):
        super().__init__(theme)

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

    def refresh(
        self,
        cursor: bool = True,
        theme: Optional[str | ThemeTokens] = None,
    ) -> None:
        if theme is not None:
            self._theme = get_theme(theme)

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
            if i == self.active_line and (
                self.highlight_active_line
                if self.highlight_active_line is not None
                else True
            ):
                # This is the active line, print it with a white background
                syntax = Syntax(
                    line,
                    self.language,
                    theme=self.theme.code_active_line_theme,
                    line_numbers=False,
                    word_wrap=True,
                )
                code_table.add_row(syntax, style=self.theme.code_active_line_style)
            else:
                # This is not the active line, print it normally
                syntax = Syntax(
                    line,
                    self.language,
                    theme=self.theme.code_default_theme,
                    line_numbers=False,
                    word_wrap=True,
                )
                code_table.add_row(syntax)

        # Create a panel for the code
        border_style = (
            self.theme.focus_border_style if cursor or self.focused else self.theme.code_border_style
        )
        code_panel = Panel(
            code_table,
            box=MINIMAL,
            style=self.theme.code_panel_style,
            border_style=border_style,
        )

        # Create a panel for the output (if there is any)
        if self.output == "" or self.output == "None":
            output_panel = ""
        else:
            output_panel = Panel(
                self.output,
                box=MINIMAL,
                style=self.theme.code_output_style,
            )

        # Create a group with the code table and output panel
        group_items = [code_panel, output_panel]
        if self.margin_top:
            # This adds some space at the top. Just looks good!
            group_items = [""] + group_items
        group = Group(*group_items)

        # Update the live display
        self.live.update(group)
        self.live.refresh()
