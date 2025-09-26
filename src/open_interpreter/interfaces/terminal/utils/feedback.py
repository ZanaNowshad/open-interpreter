from __future__ import annotations

import sys
import time
from typing import Dict


class FeedbackEmitter:
    """Emit optional audio/haptic feedback keyed to event severity."""

    _AUDIO_PATTERNS: Dict[str, int] = {
        "info": 1,
        "success": 2,
        "warning": 3,
        "error": 4,
    }

    def __init__(self, interpreter):
        self._interpreter = interpreter
        self._audio_enabled = bool(getattr(interpreter, "audio_notifications", False))
        self._haptics_enabled = bool(
            getattr(interpreter, "haptic_notifications", False)
        )

    def emit(self, severity: str) -> None:
        severity = severity.lower()
        if self._audio_enabled:
            self._emit_audio(severity)
        if self._haptics_enabled:
            self._emit_haptics(severity)

    def _emit_audio(self, severity: str) -> None:
        count = self._AUDIO_PATTERNS.get(severity, 1)
        for _ in range(count):
            # Terminal bell as a cross-platform, dependency-free cue
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.05)

    def _emit_haptics(self, severity: str) -> None:
        computer = getattr(self._interpreter, "computer", None)
        os_driver = getattr(computer, "os", None) if computer else None
        haptic_method = getattr(os_driver, "haptic_feedback", None)
        if callable(haptic_method):
            pattern = severity if severity in self._AUDIO_PATTERNS else "info"
            try:
                haptic_method(pattern)
            except Exception:
                # Silently ignore failures; feedback is optional.
                pass
