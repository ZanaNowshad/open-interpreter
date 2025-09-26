"""Cross-platform notification helper for the terminal interface."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationResult:
    """Details about a delivered notification."""

    success: bool
    channel: str | None = None


class Notifier:
    """Dispatch small desktop notifications where possible."""

    def __init__(self, default_title: str = "Open Interpreter") -> None:
        self.default_title = default_title

    # ------------------------------------------------------------------
    # Public API

    def notify(self, message: str, title: Optional[str] = None) -> NotificationResult:
        """Attempt to show an OS level notification."""

        if not message:
            return NotificationResult(False)

        heading = self._sanitize(title or self.default_title)
        body = self._sanitize(message)
        system = platform.system().lower()

        if "darwin" in system:
            return NotificationResult(self._notify_macos(heading, body), "macos")
        if "windows" in system:
            return NotificationResult(self._notify_windows(heading, body), "windows")
        return NotificationResult(self._notify_unix(heading, body), "unix")

    # ------------------------------------------------------------------
    # Platform handlers

    def _notify_macos(self, title: str, message: str) -> bool:
        script = f'display notification "{message}" with title "{title}"'
        try:
            subprocess.run(["osascript", "-e", script], check=False)
            return True
        except Exception:
            return False

    def _notify_windows(self, title: str, message: str) -> bool:
        # Try Toastify/Win10 toast notifications first
        for module_name, attribute in (("toastify", "Toast"), ("win10toast", "ToastNotifier")):
            try:
                module = __import__(module_name, fromlist=[attribute])
                notifier_cls = getattr(module, attribute)
                notifier = notifier_cls()
                if module_name == "toastify":
                    notifier.show_toast(title=title, msg=message, duration=5)
                else:
                    notifier.show_toast(title, message, duration=5, threaded=True)
                return True
            except Exception:
                continue

        # Fallback to plyer if available
        try:
            from plyer import notification

            notification.notify(title=title, message=message)
            return True
        except Exception:
            pass

        # As a last resort, try PowerShell via System.Windows.Forms
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            return False

        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "Add-Type -AssemblyName System.Drawing;"
            "$notify = New-Object System.Windows.Forms.NotifyIcon;"
            "$notify.Icon = [System.Drawing.SystemIcons]::Information;"
            f"$notify.BalloonTipTitle = '{title}';"
            f"$notify.BalloonTipText = '{message}';"
            "$notify.Visible = $true;"
            "$notify.ShowBalloonTip(3000);"
            "Start-Sleep -Seconds 5;"
            "$notify.Dispose();"
        )

        try:
            subprocess.Popen([powershell, "-NoLogo", "-NoProfile", "-Command", script])
            return True
        except Exception:
            return False

    def _notify_unix(self, title: str, message: str) -> bool:
        # Prefer plyer on Linux/Unix
        try:
            from plyer import notification

            notification.notify(title=title, message=message)
            return True
        except Exception:
            pass

        notify_send = shutil.which("notify-send")
        if notify_send:
            try:
                subprocess.run([notify_send, title, message], check=False)
                return True
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Helpers

    def _sanitize(self, value: str) -> str:
        value = value.replace("\n", " ").strip()
        value = value.replace("\"", "'")
        value = value.replace("'", "’")
        if len(value) > 200:
            value = value[:197] + "..."
        return value


__all__ = ["Notifier", "NotificationResult"]
