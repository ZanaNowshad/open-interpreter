import atexit
import base64
import os
import platform
import subprocess
import tempfile

from typing import List

from .in_jupyter_notebook import in_jupyter_notebook


_TEMP_ASSETS: List[str] = []


def _register_temp_asset(path: str) -> None:
    _TEMP_ASSETS.append(path)


@atexit.register
def _cleanup_temp_assets() -> None:
    for path in list(_TEMP_ASSETS):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _compress_text_asset(content: str) -> str:
    # Collapse trailing whitespace and duplicate blank lines to reduce file size
    lines = [line.rstrip() for line in content.splitlines()]
    compressed_lines = []
    previous_blank = False

    for line in lines:
        if line:
            compressed_lines.append(line)
            previous_blank = False
        else:
            if not previous_blank:
                compressed_lines.append(line)
            previous_blank = True

    return "\n".join(compressed_lines).strip()


def _optimize_image_file(path: str) -> None:
    try:
        from PIL import Image
    except ImportError:
        return

    try:
        with Image.open(path) as img:
            save_kwargs = {"optimize": True}
            if img.format == "JPEG":
                # Maintain a balance between quality and size
                save_kwargs.setdefault("quality", 85)
            img.save(path, **save_kwargs)
    except Exception:
        # Best effort compression only
        pass


def display_output(output):
    if in_jupyter_notebook():
        from IPython.display import HTML, Image, Javascript, display

        if output["type"] == "console":
            print(output["content"])
        elif output["type"] == "image":
            if "base64" in output["format"]:
                # Decode the base64 image data
                image_data = base64.b64decode(output["content"])
                display(Image(image_data))
            elif output["format"] == "path":
                # Display the image file on the system
                display(Image(filename=output["content"]))
        elif "format" in output and output["format"] == "html":
            display(HTML(output["content"]))
        elif "format" in output and output["format"] == "javascript":
            display(Javascript(output["content"]))
    else:
        display_output_cli(output)

    # Return a message for the LLM.
    # We should make this specific to what happened in the future,
    # like saying WHAT temporary file we made, etc. Keep the LLM informed.
    return "Displayed on the user's machine."


def display_output_cli(output):
    if output["type"] == "console":
        print(output["content"])
    elif output["type"] == "image":
        if "base64" in output["format"]:
            if "." in output["format"]:
                extension = output["format"].split(".")[-1]
            else:
                extension = "png"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix="." + extension
            ) as tmp_file:
                image_data = base64.b64decode(output["content"])
                tmp_file.write(image_data)

            _optimize_image_file(tmp_file.name)
            _register_temp_asset(tmp_file.name)

                # # Display in Terminal (DISABLED, i couldn't get it to work)
                # from term_image.image import from_file
                # image = from_file(tmp_file.name)
                # image.draw()

            open_file(tmp_file.name)
        elif output["format"] == "path":
            open_file(output["content"])
    elif "format" in output and output["format"] == "html":
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w", encoding="utf-8"
        ) as tmp_file:
            html = _compress_text_asset(output["content"])
            tmp_file.write(html)

        _register_temp_asset(tmp_file.name)
        open_file(tmp_file.name)
    elif "format" in output and output["format"] == "javascript":
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".js", mode="w", encoding="utf-8"
        ) as tmp_file:
            script = _compress_text_asset(output["content"])
            tmp_file.write(script)

        _register_temp_asset(tmp_file.name)
        open_file(tmp_file.name)


def open_file(file_path):
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path])
        else:  # Linux and other Unix-like
            subprocess.run(["xdg-open", file_path])
    except Exception as e:
        print(f"Error opening file: {e}")
