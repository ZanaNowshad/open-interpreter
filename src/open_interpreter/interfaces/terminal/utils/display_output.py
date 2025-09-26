import base64
import os
import platform
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

from .in_jupyter_notebook import in_jupyter_notebook
from .artifact_manager import Artifact, ArtifactManager

try:
    from rich.console import Console
    from rich.image import Image as RichImage
    from rich.panel import Panel
    from rich.syntax import Syntax
except Exception:  # pragma: no cover - rich is an optional dependency in some envs
    Console = None
    RichImage = None
    Panel = None
    Syntax = None


CONSOLE = Console() if Console else None


ARTIFACT_ICONS = {
    "image": "🖼️",
    "html": "🌐",
    "javascript": "🧩",
}


def display_output(output, artifact_manager: Optional[ArtifactManager] = None):
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
        return display_output_cli(output, artifact_manager=artifact_manager)

    # Return a message for the LLM.
    return "Displayed on the user's machine."


def display_output_cli(
    output, artifact_manager: Optional[ArtifactManager] = None
) -> str:
    output_type = output.get("type")
    format_hint = output.get("format")

    if output_type == "console":
        print(output["content"])
        return output["content"]

    if output_type == "image":
        return _handle_image_output(output, artifact_manager)

    if format_hint == "html":
        return _handle_textual_artifact(
            output,
            artifact_manager,
            kind="html",
            extension=".html",
            language="html",
        )

    if format_hint == "javascript":
        return _handle_textual_artifact(
            output,
            artifact_manager,
            kind="javascript",
            extension=".js",
            language="javascript",
        )

    if format_hint == "path":
        return _handle_path_artifact(output, artifact_manager)

    return "Displayed on the user's machine."


def _handle_path_artifact(output, artifact_manager: Optional[ArtifactManager]) -> str:
    path = output.get("content")
    if not path:
        return "Received artifact with no path."

    description = os.path.basename(path) or "artifact"
    size = None
    try:
        size = os.path.getsize(path)
    except OSError:
        pass

    preview_label = _render_image_preview(path=path)

    if artifact_manager:
        artifact = artifact_manager.register(
            kind=output.get("type", "artifact"),
            description=description,
            ensure_path=lambda: path,
            is_temporary=False,
            size_bytes=size,
            preview_label=_describe_preview(preview_label),
        )
        return _format_artifact_transcript(artifact)

    open_file(path)
    return f"Opened artifact at {path}."


def _handle_image_output(output, artifact_manager: Optional[ArtifactManager]) -> str:
    format_hint = output.get("format", "")
    extension = "png"
    if "." in format_hint:
        extension = format_hint.split(".")[-1]

    temp_path: Optional[str] = None
    image_bytes: Optional[bytes] = None
    is_temporary = True

    if "base64" in format_hint:
        raw_content = output.get("content", "")
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode()
        try:
            image_bytes = base64.b64decode(raw_content)
        except Exception:
            image_bytes = b""

        def ensure_path() -> str:
            nonlocal temp_path
            if temp_path and os.path.exists(temp_path):
                return temp_path
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
                tmp_file.write(image_bytes)
                temp_path = tmp_file.name
            return temp_path

    elif format_hint == "path":
        path = output.get("content")

        def ensure_path(path=path) -> str:
            return path

        is_temporary = False
        temp_path = path
    else:
        raw_content = output.get("content", b"")
        if isinstance(raw_content, bytes):
            image_bytes = bytes(raw_content)
        elif isinstance(raw_content, bytearray):
            image_bytes = bytes(raw_content)
        else:
            image_bytes = str(raw_content).encode("utf-8")

        def ensure_path() -> str:
            nonlocal temp_path
            if temp_path and os.path.exists(temp_path):
                return temp_path
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
                tmp_file.write(image_bytes)
                temp_path = tmp_file.name
            return temp_path

    preview_source = None
    if image_bytes is not None:
        preview_source = _render_image_preview(image_bytes=image_bytes)
    else:
        preview_source = _render_image_preview(path=temp_path or ensure_path())

    if not preview_source:
        preview_source = _render_sixel_preview(ensure_path())

    size = None
    if image_bytes is not None:
        size = len(image_bytes)
    else:
        try:
            size = os.path.getsize(ensure_path())
        except OSError:
            pass

    if artifact_manager:
        artifact = artifact_manager.register(
            kind="image",
            description=f"{extension.upper()} image",
            ensure_path=ensure_path,
            is_temporary=is_temporary,
            size_bytes=size,
            preview_label=_describe_preview(preview_source),
        )
        return _format_artifact_transcript(artifact)

    path = ensure_path()
    open_file(path)
    return f"Opened image at {path}."


def _handle_textual_artifact(
    output,
    artifact_manager: Optional[ArtifactManager],
    *,
    kind: str,
    extension: str,
    language: str,
) -> str:
    content = output.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    text = content or ""
    truncated, was_truncated = _truncate_text(text)
    preview_source = _render_text_preview(truncated, language)

    def ensure_path() -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, mode="w") as tmp_file:
            tmp_file.write(content)
            return tmp_file.name

    preview_label = _describe_preview(preview_source, was_truncated)
    size = len(content.encode("utf-8")) if isinstance(content, str) else None

    if artifact_manager:
        artifact = artifact_manager.register(
            kind=kind,
            description=f"{kind.upper()} artifact",
            ensure_path=ensure_path,
            is_temporary=True,
            size_bytes=size,
            preview_label=preview_label,
        )
        return _format_artifact_transcript(artifact)

    path = ensure_path()
    open_file(path)
    return f"Opened {kind} artifact at {path}."


def _render_image_preview(
    image_bytes: Optional[bytes] = None, *, path: Optional[str] = None
) -> Optional[str]:
    if CONSOLE and RichImage:
        try:
            if image_bytes is not None:
                image = RichImage.from_buffer(image_bytes)
            elif path:
                image = RichImage.from_path(path)
            else:
                return None
            CONSOLE.print(image)
            return "rich"
        except Exception:
            pass
    return None


def _render_sixel_preview(path: str) -> Optional[str]:
    if not path:
        return None
    sixel_cmd = shutil.which("img2sixel")
    if not sixel_cmd:
        return None
    try:
        subprocess.run([sixel_cmd, path], check=True)
        return "sixel"
    except Exception:
        return None


def _render_text_preview(text: str, language: str) -> Optional[str]:
    if CONSOLE and Syntax:
        try:
            syntax = Syntax(text, language, theme="monokai", word_wrap=True)
            CONSOLE.print(syntax)
            return "rich"
        except Exception:
            pass
    if CONSOLE and Panel:
        try:
            CONSOLE.print(Panel(text, title=language.upper()))
            return "panel"
        except Exception:
            pass
    print(text)
    return "text"


def _truncate_text(text: str, limit: int = 2000) -> Tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    truncated = text[: max(0, limit - 1)].rstrip()
    if not truncated.endswith("…"):
        truncated += "\n…"
    return truncated, True


def _describe_preview(source: Optional[str], truncated: bool = False) -> Optional[str]:
    if not source and not truncated:
        return None

    label_map = {
        "rich": "inline preview via Rich",
        "panel": "inline preview",
        "text": "inline preview",
        "sixel": "inline preview via sixel",
    }

    label = label_map.get(source)

    if not label and truncated:
        label = "truncated preview"

    if label and truncated:
        label = f"{label} (truncated)"

    return label


def _format_artifact_transcript(artifact: Artifact) -> str:
    icon = ARTIFACT_ICONS.get(artifact.kind, "📦")
    size_suffix = ""
    if artifact.size_bytes is not None:
        size_suffix = f" ({_format_size(artifact.size_bytes)})"

    preview_line = artifact.preview_label or "Preview unavailable"

    lines = [
        f"{icon} Artifact {artifact.id}: {artifact.description}{size_suffix}",
        f"  Preview: {preview_line}",
        f"  Quick actions: :open {artifact.id} | :save {artifact.id} <path> | :discard {artifact.id}",
    ]

    return "\n".join(lines)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


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
