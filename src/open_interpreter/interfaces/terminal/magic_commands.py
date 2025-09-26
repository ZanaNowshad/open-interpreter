import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from ..core.utils.system_debug_info import system_info
from .components.theme_tokens import available_themes, get_theme
from .utils.count_tokens import count_messages_tokens
from .utils.export_to_markdown import export_to_markdown
from .utils.transcript import export_transcript


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

    print("")  # Aesthetics.

    # Print out a preview of what messages were removed.
    for message in removed_messages:
        if "content" in message and message["content"] != None:
            self.display_message(
                f"**Removed message:** `\"{message['content'][:30]}...\"`"
            )
        elif "function_call" in message:
            self.display_message(
                f"**Removed codeblock**"
            )  # TODO: Could add preview of code removed here.

    print("")  # Aesthetics.


def handle_help(self, arguments):
    commands_description = {
        "%% [commands]": "help_command_shell",
        "%verbose [true/false]": "help_command_verbose",
        "%auto_run [true/false]": "help_command_auto_run",
        "%debug [true/false]": "help_command_debug",
        "%reset": "help_command_reset",
        "%undo": "help_command_undo",
        "%save_message [path]": "help_command_save",
        "%load_message [path]": "help_command_load",
        "%tokens [prompt]": "help_command_tokens",
        "%help": "help_command_help",
        "%info": "help_command_info",
        "%jupyter": "help_command_jupyter",
        "%markdown [path]": "help_command_markdown",
        "%theme [name]": "help_command_theme",
        "%transcript [path]": "help_command_transcript",
    }

    base_message = [self.ui_strings.get("help_intro")]

    # Add each command and its description to the message
    for cmd, desc in commands_description.items():
        base_message.append(
            f"- `{cmd}`: {self.ui_strings.get(desc)}\n"
        )

    additional_info = [self.ui_strings.get("help_footer")]

    # Combine the base message with the additional info
    full_message = base_message + additional_info

    self.display_message("".join(full_message))


def handle_verbose(self, arguments=None):
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


def handle_debug(self, arguments=None):
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


def handle_auto_run(self, arguments=None):
    if arguments == "" or arguments == "true":
        self.display_message("> Entered auto_run mode")
        self.auto_run = True
    elif arguments == "false":
        self.display_message("> Exited auto_run mode")
        self.auto_run = False
    else:
        self.display_message("> Unknown argument to auto_run command.")


def handle_theme(self, arguments: str) -> None:
    available = ", ".join(sorted(available_themes()))
    theme_name = arguments.strip().lower()

    if theme_name == "":
        self.display_message(self.ui_strings.get("theme_available", available=available))
        return

    try:
        resolved = get_theme(theme_name)
    except KeyError:
        self.display_message(
            self.ui_strings.get("theme_invalid", theme=theme_name, available=available)
        )
        return

    self.display_theme = resolved.name
    self.display_message(self.ui_strings.get("theme_changed", theme=resolved.name))


def handle_transcript(self, export_path: str) -> None:
    if len(self.messages) == 0:
        self.display_message(self.ui_strings.get("transcript_empty"))
        return

    base_name = (
        Path(self.conversation_filename).stem
        if getattr(self, "conversation_filename", None)
        else f"conversation-{int(time.time())}"
    )

    destination = Path(export_path) if export_path else Path(get_downloads_path()) / f"{base_name}-transcript"

    try:
        resolved = export_transcript(self.messages, destination, self.ui_strings)
    except OSError as exc:
        self.display_message(
            self.ui_strings.get("transcript_export_failure", reason=str(exc))
        )
    else:
        self.display_message(
            self.ui_strings.get("transcript_export_success", path=str(resolved.resolve()))
        )


def handle_info(self, arguments):
    system_info(self)


def handle_reset(self, arguments):
    self.reset()
    self.display_message("> Reset Done")


def default_handle(self, arguments):
    self.display_message("> Unknown command")
    handle_help(self, arguments)


def handle_save_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "w") as f:
        json.dump(self.messages, f, indent=2)

    self.display_message(f"> messages json export to {os.path.abspath(json_path)}")


def handle_load_message(self, json_path):
    if json_path == "":
        json_path = "messages.json"
    if not json_path.endswith(".json"):
        json_path += ".json"
    with open(json_path, "r") as f:
        self.messages = json.load(f)

    self.display_message(f"> messages json loaded from {os.path.abspath(json_path)}")


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
        (
            f"> Tokens sent with next request as context: {conversation_tokens} (Estimated Cost: ${conversation_cost})"
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
            f"> Total tokens for next request with this prompt: {total_tokens} (Estimated Cost: ${total_cost})"
        )

    outputs.append(
        f"**Note**: This functionality is currently experimental and may not be accurate. Please report any issues you find to the [Open Interpreter GitHub repository](https://github.com/OpenInterpreter/open-interpreter)."
    )

    self.display_message("\n".join(outputs))


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
    cells = []

    for msg in self.messages:
        if msg["role"] == "user" and msg["type"] == "message":
            # Prefix user messages with '>' to render them as block quotes, so they stand out
            content = f"> {msg['content']}"
            cells.append(new_markdown_cell(content))
        elif msg["role"] == "assistant" and msg["type"] == "message":
            cells.append(new_markdown_cell(msg["content"]))
        elif msg["type"] == "code":
            # Handle the language of the code cell
            if "format" in msg and msg["format"]:
                language = msg["format"]
            else:
                language = "python"  # Default to Python if no format specified
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


def markdown(self, export_path: str):
    # If it's an empty conversations
    if len(self.messages) == 0:
        print("No messages to export.")
        return

    # If user doesn't specify the export path, then save the exported PDF in '~/Downloads'
    if not export_path:
        export_path = get_downloads_path() + f"/{self.conversation_filename[:-4]}md"

    export_to_markdown(self.messages, export_path)


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
        "theme": handle_theme,
        "transcript": handle_transcript,
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

    action = switch.get(
        command, default_handle
    )  # Get the function from the dictionary, or default_handle if not found
    action(self, arguments)  # Execute the function
