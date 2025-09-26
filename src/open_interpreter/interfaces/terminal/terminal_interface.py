"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it.
"""

try:
    import readline
except ImportError:
    pass

import difflib
import os
import platform
import random
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional

from ..core.utils.scan_code import scan_code
from ..core.utils.system_debug_info import system_info
from ..core.utils.truncate_output import truncate_output
from .components.code_block import CodeBlock
from .components.message_block import MessageBlock
from .components.ui import ReviewPanel, status_bar
from .magic_commands import handle_magic_command
from .utils.check_for_package import check_for_package
from .utils.cli_input import cli_input
from .utils.display_output import display_output
from .utils.find_image_path import find_image_path

# Add examples to the readline history
examples = [
    "How many files are on my desktop?",
    "What time is it in Seattle?",
    "Make me a simple Pomodoro app.",
    "Open Chrome and go to YouTube.",
    "Can you set my system to light mode?",
]
random.shuffle(examples)
try:
    for example in examples:
        readline.add_history(example)
except:
    # If they don't have readline, that's fine
    pass


def terminal_interface(interpreter, message):
    # Auto run and offline (this.. this isn't right) don't display messages.
    # Probably worth abstracting this to something like "debug_cli" at some point.
    # If (len(interpreter.messages) == 1), they probably used the advanced "i {command}" entry, so no message should be displayed.
    if (
        not interpreter.auto_run
        and not interpreter.offline
        and not (len(interpreter.messages) == 1)
    ):
        interpreter_intro_message = [
            "**Open Interpreter** will require approval before running code."
        ]

        if interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto":
            if not check_for_package("semgrep"):
                interpreter_intro_message.append(
                    f"**Safe Mode**: {interpreter.safe_mode}\n\n>Note: **Safe Mode** requires `semgrep` (`pip install semgrep`)"
                )
        else:
            interpreter_intro_message.append("Use `interpreter -y` to bypass this.")

        if (
            not interpreter.plain_text_display
        ):  # A proxy/heuristic for standard in mode, which isn't tracked (but prob should be)
            interpreter_intro_message.append("Press `CTRL-C` to exit.")

        interpreter.display_message("\n\n".join(interpreter_intro_message) + "\n")

    if message:
        interactive = False
    else:
        interactive = True

    active_block = None
    voice_subprocess = None

    preferences = _ensure_preferences(interpreter)

    if not interpreter.plain_text_display:
        _update_status_bar(interpreter)

    while True:
        if interactive:
            if (
                len(interpreter.messages) == 1
                and interpreter.messages[-1]["role"] == "user"
                and interpreter.messages[-1]["type"] == "message"
            ):
                # They passed in a message already, probably via "i {command}"!
                message = interpreter.messages[-1]["content"]
                interpreter.messages = interpreter.messages[:-1]
            else:
                ### This is the primary input for Open Interpreter.
                try:
                    message = (
                        cli_input("> ").strip()
                        if interpreter.multi_line
                        else input("> ").strip()
                    )
                except (KeyboardInterrupt, EOFError):
                    # Treat Ctrl-D on an empty line the same as Ctrl-C by exiting gracefully
                    interpreter.display_message("\n\n`Exiting...`")
                    raise KeyboardInterrupt

            try:
                # This lets users hit the up arrow key for past messages
                readline.add_history(message)
            except:
                # If the user doesn't have readline (may be the case on windows), that's fine
                pass

        if isinstance(message, str):
            # This is for the terminal interface being used as a CLI — messages are strings.
            # This won't fire if they're in the python package, display=True, and they passed in an array of messages (for example).

            if message == "":
                # Ignore empty messages when user presses enter without typing anything
                continue

            if message.startswith("%") and interactive:
                handle_magic_command(interpreter, message)
                continue

            # Many users do this
            if message.strip() == "interpreter --local":
                print("Please exit this conversation, then run `interpreter --local`.")
                continue
            if message.strip() == "pip install --upgrade open-interpreter":
                print(
                    "Please exit this conversation, then run `pip install --upgrade open-interpreter`."
                )
                continue

            if (
                interpreter.llm.supports_vision
                or interpreter.llm.vision_renderer != None
            ):
                # Is the input a path to an image? Like they just dragged it into the terminal?
                image_path = find_image_path(message)

                ## If we found an image, add it to the message
                if image_path:
                    # Add the text interpreter's message history
                    interpreter.messages.append(
                        {
                            "role": "user",
                            "type": "message",
                            "content": message,
                        }
                    )

                    # Pass in the image to interpreter in a moment
                    message = {
                        "role": "user",
                        "type": "image",
                        "format": "path",
                        "content": image_path,
                    }

        try:
            for chunk in interpreter.chat(message, display=False, stream=True):
                yield chunk

                # Is this for thine eyes?
                if "recipient" in chunk and chunk["recipient"] != "user":
                    continue

                if interpreter.verbose:
                    print("Chunk in `terminal_interface`:", chunk)

                # Comply with PyAutoGUI fail-safe for OS mode
                # so people can turn it off by moving their mouse to a corner
                if interpreter.os:
                    if (
                        chunk.get("format") == "output"
                        and "failsafeexception" in chunk["content"].lower()
                    ):
                        print("Fail-safe triggered (mouse in one of the four corners).")
                        break

                if chunk["type"] == "review" and chunk.get("content"):
                    # Specialized models can emit a code review.
                    print(chunk.get("content"), end="", flush=True)

                # Execution notice
                if chunk["type"] == "confirmation":
                    if not interpreter.auto_run:
                        # OI is about to execute code. The user wants to approve this

                        # End the active code block so you can run input() below it
                        if active_block and not interpreter.plain_text_display:
                            active_block.refresh(cursor=False)
                            active_block.end()
                            active_block = None

                        code_to_run = chunk["content"]
                        language = code_to_run["format"]
                        code = code_to_run["content"]

                        preferences = _ensure_preferences(interpreter)

                        panel = ReviewPanel(
                            code_origin=_determine_code_origin(interpreter),
                            diff_summary=_summarize_diff(
                                preferences.get("last_executed_code"), code
                            ),
                            risk_level=_assess_risk(code, preferences.get("scan", False)),
                            runtime_estimate=_estimate_runtime(code),
                            scan_enabled=preferences.get("scan", False),
                            default_action=preferences.get("default_action", "approve"),
                            preferences=preferences,
                            safe_mode=interpreter.safe_mode,
                            status_callback=lambda: _update_status_bar(interpreter),
                        )

                        decision = panel.prompt()

                        if decision.default_action:
                            preferences["default_action"] = decision.default_action

                        preferences["scan"] = decision.scan_enabled

                        action = decision.action

                        if action == "skip":
                            preferences["last_decision"] = "Skipped"
                            if interpreter.safe_mode == "off":
                                preferences["last_scan_status"] = _log_scan_result(
                                    interpreter,
                                    {"status": "not_required", "summary": "Safe mode disabled."},
                                    language,
                                )
                            else:
                                preferences["last_scan_status"] = _log_scan_result(
                                    interpreter, None, language
                                )
                            _log_transcript(
                                interpreter,
                                label="APPROVAL",
                                message="Execution skipped.",
                                emoji="no_entry_sign",
                                style="red",
                            )
                            interpreter.messages.append(
                                {
                                    "role": "user",
                                    "type": "message",
                                    "content": "I have declined to run this code.",
                                }
                            )
                            _update_status_bar(interpreter)
                            break

                        if action == "edit":
                            code = _launch_editor(code, language)
                            interpreter.messages[-1]["content"] = code
                            preferences["last_decision"] = "Edited"
                            _log_transcript(
                                interpreter,
                                label="APPROVAL",
                                message="Code edited prior to execution.",
                                emoji="memo",
                                style="cyan",
                            )
                        else:
                            preferences["last_decision"] = "Approved"
                            _log_transcript(
                                interpreter,
                                label="APPROVAL",
                                message="Execution approved.",
                                emoji="white_check_mark",
                                style="green",
                            )

                        scan_summary = None
                        if decision.scan_enabled and interpreter.safe_mode != "off":
                            scan_summary = scan_code(code, language, interpreter)
                            preferences["last_scan_status"] = _log_scan_result(
                                interpreter, scan_summary, language
                            )
                        elif interpreter.safe_mode == "off":
                            preferences["last_scan_status"] = _log_scan_result(
                                interpreter,
                                {"status": "not_required", "summary": "Safe mode disabled."},
                                language,
                            )
                        else:
                            preferences["last_scan_status"] = _log_scan_result(
                                interpreter, None, language
                            )

                        preferences["last_executed_code"] = code
                        _update_status_bar(interpreter)

                        active_block = CodeBlock(interpreter)
                        active_block.margin_top = False  # <- Aesthetic choice
                        active_block.language = language
                        active_block.code = code

                # Plain text mode
                if interpreter.plain_text_display:
                    if "start" in chunk or "end" in chunk:
                        print("")
                    if chunk["type"] in ["code", "console"] and "format" in chunk:
                        if "start" in chunk:
                            print("```" + chunk["format"], flush=True)
                        if "end" in chunk:
                            print("```", flush=True)
                    if chunk.get("format") != "active_line":
                        print(chunk.get("content", ""), end="", flush=True)
                    continue

                if "end" in chunk and active_block:
                    active_block.refresh(cursor=False)

                    if chunk["type"] in [
                        "message",
                        "console",
                    ]:  # We don't stop on code's end — code + console output are actually one block.
                        active_block.end()
                        active_block = None

                # Assistant message blocks
                if chunk["type"] == "message":
                    if "start" in chunk:
                        active_block = MessageBlock()
                        render_cursor = True

                    if "content" in chunk:
                        active_block.message += chunk["content"]

                    if "end" in chunk and interpreter.os:
                        last_message = interpreter.messages[-1]["content"]

                        # Remove markdown lists and the line above markdown lists
                        lines = last_message.split("\n")
                        i = 0
                        while i < len(lines):
                            # Match markdown lists starting with hyphen, asterisk or number
                            if re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                                del lines[i]
                                if i > 0:
                                    del lines[i - 1]
                                    i -= 1
                            else:
                                i += 1
                        message = "\n".join(lines)
                        # Replace newlines with spaces, escape double quotes and backslashes
                        sanitized_message = (
                            message.replace("\\", "\\\\")
                            .replace("\n", " ")
                            .replace('"', '\\"')
                        )

                        # Display notification in OS mode
                        interpreter.computer.os.notify(sanitized_message)

                        # Speak message aloud
                        if platform.system() == "Darwin" and interpreter.speak_messages:
                            if voice_subprocess:
                                voice_subprocess.terminate()
                            voice_subprocess = subprocess.Popen(
                                [
                                    "osascript",
                                    "-e",
                                    f'say "{sanitized_message}" using "Fred"',
                                ]
                            )
                        else:
                            pass
                            # User isn't on a Mac, so we can't do this. You should tell them something about that when they first set this up.
                            # Or use a universal TTS library.

                # Assistant code blocks
                elif chunk["role"] == "assistant" and chunk["type"] == "code":
                    if "start" in chunk:
                        active_block = CodeBlock()
                        active_block.language = chunk["format"]
                        render_cursor = True

                    if "content" in chunk:
                        active_block.code += chunk["content"]

                # Computer can display visual types to user,
                # Which sometimes creates more computer output (e.g. HTML errors, eventually)
                if (
                    chunk["role"] == "computer"
                    and "content" in chunk
                    and (
                        chunk["type"] == "image"
                        or ("format" in chunk and chunk["format"] == "html")
                        or ("format" in chunk and chunk["format"] == "javascript")
                    )
                ):
                    if (interpreter.os == True) and (interpreter.verbose == False):
                        # We don't display things to the user in OS control mode, since we use vision to communicate the screen to the LLM so much.
                        # But if verbose is true, we do display it!
                        continue

                    assistant_code_blocks = [
                        m
                        for m in interpreter.messages
                        if m.get("role") == "assistant" and m.get("type") == "code"
                    ]
                    if assistant_code_blocks:
                        code = assistant_code_blocks[-1].get("content")
                        if any(
                            text in code
                            for text in [
                                "computer.display.view",
                                "computer.display.screenshot",
                                "computer.view",
                                "computer.screenshot",
                            ]
                        ):
                            # If the last line of the code is a computer.view command, don't display it.
                            # The LLM is going to see it, the user doesn't need to.
                            continue

                    # Display and give extra output back to the LLM
                    extra_computer_output = display_output(chunk)

                    # We're going to just add it to the messages directly, not changing `recipient` here.
                    # Mind you, the way we're doing this, this would make it appear to the user if they look at their conversation history,
                    # because we're not adding "recipient: assistant" to this block. But this is a good simple solution IMO.
                    # we just might want to change it in the future, once we're sure that a bunch of adjacent type:console blocks will be rendered normally to text-only LLMs
                    # and that if we made a new block here with "recipient: assistant" it wouldn't add new console outputs to that block (thus hiding them from the user)

                    if (
                        interpreter.messages[-1].get("format") != "output"
                        or interpreter.messages[-1]["role"] != "computer"
                        or interpreter.messages[-1]["type"] != "console"
                    ):
                        # If the last message isn't a console output, make a new block
                        interpreter.messages.append(
                            {
                                "role": "computer",
                                "type": "console",
                                "format": "output",
                                "content": extra_computer_output,
                            }
                        )
                    else:
                        # If the last message is a console output, simply append the extra output to it
                        interpreter.messages[-1]["content"] += (
                            "\n" + extra_computer_output
                        )
                        interpreter.messages[-1]["content"] = interpreter.messages[-1][
                            "content"
                        ].strip()

                # Console
                if chunk["type"] == "console":
                    render_cursor = False
                    if "format" in chunk and chunk["format"] == "output":
                        active_block.output += "\n" + chunk["content"]
                        active_block.output = (
                            active_block.output.strip()
                        )  # ^ Aesthetic choice

                        # Truncate output
                        active_block.output = truncate_output(
                            active_block.output,
                            interpreter.max_output,
                            add_scrollbars=False,
                        )  # ^ Notice that this doesn't add the "scrollbars" line, which I think is fine
                    if "format" in chunk and chunk["format"] == "active_line":
                        active_block.active_line = chunk["content"]

                        # Display action notifications if we're in OS mode
                        if interpreter.os and active_block.active_line != None:
                            action = ""

                            code_lines = active_block.code.split("\n")
                            if active_block.active_line < len(code_lines):
                                action = code_lines[active_block.active_line].strip()

                            if action.startswith("computer"):
                                description = None

                                # Extract arguments from the action
                                start_index = action.find("(")
                                end_index = action.rfind(")")
                                if start_index != -1 and end_index != -1:
                                    # (If we found both)
                                    arguments = action[start_index + 1 : end_index]
                                else:
                                    arguments = None

                                # NOTE: Do not put the text you're clicking on screen
                                # (unless we figure out how to do this AFTER taking the screenshot)
                                # otherwise it will try to click this notification!

                                if any(
                                    action.startswith(text)
                                    for text in [
                                        "computer.screenshot",
                                        "computer.display.screenshot",
                                        "computer.display.view",
                                        "computer.view",
                                    ]
                                ):
                                    description = "Viewing screen..."
                                elif action == "computer.mouse.click()":
                                    description = "Clicking..."
                                elif action.startswith("computer.mouse.click("):
                                    if "icon=" in arguments:
                                        text_or_icon = "icon"
                                    else:
                                        text_or_icon = "text"
                                    description = f"Clicking {text_or_icon}..."
                                elif action.startswith("computer.mouse.move("):
                                    if "icon=" in arguments:
                                        text_or_icon = "icon"
                                    else:
                                        text_or_icon = "text"
                                    if (
                                        "click" in active_block.code
                                    ):  # This could be better
                                        description = f"Clicking {text_or_icon}..."
                                    else:
                                        description = f"Mousing over {text_or_icon}..."
                                elif action.startswith("computer.keyboard.write("):
                                    description = f"Typing {arguments}."
                                elif action.startswith("computer.keyboard.hotkey("):
                                    description = f"Pressing {arguments}."
                                elif action.startswith("computer.keyboard.press("):
                                    description = f"Pressing {arguments}."
                                elif action == "computer.os.get_selected_text()":
                                    description = f"Getting selected text."

                                if description:
                                    interpreter.computer.os.notify(description)

                    if "start" in chunk:
                        # We need to make a code block if we pushed out an HTML block first, which would have closed our code block.
                        if not isinstance(active_block, CodeBlock):
                            if active_block:
                                active_block.end()
                            active_block = CodeBlock()

                if active_block:
                    active_block.refresh(cursor=render_cursor)

            # (Sometimes -- like if they CTRL-C quickly -- active_block is still None here)
            if "active_block" in locals():
                if active_block:
                    active_block.end()
                    active_block = None
                    time.sleep(0.1)

            if not interactive:
                # Don't loop
                break

        except KeyboardInterrupt:
            # Exit gracefully
            if "active_block" in locals() and active_block:
                active_block.end()
                active_block = None

            if interactive:
                # (this cancels LLM, returns to the interactive "> " input)
                continue
            else:
                break
        except:
            if interpreter.debug:
                system_info(interpreter)
            raise


def _ensure_preferences(interpreter) -> Dict[str, Any]:
    existing = getattr(interpreter, "terminal_preferences", None)
    if not isinstance(existing, dict):
        existing = {}

    defaults: Dict[str, Any] = {
        "scan": interpreter.safe_mode != "off",
        "default_action": "approve",
        "last_decision": None,
        "last_scan_status": None,
        "last_executed_code": "",
    }

    for key, value in defaults.items():
        existing.setdefault(key, value)

    interpreter.terminal_preferences = existing
    return existing


def _update_status_bar(interpreter) -> None:
    if getattr(interpreter, "plain_text_display", False):
        return
    preferences = _ensure_preferences(interpreter)
    status_bar.update(preferences, interpreter.safe_mode)


def _determine_code_origin(interpreter) -> str:
    model_name = getattr(interpreter.llm, "model", None)
    origin = model_name or "Assistant"
    last_assistant_code = next(
        (
            message
            for message in reversed(interpreter.messages)
            if message.get("role") == "assistant" and message.get("type") == "code"
        ),
        None,
    )
    if last_assistant_code and last_assistant_code.get("metadata"):
        origin = last_assistant_code["metadata"].get("origin", origin)
    return origin


def _summarize_diff(previous_code: Optional[str], current_code: str) -> str:
    if not previous_code:
        return "No previous execution."

    diff_lines = list(
        difflib.unified_diff(
            previous_code.splitlines(),
            current_code.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )
    diff_lines = [line for line in diff_lines if line.strip()]

    if not diff_lines:
        return "No changes since last run."

    max_lines = 12
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + ["..."]
    return "\n".join(diff_lines)


def _assess_risk(code: str, scan_enabled: bool) -> str:
    lowered = code.lower()
    high_risk_patterns = ["rm -rf", "del /q", "shutdown", "format ", "drop table", "sudo"]
    medium_risk_patterns = [
        "subprocess",
        "os.remove",
        "shutil.rmtree",
        "eval(",
        "exec(",
        "while true",
    ]

    risk_level = "Low"
    style = "green"

    if any(pattern in lowered for pattern in high_risk_patterns):
        risk_level = "High"
        style = "red"
    elif any(pattern in lowered for pattern in medium_risk_patterns) or len(code.splitlines()) > 80:
        risk_level = "Moderate"
        style = "yellow"

    suffix = " (scan enabled)" if scan_enabled else " (scan off)"
    return f"[{style}]{risk_level}[/] risk{suffix}"


def _estimate_runtime(code: str) -> str:
    line_count = len([line for line in code.splitlines() if line.strip()])
    long_running_signals = ["time.sleep", "asyncio.sleep", "subprocess.run", "requests.get"]

    if any(signal in code for signal in long_running_signals):
        return "Likely longer (>10s)"
    if line_count <= 10:
        return "Short (<2s)"
    if line_count <= 40:
        return "Moderate (≈5s)"
    return "Extended (>10s)"


def _launch_editor(code: str, language: str) -> str:
    suffix = ".tmp"
    if language:
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "", language.split("/")[-1])
        if sanitized:
            suffix = f".{sanitized}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
        temp_file.write(code.encode())
        temp_file.flush()
        temp_path = temp_file.name

    try:
        subprocess.call([os.environ.get("EDITOR", "vim"), temp_path])
        with open(temp_path, "r") as updated:
            return updated.read()
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _log_transcript(
    interpreter,
    *,
    label: str,
    message: str,
    emoji: str = "memo",
    style: str = "green",
) -> None:
    content = f":{emoji}: [bold {style}][{label}][/bold {style}] {message}"
    entry = {
        "role": "system",
        "type": "message",
        "content": content,
        "recipient": "user",
    }
    interpreter.messages.append(entry)
    interpreter.display_message(content)


def _log_scan_result(
    interpreter,
    scan_result: Optional[Dict[str, Any]],
    language: str,
) -> str:
    language_label = language or "code"

    if not scan_result:
        _log_transcript(
            interpreter,
            label="SCAN",
            message=f"{language_label} scan skipped by user.",
            emoji="shield",
            style="yellow",
        )
        return "Skipped"

    status = str(scan_result.get("status", "unknown")).lower()
    summary = scan_result.get("summary", "") or ""
    output = scan_result.get("output", "") or ""

    if status == "passed":
        message = summary or f"No issues were found in this {language_label} code."
        _log_transcript(
            interpreter,
            label="SCAN",
            message=message,
            emoji="shield",
            style="green",
        )
        return "Passed"

    if status in {"issues", "failed"}:
        snippet = _truncate_text(summary or output)
        detail = f"\n\n```\n{snippet}\n```" if snippet else ""
        _log_transcript(
            interpreter,
            label="SCAN",
            message=f"Potential issues detected in {language_label}.{detail}",
            emoji="shield",
            style="red",
        )
        return "Issues detected"

    if status in {"error", "exception"}:
        message = summary or "Scan encountered an error."
        _log_transcript(
            interpreter,
            label="SCAN",
            message=f"Scan error for {language_label}: {message}",
            emoji="shield",
            style="yellow",
        )
        return "Error"

    if status in {"skipped", "not required", "not_required"}:
        message = summary or f"{language_label} scan skipped."
        _log_transcript(
            interpreter,
            label="SCAN",
            message=message,
            emoji="shield",
            style="yellow",
        )
        if status in {"not required", "not_required"}:
            return "Not required"
        return "Skipped"

    message = summary or f"Scan status: {status}."
    _log_transcript(
        interpreter,
        label="SCAN",
        message=message,
        emoji="shield",
        style="yellow",
    )
    return status.title()


def _truncate_text(text: str, limit: int = 400) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
