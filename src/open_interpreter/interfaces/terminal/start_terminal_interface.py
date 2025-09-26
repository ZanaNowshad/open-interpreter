import argparse
import logging
import os
import sys
import time
from collections import defaultdict

from importlib.metadata import version

from open_interpreter.interfaces.terminal.contributing_conversations import (
    contribute_conversation_launch_logic,
    contribute_conversations,
)

from .conversation_navigator import conversation_navigator
from .profiles.profiles import (
    migrate_user_app_directory,
    open_storage_dir,
    profile,
    reset_profile,
)
from .utils.check_for_update import check_for_update
from .utils.cli_overrides import capture_cli_overrides
from .utils.session_header import display_session_header
from .validate_llm_settings import validate_llm_settings

from rich.console import Console
from rich.table import Table
from rich.text import Text


logger = logging.getLogger(__name__)


HELP_CATEGORY_STYLES = {
    "Profiles & Sessions": "bold magenta",
    "Model Configuration": "bold cyan",
    "Execution & Safety": "bold green",
    "Display & Interaction": "bold yellow",
    "Connectivity & API": "bold blue",
    "Accessibility": "bold white",
    "Diagnostics & Debugging": "bold red",
    "Community": "bold bright_magenta",
}

HELP_CATEGORY_ORDER = [
    "Profiles & Sessions",
    "Model Configuration",
    "Execution & Safety",
    "Display & Interaction",
    "Connectivity & API",
    "Accessibility",
    "Diagnostics & Debugging",
    "Community",
]


def start_terminal_interface(interpreter):
    """
    Meant to be used from the command line. Parses arguments, starts OI's terminal interface.
    """

    # Instead use an async interpreter, which has a server. Set settings on that
    if "--server" in sys.argv:
        from open_interpreter.runtime import AsyncInterpreter

        interpreter = AsyncInterpreter()

    arguments = [
        {
            "name": "profile",
            "nickname": "p",
            "help_text": "name of profile. run `--profiles` to open profile directory",
            "type": str,
            "default": "default.yaml",
            "category": "Profiles & Sessions",
            "example": "interpreter --profile research.yaml",
        },
        {
            "name": "custom_instructions",
            "nickname": "ci",
            "help_text": "custom instructions for the language model. will be appended to the system_message",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "custom_instructions"},
            "category": "Model Configuration",
            "example": "interpreter --custom_instructions \"Prefer python\"",
        },
        {
            "name": "system_message",
            "nickname": "sm",
            "help_text": "(we don't recommend changing this) base prompt for the language model",
            "type": str,
            "attribute": {"object": interpreter, "attr_name": "system_message"},
            "category": "Model Configuration",
            "example": "interpreter --system_message path/to/prompt.txt",
        },
        {
            "name": "auto_run",
            "nickname": "y",
            "help_text": "automatically run generated code",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "auto_run"},
            "category": "Execution & Safety",
            "example": "interpreter --auto_run",
        },
        {
            "name": "no_highlight_active_line",
            "nickname": "nhl",
            "help_text": "turn off active line highlighting in code blocks",
            "type": bool,
            "action": "store_true",
            "default": False,
            "category": "Display & Interaction",
            "example": "interpreter --no_highlight_active_line",
        },
        {
            "name": "verbose",
            "nickname": "v",
            "help_text": "print detailed logs",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "verbose"},
            "category": "Diagnostics & Debugging",
            "example": "interpreter --verbose",
        },
        {
            "name": "model",
            "nickname": "m",
            "help_text": "language model to use",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "model"},
            "category": "Model Configuration",
            "example": "interpreter --model openai/gpt-4o-mini",
        },
        {
            "name": "temperature",
            "nickname": "t",
            "help_text": "optional temperature setting for the language model",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "temperature"},
            "category": "Model Configuration",
            "example": "interpreter --temperature 0.2",
        },
        {
            "name": "llm_supports_vision",
            "nickname": "lsv",
            "help_text": "inform OI that your model supports vision, and can receive vision inputs",
            "type": bool,
            "action": argparse.BooleanOptionalAction,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_vision"},
            "category": "Model Configuration",
            "example": "interpreter --llm_supports_vision",
        },
        {
            "name": "llm_supports_functions",
            "nickname": "lsf",
            "help_text": "inform OI that your model supports OpenAI-style functions, and can make function calls",
            "type": bool,
            "action": argparse.BooleanOptionalAction,
            "attribute": {"object": interpreter.llm, "attr_name": "supports_functions"},
            "category": "Model Configuration",
            "example": "interpreter --no-llm_supports_functions",
        },
        {
            "name": "context_window",
            "nickname": "cw",
            "help_text": "optional context window size for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "context_window"},
            "category": "Model Configuration",
            "example": "interpreter --context_window 32768",
        },
        {
            "name": "max_tokens",
            "nickname": "x",
            "help_text": "optional maximum number of tokens for the language model",
            "type": int,
            "attribute": {"object": interpreter.llm, "attr_name": "max_tokens"},
            "category": "Model Configuration",
            "example": "interpreter --max_tokens 2048",
        },
        {
            "name": "max_budget",
            "nickname": "b",
            "help_text": "optionally set the max budget (in USD) for your llm calls",
            "type": float,
            "attribute": {"object": interpreter.llm, "attr_name": "max_budget"},
            "category": "Model Configuration",
            "example": "interpreter --max_budget 1.25",
        },
        {
            "name": "api_base",
            "nickname": "ab",
            "help_text": "optionally set the API base URL for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_base"},
            "category": "Connectivity & API",
            "example": "interpreter --api_base https://api.example.com",
        },
        {
            "name": "api_key",
            "nickname": "ak",
            "help_text": "optionally set the API key for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_key"},
            "category": "Connectivity & API",
            "example": "interpreter --api_key sk-...",
        },
        {
            "name": "api_version",
            "nickname": "av",
            "help_text": "optionally set the API version for your llm calls (this will override environment variables)",
            "type": str,
            "attribute": {"object": interpreter.llm, "attr_name": "api_version"},
            "category": "Connectivity & API",
            "example": "interpreter --api_version 2024-05-01",
        },
        {
            "name": "max_output",
            "nickname": "xo",
            "help_text": "optional maximum number of characters for code outputs",
            "type": int,
            "attribute": {"object": interpreter, "attr_name": "max_output"},
            "category": "Execution & Safety",
            "example": "interpreter --max_output 1200",
        },
        {
            "name": "loop",
            "help_text": "runs OI in a loop, requiring it to admit to completing/failing task",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "loop"},
            "category": "Execution & Safety",
            "example": "interpreter --loop",
        },
        {
            "name": "disable_telemetry",
            "nickname": "dt",
            "help_text": "disables sending of basic anonymous usage stats",
            "type": bool,
            "default": False,
            "attribute": {"object": interpreter, "attr_name": "disable_telemetry"},
            "category": "Diagnostics & Debugging",
            "example": "interpreter --disable_telemetry",
        },
        {
            "name": "offline",
            "nickname": "o",
            "help_text": "turns off all online features (except the language model, if it's hosted)",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "offline"},
            "category": "Connectivity & API",
            "example": "interpreter --offline",
        },
        {
            "name": "speak_messages",
            "nickname": "sp",
            "help_text": "(Mac only, experimental) use the applescript `say` command to read messages aloud",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "speak_messages"},
            "category": "Accessibility",
            "example": "interpreter --speak_messages",
        },
        {
            "name": "safe_mode",
            "nickname": "safe",
            "help_text": "optionally enable safety mechanisms like code scanning; valid options are off, ask, and auto",
            "type": str,
            "choices": ["off", "ask", "auto"],
            "default": "off",
            "attribute": {"object": interpreter, "attr_name": "safe_mode"},
            "category": "Execution & Safety",
            "example": "interpreter --safe_mode ask",
        },
        {
            "name": "debug",
            "nickname": "debug",
            "help_text": "debug mode for open interpreter developers",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "debug"},
            "category": "Diagnostics & Debugging",
            "example": "interpreter --debug",
        },
        {
            "name": "fast",
            "nickname": "f",
            "help_text": "runs `interpreter --model gpt-4o-mini` and asks OI to be extremely concise (shortcut for `interpreter --profile fast`)",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --fast",
        },
        {
            "name": "multi_line",
            "nickname": "ml",
            "help_text": "enable multi-line inputs starting and ending with ```",
            "type": bool,
            "attribute": {"object": interpreter, "attr_name": "multi_line"},
            "category": "Display & Interaction",
            "example": "interpreter --multi_line",
        },
        {
            "name": "local",
            "nickname": "l",
            "help_text": "setup a local model (shortcut for `interpreter --profile local`)",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --local",
        },
        {
            "name": "codestral",
            "help_text": "shortcut for `interpreter --profile codestral`",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --codestral",
        },
        {
            "name": "assistant",
            "help_text": "shortcut for `interpreter --profile assistant.py`",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --assistant",
        },
        {
            "name": "llama3",
            "help_text": "shortcut for `interpreter --profile llama3`",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --llama3",
        },
        {
            "name": "groq",
            "help_text": "shortcut for `interpreter --profile groq`",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --groq",
        },
        {
            "name": "vision",
            "nickname": "vi",
            "help_text": "experimentally use vision for supported languages (shortcut for `interpreter --profile vision`)",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --vision",
        },
        {
            "name": "os",
            "nickname": "os",
            "help_text": "experimentally let Open Interpreter control your mouse and keyboard (shortcut for `interpreter --profile os`)",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --os",
        },
        {
            "name": "reset_profile",
            "help_text": "reset a profile file. run `--reset_profile` without an argument to reset all default profiles",
            "type": str,
            "default": "NOT_PROVIDED",
            "nargs": "?",
            "category": "Profiles & Sessions",
            "example": "interpreter --reset_profile default.yaml",
        },
        {
            "name": "reset_profile_force",
            "help_text": "reset profiles without prompts (use with --reset_profile)",
            "type": bool,
            "default": False,
            "category": "Profiles & Sessions",
            "example": "interpreter --reset_profile --reset_profile_force",
        },
        {
            "name": "migrate_profiles",
            "help_text": "migrate stored profiles to the latest format without prompts",
            "type": bool,
            "default": False,
            "category": "Profiles & Sessions",
            "example": "interpreter --migrate_profiles",
        },
        {
            "name": "profiles",
            "help_text": "opens profiles directory",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --profiles",
        },
        {
            "name": "local_models",
            "help_text": "opens local models directory",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --local_models",
        },
        {
            "name": "conversations",
            "help_text": "list conversations to resume",
            "type": bool,
            "category": "Profiles & Sessions",
            "example": "interpreter --conversations",
        },
        {
            "name": "server",
            "help_text": "start open interpreter as a server",
            "type": bool,
            "category": "Connectivity & API",
            "example": "interpreter --server",
        },
        {
            "name": "version",
            "help_text": "get Open Interpreter's version number",
            "type": bool,
            "category": "Diagnostics & Debugging",
            "example": "interpreter --version",
        },
        {
            "name": "contribute_conversation",
            "help_text": "let Open Interpreter use the current conversation to train an Open-Source LLM",
            "type": bool,
            "attribute": {
                "object": interpreter,
                "attr_name": "contribute_conversation",
            },
            "category": "Community",
            "example": "interpreter --contribute_conversation",
        },
        {
            "name": "plain",
            "nickname": "pl",
            "help_text": "set output to plain text",
            "type": bool,
            "attribute": {
                "object": interpreter,
                "attr_name": "plain_text_display",
            },
            "category": "Display & Interaction",
            "example": "interpreter --plain",
        },
        {
            "name": "stdin",
            "nickname": "s",
            "help_text": "Run OI in stdin mode",
            "type": bool,
            "category": "Display & Interaction",
            "example": "echo 'hello' | interpreter --stdin",
        },
    ]

    if "--stdin" in sys.argv and "--plain" not in sys.argv:
        sys.argv += ["--plain"]

    # i shortcut
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        message = " ".join(sys.argv[1:])
        interpreter.messages.append(
            {"role": "user", "type": "message", "content": "I " + message}
        )
        sys.argv = sys.argv[:1]

        interpreter.custom_instructions = "UPDATED INSTRUCTIONS: You are in ULTRA FAST, ULTRA CERTAIN mode. Do not ask the user any questions or run code to gathet information. Go as quickly as you can. Run code quickly. Do not plan out loud, simply start doing the best thing. The user expects speed. Trust that the user knows best. Just interpret their ambiguous command as quickly and certainly as possible and try to fulfill it IN ONE COMMAND, assuming they have the right information. If they tell you do to something, just do it quickly in one command, DO NOT try to get more information (for example by running `cat` to get a file's infomration— this is probably unecessary!). DIRECTLY DO THINGS AS FAST AS POSSIBLE."

        files_in_directory = os.listdir()[:100]
        interpreter.custom_instructions += (
            "\nThe files in CWD, which THE USER MAY BE REFERRING TO, are: "
            + ", ".join(files_in_directory)
        )

        # interpreter.debug = True

    # Check for deprecated flags before parsing arguments
    deprecated_flags = {
        "--debug_mode": "--verbose",
    }

    for old_flag, new_flag in deprecated_flags.items():
        if old_flag in sys.argv:
            print(f"\n`{old_flag}` has been renamed to `{new_flag}`.\n")
            time.sleep(1.5)
            sys.argv.remove(old_flag)
            sys.argv.append(new_flag)

    class CustomHelpParser(argparse.ArgumentParser):
        def print_help(self, *args, **kwargs):
            console = Console()
            console.print(Text("Open Interpreter", style="bold cyan"))
            console.print(Text(self.format_usage().strip(), style="dim"))
            console.print("")

            grouped_arguments = defaultdict(list)
            for spec in arguments:
                grouped_arguments[spec.get("category", "Other")].append(spec)

            for category in HELP_CATEGORY_ORDER:
                specs = grouped_arguments.get(category)
                if not specs:
                    continue

                console.print(Text(category, style=HELP_CATEGORY_STYLES.get(category, "bold")))
                table = Table(show_header=False, box=None, padding=(0, 1))

                for spec in specs:
                    flags = []
                    nickname = spec.get("nickname")
                    if nickname:
                        flags.append(f"-{nickname}")
                    flags.append(f"--{spec['name']}")

                    help_text = spec["help_text"]
                    example = spec.get("example")
                    if example:
                        help_text = f"{help_text} [dim](e.g. {example})[/dim]"

                    table.add_row(f"[cyan]{', '.join(flags)}[/cyan]", help_text)

                console.print(table)
                console.print("")

            console.print(
                Text(
                    "Tip: type '::' during a session to open the command palette.",
                    style="dim",
                )
            )
            console.print(Text("Use \"\"\" to write multi-line messages.", style="dim"))
            console.print(Text("Open Interpreter, 2024", style="dim"))

    parser = CustomHelpParser(
        description="Open Interpreter", usage="%(prog)s [options]"
    )

    # Add arguments
    for arg in arguments:
        default = arg.get("default")
        action = arg.get("action", "store_true")
        nickname = arg.get("nickname")

        name_or_flags = [f'--{arg["name"]}']
        if nickname:
            name_or_flags.append(f"-{nickname}")

        # Construct argument name flags
        flags = (
            [f"-{nickname}", f'--{arg["name"]}'] if nickname else [f'--{arg["name"]}']
        )

        if arg["type"] == bool:
            parser.add_argument(
                *flags,
                dest=arg["name"],
                help=arg["help_text"],
                action=action,
                default=default,
            )
        else:
            choices = arg.get("choices")
            parser.add_argument(
                *flags,
                dest=arg["name"],
                help=arg["help_text"],
                type=arg["type"],
                choices=choices,
                default=default,
                nargs=arg.get("nargs"),
            )

    args, unknown_args = parser.parse_known_args()
    cli_overrides, attribute_map = capture_cli_overrides(interpreter, args, arguments)

    # handle unknown arguments
    if unknown_args:
        print(f"\nUnrecognized argument(s): {unknown_args}")
        parser.print_usage()
        print(
            "For detailed documentation of supported arguments, please visit: https://docs.openinterpreter.com/settings/all-settings"
        )
        sys.exit(1)

    if args.reset_profile_force and args.reset_profile == "NOT_PROVIDED":
        print("`--reset_profile_force` must be used together with `--reset_profile`.")
        sys.exit(1)

    if args.migrate_profiles:
        summary = migrate_user_app_directory(log=logger.info)
        _print_operations_summary("Profile migration", summary)
        return

    if args.profiles:
        open_storage_dir("profiles")
        return

    if args.local_models:
        open_storage_dir("models")
        return

    if args.reset_profile != "NOT_PROVIDED":
        summary = reset_profile(
            args.reset_profile,
            non_interactive=args.reset_profile_force,
            confirm=args.reset_profile_force,
            log=logger.info,
        )
        if args.reset_profile_force:
            _print_operations_summary("Profile reset", summary)
        return

    if args.version:
        oi_version = version("open-interpreter")
        update_name = "Developer Preview"  # Change this with each major update
        print(f"Open Interpreter {oi_version} {update_name}")
        return

    if args.no_highlight_active_line:
        interpreter.highlight_active_line = False

    # if safe_mode and auto_run are enabled, safe_mode disables auto_run
    if interpreter.auto_run and (
        interpreter.safe_mode == "ask" or interpreter.safe_mode == "auto"
    ):
        setattr(interpreter, "auto_run", False)

    ### Set attributes on interpreter, so that a profile script can read the arguments passed in via the CLI

    set_attributes(args, arguments)

    ### Apply profile

    # Profile shortcuts, which should probably not exist:

    if args.fast:
        args.profile = "fast.yaml"

    if args.vision:
        args.profile = "vision.yaml"

    if args.os:
        args.profile = "os.py"

    if args.local:
        args.profile = "local.py"
        if args.vision:
            # This is local vision, set up moondream!
            interpreter.computer.vision.load()
        if args.os:
            args.profile = "local-os.py"

    if args.codestral:
        args.profile = "codestral.py"
        if args.vision:
            args.profile = "codestral-vision.py"
        if args.os:
            args.profile = "codestral-os.py"

    if args.assistant:
        args.profile = "assistant.py"

    if args.llama3:
        args.profile = "llama3.py"
        if args.vision:
            args.profile = "llama3-vision.py"
        if args.os:
            args.profile = "llama3-os.py"

    if args.groq:
        args.profile = "groq.py"

    interpreter = profile(
        interpreter,
        args.profile or get_argument_dictionary(arguments, "profile")["default"],
    )

    ### Set attributes on interpreter, because the arguments passed in via the CLI should override profile

    set_attributes(args, arguments)
    interpreter.disable_telemetry = (
        os.getenv("DISABLE_TELEMETRY", "false").lower() == "true"
        or args.disable_telemetry
    )

    interpreter._cli_overrides = cli_overrides
    interpreter._cli_attribute_map = attribute_map
    interpreter._command_palette_enabled = not args.stdin

    ### Set some helpful settings we know are likely to be true

    if interpreter.llm.model == "gpt-4" or interpreter.llm.model == "openai/gpt-4":
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 6500
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = (
                False if "vision" in interpreter.llm.model else True
            )

    elif interpreter.llm.model.startswith("gpt-4") or interpreter.llm.model.startswith(
        "openai/gpt-4"
    ):
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 123000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = (
                False if "vision" in interpreter.llm.model else True
            )

    if interpreter.llm.model.startswith(
        "gpt-3.5-turbo"
    ) or interpreter.llm.model.startswith("openai/gpt-3.5-turbo"):
        if interpreter.llm.context_window is None:
            interpreter.llm.context_window = 16000
        if interpreter.llm.max_tokens is None:
            interpreter.llm.max_tokens = 4096
        if interpreter.llm.supports_functions is None:
            interpreter.llm.supports_functions = True

    if not args.stdin:
        display_session_header(interpreter)

    ### Check for update

    try:
        if not interpreter.offline and not args.stdin:
            # This message should actually be pushed into the utility
            if check_for_update():
                interpreter.display_message(
                    "> **A new version of Open Interpreter is available.**\n>Please run: `pip install --upgrade open-interpreter`\n\n---"
                )
    except:
        # Doesn't matter
        pass

    if interpreter.llm.api_base:
        if (
            not interpreter.llm.model.lower().startswith("openai/")
            and not interpreter.llm.model.lower().startswith("azure/")
            and not interpreter.llm.model.lower().startswith("ollama")
            and not interpreter.llm.model.lower().startswith("jan")
            and not interpreter.llm.model.lower().startswith("local")
        ):
            interpreter.llm.model = "openai/" + interpreter.llm.model
        elif interpreter.llm.model.lower().startswith("jan/"):
            # Strip jan/ from the model name
            interpreter.llm.model = interpreter.llm.model[4:]

    # If --conversations is used, run conversation_navigator
    if args.conversations:
        conversation_navigator(interpreter)
        return

    if interpreter.llm.model in [
        "claude-3.5",
        "claude-3-5",
        "claude-3.5-sonnet",
        "claude-3-5-sonnet",
    ]:
        interpreter.llm.model = "claude-3-5-sonnet-20240620"

    if not args.server:
        # This SHOULD RUN WHEN THE SERVER STARTS. But it can't rn because
        # if you don't have an API key, a prompt shows up, breaking the whole thing.
        validate_llm_settings(
            interpreter
        )  # This should actually just run interpreter.llm.load() once that's == to validate_llm_settings

    if args.server:
        interpreter.server.run()
        return

    interpreter.in_terminal_interface = True

    contribute_conversation_launch_logic(interpreter)

    # Standard in mode
    if args.stdin:
        stdin_input = input()
        interpreter.plain_text_display = True
        interpreter.chat(stdin_input)
    else:
        interpreter.chat()


def set_attributes(args, arguments):
    for argument_name, argument_value in vars(args).items():
        if argument_value is not None:
            if argument_dictionary := get_argument_dictionary(arguments, argument_name):
                if "attribute" in argument_dictionary:
                    attr_dict = argument_dictionary["attribute"]
                    setattr(attr_dict["object"], attr_dict["attr_name"], argument_value)

                    if args.verbose:
                        print(
                            f"Setting attribute {attr_dict['attr_name']} on {attr_dict['object'].__class__.__name__.lower()} to '{argument_value}'..."
                        )


def _print_operations_summary(title: str, operations):
    if operations is None:
        return

    if not operations:
        print(f"{title}: No changes were necessary.")
        return

    print(title)
    for line in operations:
        print(f" - {line}")


def get_argument_dictionary(arguments: list[dict], key: str) -> dict:
    if (
        len(
            argument_dictionary_list := list(
                filter(lambda x: x["name"] == key, arguments)
            )
        )
        > 0
    ):
        return argument_dictionary_list[0]
    return {}


def main():
    from open_interpreter.runtime import interpreter

    try:
        start_terminal_interface(interpreter)
    except KeyboardInterrupt:
        try:
            interpreter.computer.terminate()

            if not interpreter.offline and not interpreter.disable_telemetry:
                feedback = None
                if len(interpreter.messages) > 3:
                    feedback = (
                        input("\n\nWas Open Interpreter helpful? (y/n): ")
                        .strip()
                        .lower()
                    )
                    if feedback == "y":
                        feedback = True
                    elif feedback == "n":
                        feedback = False
                    else:
                        feedback = None
                    if feedback != None and not interpreter.contribute_conversation:
                        if interpreter.llm.model == "i":
                            contribute = "y"
                        else:
                            print(
                                "\nThanks for your feedback! Would you like to send us this chat so we can improve?\n"
                            )
                            contribute = input("(y/n): ").strip().lower()

                        if contribute == "y":
                            interpreter.contribute_conversation = True
                            interpreter.display_message(
                                "\n*Thank you for contributing!*\n"
                            )

                if (
                    interpreter.contribute_conversation or interpreter.llm.model == "i"
                ) and interpreter.messages != []:
                    conversation_id = (
                        interpreter.conversation_id
                        if hasattr(interpreter, "conversation_id")
                        else None
                    )
                    contribute_conversations(
                        [interpreter.messages], feedback, conversation_id
                    )

        except KeyboardInterrupt:
            pass
    finally:
        interpreter.computer.terminate()
