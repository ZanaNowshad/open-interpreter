"""Message rendering utilities for the terminal interface."""

from __future__ import annotations

import re
from typing import Any, Iterable


def render_message(interpreter: Any, message: str) -> str:
    """Render a dynamic message template using the interpreter's computer.

    The legacy implementation allowed templates to embed executable blocks
    wrapped in ``{{ ... }}``. Each block is executed via the computer service
    and replaced with its textual output. This helper mirrors that behaviour so
    that existing prompts continue to function while living inside the modular
    interface layer.
    """

    previous_save_skills_setting = interpreter.computer.save_skills
    interpreter.computer.save_skills = False

    parts = re.split(r"({{.*?}})", message, flags=re.DOTALL)

    for index, part in enumerate(parts):
        if part.startswith("{{") and part.endswith("}}"):
            output = interpreter.computer.run(
                "python",
                part[2:-2].strip(),
                display=interpreter.verbose,
            )

            outputs: Iterable[str] = (
                line["content"]
                for line in output
                if line.get("format") == "output"
                and "IGNORE_ALL_ABOVE_THIS_LINE" not in line["content"]
            )
            parts[index] = "\n".join(outputs)

    rendered_message = "".join(parts).strip()

    if interpreter.debug == True and False:  # Maintains legacy switch placement
        print("\n\n\nSYSTEM MESSAGE\n\n\n")
        print(rendered_message)
        print("\n\n\n")

    interpreter.computer.save_skills = previous_save_skills_setting

    return rendered_message


__all__ = ["render_message"]
