import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Callable, Optional, Sequence

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

from ..core.utils.system_debug_info import system_info
from .utils.count_tokens import count_messages_tokens
from .utils.export_to_markdown import export_to_markdown


console = Console()

STATUS_META = {
    "info": {"color": "cyan", "icon": "ℹ", "label": "Info"},
    "success": {"color": "green", "icon": "✔", "label": "Success"},
    "warning": {"color": "yellow", "icon": "⚠", "label": "Warning"},
    "error": {"color": "red", "icon": "✖", "label": "Error"},
}

ACTION_STYLES = {
    "open": "bold white on dark_green",
    "copy path": "bold white on dark_cyan",
    "export": "bold white on dark_magenta",
}

DEFAULT_ACTIONS = ("open", "copy path", "export")


def _render_action_chips(actions: Sequence[str]) -> Text:
    chips = Text()
    for action in actions:
        if chips:
            chips.append(" ")
        style = ACTION_STYLES.get(action.lower(), "bold white on grey37")
        chip = Text(f" {action.title()} ", style=style)
        chips.append_text(chip)
    return chips


def _display_magic_panel(
    self,
    body: str,
    *,
    status: str = "info",
    path: Optional[str] = None,
    actions: Optional[Sequence[str]] = None,
) -> None:
    meta = STATUS_META.get(status, STATUS_META["info"])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_actions = tuple(actions or ())

    if getattr(self, "plain_text_display", False):
        plain_lines = [f"[{meta['label']}] {body.strip()}"]
        plain_lines.append(f"Timestamp: {timestamp}")
        if path:
            plain_lines.append(f"Path: {path}")
        if normalized_actions:
            plain_lines.append("Actions: " + " | ".join(action.title() for action in normalized_actions))
        self.display_message("\n".join(plain_lines))
        return

    content_parts = []
    if body:
        content_parts.append(Markdown(body))
    if path:
        path_text = Text.assemble(("Path: ", "bold"), (path, "cyan"))
        content_parts.append(path_text)
    if normalized_actions:
        content_parts.append(_render_action_chips(normalized_actions))

    if not content_parts:
        content_parts.append(Text(""))

    panel = Panel(
        Group(*content_parts),
        title=f"[{meta['color']}]{meta['icon']} {meta['label']}[/]",
        subtitle=f"[dim]{timestamp}[/]",
        border_style=meta["color"],
    )
    console.print(panel)


def _run_export_with_progress(
    self,
    description: str,
    total_steps: int,
    worker: Callable[[Optional[Progress], Optional[int]], int],
) -> int:
    if getattr(self, "plain_text_display", False) or total_steps <= 0:
        return worker(None, None)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        transient=True,
        console=console,
    )

    with progress as progress_display:
        task_id = progress_display.add_task(description, total=total_steps)
        return worker(progress_display, task_id)


def handle_undo(self, arguments):
    # Removes all messages after the most recent user entry (and the entry itself).
    # Therefore user can jump back to the latest point of conversation.
    # Also gives a visual representation of the messages removed.

    if len(self.messages) == 0:
        return
    # Find the index of the last 'role': 'user' entry
    last_user_index = None
    for i, message in enumerate(self.messages):
        if message.get("role") == "user":
            last_user_index = i

    removed_messages = []

    # Remove all messages after the last 'role': 'user'
    if last_user_index is not None:
        removed_messages = self.messages[last_user_index:]
        self.messages = self.messages[:last_user_index]

    if not removed_messages:
        _display_magic_panel(
            self,
            "No user messages were available to undo.",
            status="warning",
        )
        return

    removed_lines = []
    for message in removed_messages:
        if "content" in message and message["content"] is not None:
            removed_lines.append(
                f"- Removed message: `\"{message['content'][:30]}...\"`"
            )
        elif "function_call" in message:
            removed_lines.append("- Removed code block")

    body = "\n".join(removed_lines)
    _display_magic_panel(
        self,
        body or "Previous exchange removed from history.",
        status="warning",
    )


def handle_help(self, arguments):
    commands_description = {
        "%% [commands]": "Run commands in system shell.",
        "%verbose [true/false]": "Toggle verbose mode. Without arguments or with 'true', it enters verbose mode. With 'false', it exits verbose mode.",
        "%reset": "Reset the current session.",
        "%undo": "Remove previous messages and their response from the message history.",
        "%save_message [path]": "Save messages to a specified JSON path. Defaults to 'messages.json'.",
        "%load_message [path]": "Load messages from a specified JSON path. Defaults to 'messages.json'.",
        "%tokens [prompt]": "EXPERIMENTAL: Estimate tokens for the next request and optionally include an additional prompt.",
        "%help": "Show this help message.",
        "%info": "Show system and interpreter information.",
        "%jupyter": "Export the conversation to a Jupyter notebook with progress feedback and quick actions.",
        "%markdown [path]": "Export the conversation to Markdown with progress feedback. Defaults to the Downloads folder.",
    }

    body_lines = ["**Available Commands:**", ""]

    for cmd, desc in commands_description.items():
        body_lines.append(f"- `{cmd}`: {desc}")

    body_lines.extend(
        [
            "",
            "_Command responses appear in timestamped panels with quick actions to open files, copy their paths, or trigger exports._",
            "_Long-running exports surface ephemeral progress toasts before posting their completion summary here._",
            "",
            "For further assistance, please join our community Discord or consider contributing to the project's development.",
        ]
    )

    _display_magic_panel(self, "\n".join(body_lines), status="info")


def handle_verbose(self, arguments=None):
    if arguments == "" or arguments == "true":
        _display_magic_panel(
            self,
            "Verbose mode enabled. Streaming chunks will now be logged to the console.",
            status="success",
        )
        print("\n\nCurrent messages:\n")
        for message in self.messages:
            message = message.copy()
            if message["type"] == "image" and message.get("format") not in [
                "path",
                "description",
            ]:
                message["content"] = (
                    message["content"][:30] + "..." + message["content"][-30:]
                )
            print(message, "\n")
        print("\n")
        self.verbose = True
    elif arguments == "false":
        _display_magic_panel(
            self,
            "Verbose mode disabled.",
            status="success",
        )
        self.verbose = False
    else:
        _display_magic_panel(
            self,
            "Unknown argument supplied to `%verbose`. Use `true` or `false`.",
            status="error",
        )


def handle_debug(self, arguments=None):
    if arguments == "" or arguments == "true":
        _display_magic_panel(
            self,
            "Debug mode enabled. Raw message objects will be printed below.",
            status="success",
        )
        print("\n\nCurrent messages:\n")
        for message in self.messages:
            message = message.copy()
            if message["type"] == "image" and message.get("format") not in [
                "path",
                "description",
            ]:
                message["content"] = (
                    message["content"][:30] + "..." + message["content"][-30:]
                )
            print(message, "\n")
        print("\n")
        self.debug = True
    elif arguments == "false":
        _display_magic_panel(
            self,
            "Debug mode disabled.",
            status="success",
        )
        self.debug = False
    else:
        _display_magic_panel(
            self,
            "Unknown argument supplied to `%debug`. Use `true` or `false`.",
            status="error",
        )


def handle_auto_run(self, arguments=None):
    if arguments == "" or arguments == "true":
        _display_magic_panel(
            self,
            "Auto-run enabled. Interpreter will execute approved code without prompting.",
            status="success",
        )
        self.auto_run = True
    elif arguments == "false":
        _display_magic_panel(
            self,
            "Auto-run disabled. Execution will require confirmation.",
            status="success",
        )
        self.auto_run = False
    else:
        _display_magic_panel(
            self,
            "Unknown argument supplied to `%auto_run`. Use `true` or `false`.",
            status="error",
        )


def handle_info(self, arguments):
    system_info(self)


def handle_reset(self, arguments):
    self.reset()
    _display_magic_panel(
        self,
        "Conversation reset. Interpreter state cleared.",
        status="success",
    )


def default_handle(self, command):
    _display_magic_panel(
        self,
        f"Unknown command `%{command}`. Showing help.",
        status="error",
    )
    handle_help(self, command)


def handle_save_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "w") as f:
        json.dump(self.messages, f, indent=2)

    absolute_path = os.path.abspath(json_path)
    _display_magic_panel(
        self,
        f"Conversation saved to `{absolute_path}`.",
        status="success",
        path=absolute_path,
        actions=DEFAULT_ACTIONS,
    )


def handle_load_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "r") as f:
        self.messages = json.load(f)

    absolute_path = os.path.abspath(json_path)
    _display_magic_panel(
        self,
        f"Conversation loaded from `{absolute_path}`.",
        status="success",
        path=absolute_path,
        actions=DEFAULT_ACTIONS,
    )


def handle_count_tokens(self, prompt):
    messages = [{"role": "system", "message": self.system_message}] + self.messages

    outputs = []

    if len(self.messages) == 0:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )
    else:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )

    outputs.append(
        f"**Context tokens:** {conversation_tokens} _(estimated cost: ${conversation_cost:.6f})_"
    )

    if prompt:
        (prompt_tokens, prompt_cost) = count_messages_tokens(
            messages=[prompt], model=self.llm.model
        )
        outputs.append(
            f"**Prompt tokens:** {prompt_tokens} _(estimated cost: ${prompt_cost:.6f})_"
        )

        total_tokens = conversation_tokens + prompt_tokens
        total_cost = conversation_cost + prompt_cost

        outputs.append(
            f"**Total tokens (context + prompt):** {total_tokens} _(estimated cost: ${total_cost:.6f})_"
        )

    outputs.append(
        "_Token estimates are experimental. Please report discrepancies on the [Open Interpreter GitHub repository](https://github.com/OpenInterpreter/open-interpreter)._"
    )

    _display_magic_panel(self, "\n".join(outputs), status="info")


def get_downloads_path():
    if os.name == "nt":
        # For Windows
        downloads = os.path.join(os.environ["USERPROFILE"], "Downloads")
    else:
        # For MacOS and Linux
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        # For some GNU/Linux distros, there's no '~/Downloads' dir by default
        if not os.path.exists(downloads):
            os.makedirs(downloads)
    return downloads


def install_and_import(package):
    try:
        module = __import__(package)
    except ImportError:
        try:
            # Install the package silently with pip
            print("")
            print(f"Installing {package}...")
            print("")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            module = __import__(package)
        except subprocess.CalledProcessError:
            # If pip fails, try pip3
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip3", "install", package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                print(f"Failed to install package {package}.")
                return
    finally:
        globals()[package] = module
    return module


def jupyter(self, arguments):
    # Dynamically install nbformat if not already installed
    nbformat = install_and_import("nbformat")
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

    downloads = get_downloads_path()
    current_time = datetime.now()
    formatted_time = current_time.strftime("%m-%d-%y-%I%M%p")
    filename = f"open-interpreter-{formatted_time}.ipynb"
    notebook_path = os.path.join(downloads, filename)
    nb = new_notebook()

    def _export(progress_display: Optional[Progress], task_id: Optional[int]) -> int:
        cells = []
        if progress_display and task_id is not None:
            progress_display.update(task_id, description="Building notebook cells")

        for msg in self.messages:
            if msg["role"] == "user" and msg["type"] == "message":
                content = f"> {msg['content']}"
                cells.append(new_markdown_cell(content))
            elif msg["role"] == "assistant" and msg["type"] == "message":
                cells.append(new_markdown_cell(msg["content"]))
            elif msg["type"] == "code":
                if "format" in msg and msg["format"]:
                    language = msg["format"]
                else:
                    language = "python"
                code_cell = new_code_cell(msg["content"])
                code_cell.metadata.update({"language": language})
                cells.append(code_cell)

            if progress_display and task_id is not None:
                progress_display.advance(task_id)

        nb["cells"] = cells

        if progress_display and task_id is not None:
            progress_display.update(task_id, description="Writing notebook file")

        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)

        if progress_display and task_id is not None:
            progress_display.advance(task_id)

        return len(cells)

    total_steps = len(self.messages) + 1
    cell_count = _run_export_with_progress(
        self,
        "Exporting Jupyter notebook",
        total_steps=total_steps,
        worker=_export,
    )

    absolute_path = os.path.abspath(notebook_path)
    _display_magic_panel(
        self,
        f"Jupyter notebook exported with {cell_count} cells.",
        status="success",
        path=absolute_path,
        actions=DEFAULT_ACTIONS,
    )


def markdown(self, export_path: str):
    # If it's an empty conversations
    if len(self.messages) == 0:
        _display_magic_panel(
            self,
            "No messages to export yet. Start a conversation before exporting.",
            status="warning",
        )
        return

    # If user doesn't specify the export path, then save the exported PDF in '~/Downloads'
    if not export_path:
        export_path = get_downloads_path() + f"/{self.conversation_filename[:-4]}md"

    export_path = os.path.abspath(export_path)

    def _export(progress_display: Optional[Progress], task_id: Optional[int]) -> int:
        if progress_display and task_id is not None:
            progress_display.update(task_id, description="Compiling transcript")
            progress_display.advance(task_id)
            progress_display.update(task_id, description="Writing Markdown")

        export_to_markdown(self.messages, export_path, announce=False)

        if progress_display and task_id is not None:
            progress_display.advance(task_id)

        return len(self.messages)

    message_count = _run_export_with_progress(
        self,
        "Preparing Markdown export",
        total_steps=2,
        worker=_export,
    )

    _display_magic_panel(
        self,
        f"Markdown transcript exported ({message_count} messages).",
        status="success",
        path=export_path,
        actions=DEFAULT_ACTIONS,
    )


def handle_magic_command(self, user_input):
    # Handle shell
    if user_input.startswith("%%"):
        code = user_input[2:].strip()
        self.computer.run("shell", code, stream=False, display=True)
        print("")
        return

    # split the command into the command and the arguments, by the first whitespace
    switch = {
        "help": handle_help,
        "verbose": handle_verbose,
        "debug": handle_debug,
        "auto_run": handle_auto_run,
        "reset": handle_reset,
        "save_message": handle_save_message,
        "load_message": handle_load_message,
        "undo": handle_undo,
        "tokens": handle_count_tokens,
        "info": handle_info,
        "jupyter": jupyter,
        "markdown": markdown,
    }

    user_input = user_input[1:].strip()  # Capture the part after the `%`
    command = user_input.split(" ")[0]
    arguments = user_input[len(command) :].strip()

    if command == "debug":
        print(
            "\n`%debug` / `--debug_mode` has been renamed to `%verbose` / `--verbose`.\n"
        )
        time.sleep(1.5)
        command = "verbose"

    action = switch.get(command)
    if action:
        action(self, arguments)
    else:
        default_handle(self, command)
