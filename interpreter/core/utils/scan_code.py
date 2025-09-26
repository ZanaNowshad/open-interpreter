import os
import subprocess
from typing import Any, Dict

from .temporary_file import cleanup_temporary_file, create_temporary_file

try:
    from yaspin import yaspin
except ImportError:  # pragma: no cover - optional dependency
    yaspin = None  # type: ignore[assignment]


def scan_code(code, language, interpreter) -> Dict[str, Any]:
    """
    Scan code with semgrep and return a structured result.
    """

    language_class = interpreter.computer.terminal.get_language(language)
    temp_file = create_temporary_file(
        code, language_class.file_extension, verbose=interpreter.verbose
    )
    temp_path = os.path.dirname(temp_file)
    file_name = os.path.basename(temp_file)

    result: Dict[str, Any] = {
        "status": "skipped",
        "summary": "",
        "return_code": None,
        "output": "",
    }

    if interpreter.verbose:
        print(f"Scanning {language} code in {file_name}")
        print("---")

    spinner = None
    try:
        if yaspin:
            spinner = yaspin(text="  Scanning code...").green.right.binary
            spinner.start()

        scan = subprocess.run(
            f"cd {temp_path} && semgrep scan --config auto --quiet --error {file_name}",
            shell=True,
            capture_output=True,
            text=True,
        )

        result["return_code"] = scan.returncode
        output_segments = [segment.strip() for segment in [scan.stdout, scan.stderr] if segment]
        output_text = "\n".join(segment for segment in output_segments if segment)
        result["output"] = output_text

        if spinner:
            if scan.returncode == 0:
                spinner.ok("✔")
            else:
                spinner.fail("✖")

        if output_text:
            print(output_text)
            print("")

        language_name = language_class.name
        if scan.returncode == 0:
            result["status"] = "passed"
            summary = (
                f"{'Code Scanner: ' if interpreter.safe_mode == 'auto' else ''}"
                f"No issues were found in this {language_name} code."
            )
            result["summary"] = summary
            print(f"  {summary}")
            print("")
        else:
            result["status"] = "issues"
            result["summary"] = (
                output_text or f"Potential issues detected in {language_name} code."
            )

    except Exception as exc:  # pragma: no cover - defensive fallback
        if spinner:
            spinner.fail("✖")
        print(f"Could not scan {language} code. Have you installed 'semgrep'?")
        print(exc)
        print("")  # <- Aesthetic choice
        result["status"] = "error"
        result["summary"] = str(exc)
    finally:
        if spinner:
            spinner.stop()
        cleanup_temporary_file(temp_file, verbose=interpreter.verbose)

    return result
