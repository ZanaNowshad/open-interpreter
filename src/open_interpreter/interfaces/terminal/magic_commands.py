import importlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from ..core.utils.system_debug_info import system_info
from .utils.count_tokens import count_messages_tokens
from .utils.export_to_markdown import export_to_markdown


@dataclass(frozen=True)
class CommandMetadata:
    """Serializable data describing a magic command."""

    name: str
    syntax: str
    description: str
    category: str
    icon: str
    shortcut: Optional[str] = None
    state: Optional[str] = None
    palette_snippet: Optional[str] = None
    insertable: bool = True


@dataclass(frozen=True)
class MagicCommand:
    """Declarative definition for a magic command handler."""

    name: str
    syntax: str
    description: str
    handler: Callable[[object, str], None]
    category: str
    icon: str
    shortcut: Optional[str] = None
    aliases: Sequence[str] = ()
    palette_snippet: Optional[str] = None
    state_getter: Optional[Callable[[object], str]] = None

    def to_metadata(self, interpreter: object) -> CommandMetadata:
        state = self.state_getter(interpreter) if self.state_getter else None
        snippet = self.palette_snippet or f"%{self.name} "
        return CommandMetadata(
            name=self.name,
            syntax=self.syntax,
            description=self.description,
            category=self.category,
            icon=self.icon,
            shortcut=self.shortcut,
            state=state,
            palette_snippet=snippet,
            insertable=True,
        )


def handle_undo(self, arguments: str) -> None:
    """Remove the most recent user interaction from the conversation."""

    if len(self.messages) == 0:
        return

    last_user_index = None
    for i, message in enumerate(self.messages):
        if message.get("role") == "user":
            last_user_index = i

    removed_messages = []

    if last_user_index is not None:
        removed_messages = self.messages[last_user_index:]
        self.messages = self.messages[:last_user_index]

    print("")

    for message in removed_messages:
        if "content" in message and message["content"] is not None:
            self.display_message(
                f"**Removed message:** `\"{message['content'][:30]}...\"`"
            )
        elif "function_call" in message:
            self.display_message("**Removed codeblock**")

    print("")


def handle_help(self, arguments: str) -> None:
    catalog = get_magic_command_catalog(self)

    lines = ["> **Available Commands:**\n\n"]
    for category, payload in catalog.items():
        icon = payload["icon"]
        lines.append(f"### {icon} {category}\n")
        for entry in payload["commands"]:
            shortcut = f" _(Shortcut: {entry.shortcut})" if entry.shortcut else ""
            state = f" _(State: {entry.state})" if entry.state else ""
            lines.append(
                f"- `{entry.syntax}` — {entry.description}{shortcut}{state}\n"
            )
        lines.append("\n")

    lines.append(
        "For further assistance, please join our community Discord or consider "
        "contributing to the project's development."
    )

    self.display_message("".join(lines))


def handle_verbose(self, arguments: Optional[str] = None) -> None:
    if arguments == "" or arguments == "true":
        self.display_message("> Entered verbose mode")
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
        self.display_message("> Exited verbose mode")
        self.verbose = False
    else:
        self.display_message("> Unknown argument to verbose command.")


def handle_debug(self, arguments: Optional[str] = None) -> None:
    if arguments == "" or arguments == "true":
        self.display_message("> Entered debug mode")
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
        self.display_message("> Exited verbose mode")
        self.debug = False
    else:
        self.display_message("> Unknown argument to debug command.")


def handle_auto_run(self, arguments: Optional[str] = None) -> None:
    if arguments == "" or arguments == "true":
        self.display_message("> Entered auto_run mode")
        self.auto_run = True
    elif arguments == "false":
        self.display_message("> Exited auto_run mode")
        self.auto_run = False
    else:
        self.display_message("> Unknown argument to auto_run command.")


def handle_info(self, arguments: str) -> None:
    system_info(self)


def handle_reset(self, arguments: str) -> None:
    self.reset()
    self.display_message("> Reset Done")


def default_handle(self, arguments: str) -> None:
    self.display_message("> Unknown command")
    handle_help(self, arguments)


def handle_save_message(self, json_path: str) -> None:
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(self.messages, f, indent=2)

    self.display_message(f"> messages json export to {os.path.abspath(json_path)}")


def handle_load_message(self, json_path: str) -> None:
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "r", encoding="utf-8") as f:
        self.messages = json.load(f)

    self.display_message(f"> messages json loaded from {os.path.abspath(json_path)}")


def handle_count_tokens(self, prompt: str) -> None:
    messages = [{"role": "system", "message": self.system_message}] + self.messages

    outputs: List[str] = []

    if len(self.messages) == 0:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )
    else:
        (conversation_tokens, conversation_cost) = count_messages_tokens(
            messages=messages, model=self.llm.model
        )

    outputs.append(
        (
            f"> Tokens sent with next request as context: {conversation_tokens} "
            f"(Estimated Cost: ${conversation_cost})"
        )
    )

    if prompt:
        (prompt_tokens, prompt_cost) = count_messages_tokens(
            messages=[prompt], model=self.llm.model
        )
        outputs.append(
            f"> Tokens used by this prompt: {prompt_tokens} (Estimated Cost: ${prompt_cost})"
        )

        total_tokens = conversation_tokens + prompt_tokens
        total_cost = conversation_cost + prompt_cost
        outputs.append(
            f"> Total tokens for next request with this prompt: {total_tokens} "
            f"(Estimated Cost: ${total_cost})"
        )

    outputs.append(
        "**Note**: This functionality is currently experimental and may not be "
        "accurate. Please report any issues you find to the "
        "[Open Interpreter GitHub repository](https://github.com/OpenInterpreter/open-interpreter)."
    )

    self.display_message("\n".join(outputs))


def get_downloads_path() -> str:
    if os.name == "nt":
        downloads = os.path.join(os.environ["USERPROFILE"], "Downloads")
    else:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(downloads):
            os.makedirs(downloads)
    return downloads


def install_and_import(package: str):
    if importlib.util.find_spec(package) is None:
        print("")
        print(f"Installing {package}...")
        print("")
        command = [sys.executable, "-m", "pip", "install", package]
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            fallback = [sys.executable, "-m", "pip3", "install", package]
            subprocess.check_call(
                fallback,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    return importlib.import_module(package)


def jupyter(self, arguments: str) -> None:
    nbformat = install_and_import("nbformat")
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

    downloads = get_downloads_path()
    current_time = datetime.now()
    formatted_time = current_time.strftime("%m-%d-%y-%I%M%p")
    filename = f"open-interpreter-{formatted_time}.ipynb"
    notebook_path = os.path.join(downloads, filename)
    nb = new_notebook()
    cells = []

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

    nb["cells"] = cells

    with open(notebook_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print("")
    self.display_message(
        f"Jupyter notebook file exported to {os.path.abspath(notebook_path)}"
    )


def markdown(self, export_path: str) -> None:
    if len(self.messages) == 0:
        print("No messages to export.")
        return

    if not export_path:
        export_path = get_downloads_path() + f"/{self.conversation_filename[:-4]}md"

    export_to_markdown(self.messages, export_path)


MAGIC_COMMANDS: List[MagicCommand] = [
    MagicCommand(
        name="help",
        syntax="%help",
        description="Show this help message.",
        handler=handle_help,
        category="General",
        icon="❓",
        palette_snippet="%help",
    ),
    MagicCommand(
        name="verbose",
        syntax="%verbose [true/false]",
        description="Toggle verbose mode for detailed logs.",
        handler=handle_verbose,
        category="Diagnostics",
        icon="🩺",
        aliases=("debug",),
        palette_snippet="%verbose ",
        state_getter=lambda interpreter: "ON" if getattr(interpreter, "verbose", False) else "OFF",
    ),
    MagicCommand(
        name="reset",
        syntax="%reset",
        description="Reset the current session.",
        handler=handle_reset,
        category="Session",
        icon="🔁",
    ),
    MagicCommand(
        name="undo",
        syntax="%undo",
        description="Remove the last user message and assistant response.",
        handler=handle_undo,
        category="Editing",
        icon="✏️",
    ),
    MagicCommand(
        name="save_message",
        syntax="%save_message [path]",
        description="Export the conversation to a JSON file.",
        handler=handle_save_message,
        category="Export",
        icon="💾",
        palette_snippet="%save_message ",
    ),
    MagicCommand(
        name="load_message",
        syntax="%load_message [path]",
        description="Load a conversation from a JSON file.",
        handler=handle_load_message,
        category="Import",
        icon="📥",
        palette_snippet="%load_message ",
    ),
    MagicCommand(
        name="tokens",
        syntax="%tokens [prompt]",
        description="Estimate token usage and cost for the next request.",
        handler=handle_count_tokens,
        category="Diagnostics",
        icon="🩺",
        palette_snippet="%tokens ",
    ),
    MagicCommand(
        name="info",
        syntax="%info",
        description="Display system and interpreter information.",
        handler=handle_info,
        category="Diagnostics",
        icon="🩺",
    ),
    MagicCommand(
        name="auto_run",
        syntax="%auto_run [true/false]",
        description="Toggle automatic execution of generated code.",
        handler=handle_auto_run,
        category="Execution",
        icon="⚙️",
        palette_snippet="%auto_run ",
        state_getter=lambda interpreter: "ON" if getattr(interpreter, "auto_run", False) else "OFF",
    ),
    MagicCommand(
        name="jupyter",
        syntax="%jupyter",
        description="Export the conversation to a Jupyter notebook.",
        handler=jupyter,
        category="Export",
        icon="💾",
    ),
    MagicCommand(
        name="markdown",
        syntax="%markdown [path]",
        description="Export the conversation to Markdown.",
        handler=markdown,
        category="Export",
        icon="💾",
        palette_snippet="%markdown ",
    ),
]


_COMMAND_LOOKUP: Dict[str, MagicCommand] = {}
for magic_command in MAGIC_COMMANDS:
    _COMMAND_LOOKUP[magic_command.name] = magic_command
    for alias in magic_command.aliases:
        _COMMAND_LOOKUP[alias] = magic_command


def iter_magic_command_metadata(interpreter: object) -> Iterable[CommandMetadata]:
    for command in MAGIC_COMMANDS:
        yield command.to_metadata(interpreter)

    yield CommandMetadata(
        name="shell",
        syntax="%% [command]",
        description="Run a command in the system shell.",
        category="Execution",
        icon="⚙️",
        shortcut="%%",
        palette_snippet="%% ",
        insertable=True,
    )

    yield CommandMetadata(
        name="multi_line_mode",
        syntax="Toggle multi-line input",
        description="Switch interactive input between single-line and multi-line capture.",
        category="Input",
        icon="⌨️",
        shortcut="F2",
        state="ON" if getattr(interpreter, "multi_line", False) else "OFF",
        palette_snippet=None,
        insertable=False,
    )

    yield CommandMetadata(
        name="voice_capture",
        syntax="Toggle voice capture",
        description="Enable or disable speaking assistant responses aloud.",
        category="Input",
        icon="🎙️",
        shortcut="F3",
        state="ON" if getattr(interpreter, "speak_messages", False) else "OFF",
        palette_snippet=None,
        insertable=False,
    )

    yield CommandMetadata(
        name="safe_mode",
        syntax="Cycle safe execution mode",
        description="Cycle safe-mode enforcement between ask, auto, and off.",
        category="Execution",
        icon="⚙️",
        shortcut="F4",
        state=str(getattr(interpreter, "safe_mode", "off") or "off").upper(),
        palette_snippet=None,
        insertable=False,
    )

    yield CommandMetadata(
        name="auto_run_toggle",
        syntax="Toggle automatic execution",
        description="Switch between manual approvals and automatic code execution.",
        category="Execution",
        icon="⚙️",
        shortcut="F5",
        state="ON" if getattr(interpreter, "auto_run", False) else "OFF",
        palette_snippet=None,
        insertable=False,
    )


def get_magic_command_catalog(interpreter: object) -> Dict[str, Dict[str, object]]:
    catalog: Dict[str, Dict[str, object]] = {}
    for entry in iter_magic_command_metadata(interpreter):
        bucket = catalog.setdefault(
            entry.category,
            {"icon": entry.icon, "commands": []},
        )
        bucket["commands"].append(entry)

    for payload in catalog.values():
        payload["commands"].sort(key=lambda item: item.name)

    return dict(sorted(catalog.items(), key=lambda item: item[0]))


def get_magic_command_palette_entries(interpreter: object) -> List[CommandMetadata]:
    return list(iter_magic_command_metadata(interpreter))


def handle_magic_command(self, user_input: str) -> None:
    if user_input.startswith("%%"):
        code = user_input[2:].strip()
        self.computer.run("shell", code, stream=False, display=True)
        print("")
        return

    user_input = user_input[1:].strip()
    if not user_input:
        return
    command = user_input.split(" ")[0]
    arguments = user_input[len(command) :].strip()

    if command == "debug":
        print(
            "\n`%debug` / `--debug_mode` has been renamed to `%verbose` / `--verbose`.\n"
        )
        time.sleep(1.5)
        command = "verbose"

    action = _COMMAND_LOOKUP.get(command)
    if action is None:
        default_handle(self, arguments)
        return

    action.handler(self, arguments)

