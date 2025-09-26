"""
The terminal interface is just a view. Just handles the very top layer.
If you were to build a frontend this would be a way to do it.
"""

try:
    import readline
except ImportError:
    pass

import os
import platform
import random
import re
import subprocess
import tempfile

from ..core.utils.scan_code import scan_code
from ..core.utils.system_debug_info import system_info
from .components.code_block import CodeBlock
from .history_renderer import ConversationHistoryRenderer
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

    history_renderer = ConversationHistoryRenderer(
        interpreter=interpreter,
        plain_text=interpreter.plain_text_display,
        max_output=getattr(interpreter, "max_output", None),
    )
    voice_subprocess = None

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
                        if (
                            history_renderer.active_block
                            and not interpreter.plain_text_display
                        ):
                            history_renderer.finalize()

                        code_to_run = chunk["content"]
                        language = code_to_run["format"]
                        code = code_to_run["content"]

                        should_scan_code = False

                        if not interpreter.safe_mode == "off":
                            if interpreter.safe_mode == "auto":
                                should_scan_code = True
                            elif interpreter.safe_mode == "ask":
                                response = input(
                                    "  Would you like to scan this code? (y/n)\n\n  "
                                )
                                print("")  # <- Aesthetic choice

                                if response.strip().lower() == "y":
                                    should_scan_code = True

                        if should_scan_code:
                            scan_code(code, language, interpreter)

                        if interpreter.plain_text_display:
                            response = input(
                                "Would you like to run this code? (y/n)\n\n"
                            )
                        else:
                            response = input(
                                "  Would you like to run this code? (y/n)\n\n  "
                            )
                        print("")  # <- Aesthetic choice

                        if response.strip().lower() == "y":
                            # Create a new, identical block where the code will actually be run
                            # Conveniently, the chunk includes everything we need to do this:
                            block = CodeBlock(interpreter)
                            block.margin_top = False  # <- Aesthetic choice
                            block.language = language
                            block.code = code
                            history_renderer.attach_block(block)
                        elif response.strip().lower() == "e":
                            # Edit

                            # Create a temporary file
                            with tempfile.NamedTemporaryFile(
                                suffix=".tmp", delete=False
                            ) as tf:
                                tf.write(code.encode())
                                tf.flush()

                            # Open the temporary file with the default editor
                            subprocess.call([os.environ.get("EDITOR", "vim"), tf.name])

                            # Read the modified code
                            with open(tf.name, "r") as tf:
                                code = tf.read()

                            interpreter.messages[-1]["content"] = code  # Give it code

                            # Delete the temporary file
                            os.unlink(tf.name)
                            block = CodeBlock()
                            block.margin_top = False  # <- Aesthetic choice
                            block.language = language
                            block.code = code
                            history_renderer.attach_block(block)
                        else:
                            # User declined to run code.
                            interpreter.messages.append(
                                {
                                    "role": "user",
                                    "type": "message",
                                    "content": "I have declined to run this code.",
                                }
                            )
                            break

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

                if not interpreter.plain_text_display:
                    history_renderer.process_chunk(chunk)

                if (
                    chunk["type"] == "message"
                    and chunk.get("end")
                    and interpreter.os
                ):
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


            if not interpreter.plain_text_display:
                history_renderer.finalize()

            if not interactive:
                # Don't loop
                break

        except KeyboardInterrupt:
            # Exit gracefully
            if not interpreter.plain_text_display:
                history_renderer.finalize()

            if interactive:
                # (this cancels LLM, returns to the interactive "> " input)
                continue
            else:
                break
        except:
            if not interpreter.plain_text_display:
                history_renderer.finalize()
            if interpreter.debug:
                system_info(interpreter)
            raise
