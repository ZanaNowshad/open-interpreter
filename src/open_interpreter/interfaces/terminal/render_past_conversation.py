"""
This is all messed up.... Uses the old streaming structure.
"""


import itertools

from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .utils.display_markdown_message import display_markdown_message


def render_past_conversation(messages, page_size=200):
    # This is a clone of the terminal interface.
    # So we should probably find a way to deduplicate...

    active_block = None
    render_cursor = False
    ran_code_block = False
    syntax_cache = {}
    rendered_count = 0

    messages_iter = iter(messages)

    def prompt_for_more(rendered_count):
        try:
            response = input(
                f"\n-- Displayed {rendered_count} transcript chunks. Press <enter> to load more, or type 'q' to stop: "
            )
        except (EOFError, KeyboardInterrupt):
            return False
        return response.strip().lower() not in {"q", "quit", "exit"}

    while True:
        page = list(itertools.islice(messages_iter, page_size))
        if not page:
            break

        for chunk in page:
            # Only addition to the terminal interface:
            if chunk["role"] == "user":
                if active_block:
                    active_block.end()
                    active_block = None
                print(">", chunk["content"])
                continue

            # Message
            if chunk["type"] == "message":
                if active_block is None or active_block.type != "message":
                    if active_block:
                        active_block.end()
                    active_block = MessageBlock()
                render_cursor = True
                active_block.message += chunk["content"]
                active_block.refresh(cursor=render_cursor)
                continue

            # Code
            if chunk["type"] == "code":
                if active_block is None or active_block.type != "code" or ran_code_block:
                    if active_block:
                        active_block.end()
                    active_block = CodeBlock()
                    active_block.syntax_cache = syntax_cache
                ran_code_block = False
                render_cursor = True

                if "format" in chunk:
                    active_block.language = chunk["format"]
                if "content" in chunk:
                    active_block.code += chunk["content"]
                if "active_line" in chunk:
                    active_block.active_line = chunk["active_line"]
                active_block.refresh(cursor=render_cursor)
                continue

            # Console
            if chunk["type"] == "console" and active_block:
                ran_code_block = True
                render_cursor = False
                active_block.output += "\n" + chunk["content"]
                active_block.output = active_block.output.strip()  # <- Aesthetic choice
                active_block.refresh(cursor=render_cursor)

        rendered_count += len(page)

        if len(page) < page_size:
            break

        if not prompt_for_more(rendered_count):
            break

    if active_block:
        active_block.end()
