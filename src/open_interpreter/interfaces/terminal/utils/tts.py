"""Utilities for speaking assistant responses via local TTS engines."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from open_interpreter.core.runtime import TTSSettings


class TTSUnavailable(RuntimeError):
    """Raised when a requested TTS engine cannot be used."""


@dataclass
class TTSPlaybackHandle:
    process: Optional[subprocess.Popen] = None
    file_path: Optional[str] = None

    def __post_init__(self) -> None:
        if self.process and self.file_path:
            thread = threading.Thread(target=self._cleanup, daemon=True)
            thread.start()

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self._remove_file()

    def _cleanup(self) -> None:
        if self.process:
            try:
                self.process.wait()
            except Exception:
                pass
        self._remove_file()

    def _remove_file(self) -> None:
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except OSError:
                pass


_COQUI_MODELS: Dict[str, Any] = {}


def speak_text(text: str, settings: "TTSSettings") -> Optional[TTSPlaybackHandle]:
    """Generate speech for ``text`` using the configured engine."""

    if not text or not getattr(settings, "enabled", False):
        return None

    engine = (getattr(settings, "engine", None) or "coqui").lower()

    if engine == "piper":
        audio_path = _synthesise_with_piper(text, settings)
    else:
        audio_path = _synthesise_with_coqui(text, settings)

    return _play_audio(audio_path)


def _synthesise_with_coqui(text: str, settings: "TTSSettings") -> str:
    try:
        from TTS.api import TTS as CoquiTTS
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise TTSUnavailable(
            "Coqui TTS engine requires the `TTS` package. Install it with `pip install TTS`."
        ) from exc

    voice_id = getattr(settings, "voice", None) or "tts_models/en/vctk/vits"
    key = voice_id

    if key not in _COQUI_MODELS:
        kwargs: Dict[str, Any] = {"model_name": voice_id}
        if getattr(settings, "voice_path", None):
            kwargs = {"model_path": settings.voice_path}
        _COQUI_MODELS[key] = CoquiTTS(**kwargs)

    output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output.close()

    speaker = getattr(settings, "speaker", None)

    _COQUI_MODELS[key].tts_to_file(
        text=text,
        file_path=output.name,
        speaker=speaker,
    )
    return output.name


def _synthesise_with_piper(text: str, settings: "TTSSettings") -> str:
    voice_path = getattr(settings, "voice_path", None) or getattr(settings, "voice", None)
    if not voice_path:
        raise TTSUnavailable("Piper requires `voice` or `voice_path` pointing to a model file.")

    binary = getattr(settings, "binary", None) or "piper"
    if not shutil.which(binary):
        raise TTSUnavailable(f"Unable to locate Piper binary '{binary}'.")

    output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output.close()

    command = [binary, "--model", voice_path, "--output_file", output.name]

    speaker = getattr(settings, "speaker", None)
    if speaker is not None:
        command.extend(["--speaker", str(speaker)])

    extra_args = getattr(settings, "extra_args", {}) or {}
    for key, value in extra_args.items():
        command.append(str(key))
        if value is not None:
            command.append(str(value))

    try:
        subprocess.run(command, input=text.encode("utf-8"), check=True)
    except subprocess.CalledProcessError as exc:
        raise TTSUnavailable("Piper synthesis failed. Check your voice model path.") from exc

    return output.name


def _play_audio(file_path: str) -> TTSPlaybackHandle:
    system = platform.system().lower()

    if "darwin" in system:
        player = ["afplay", file_path]
    elif "windows" in system:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            raise TTSUnavailable("PowerShell is required for audio playback on Windows.")
        script = f"(New-Object Media.SoundPlayer '{file_path}').PlaySync()"
        player = [powershell, "-NoLogo", "-NoProfile", "-Command", script]
    else:
        player = None
        for candidate in (["paplay", file_path], ["aplay", file_path], ["ffplay", "-nodisp", "-autoexit", file_path]):
            if shutil.which(candidate[0]):
                player = candidate
                break
        if player is None:
            raise TTSUnavailable(
                "No audio playback utility found. Install `paplay`, `aplay`, or `ffplay` to enable TTS playback."
            )

    try:
        process = subprocess.Popen(player)
    except FileNotFoundError as exc:
        raise TTSUnavailable("Failed to start audio playback process.") from exc

    return TTSPlaybackHandle(process=process, file_path=file_path)


__all__ = ["speak_text", "TTSPlaybackHandle", "TTSUnavailable"]
