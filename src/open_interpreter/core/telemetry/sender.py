"""Telemetry helpers for anonymous usage reporting."""

from __future__ import annotations

import contextlib
import json
import os
import threading
import uuid
from importlib.metadata import PackageNotFoundError, version

import requests

__all__ = ["send_telemetry", "get_or_create_uuid", "user_id"]


def get_or_create_uuid() -> str:
    """Return the persisted anonymous telemetry identifier."""

    try:
        uuid_file_path = os.path.join(
            os.path.expanduser("~"), "\.cache", "open-interpreter", "telemetry_user_id"
        )
        os.makedirs(os.path.dirname(uuid_file_path), exist_ok=True)

        if os.path.exists(uuid_file_path):
            with open(uuid_file_path, "r", encoding="utf-8") as file:
                return file.read()

        new_uuid = str(uuid.uuid4())
        with open(uuid_file_path, "w", encoding="utf-8") as file:
            file.write(new_uuid)
        return new_uuid
    except Exception:
        return "idk"


user_id = get_or_create_uuid()


def _resolve_version() -> str:
    try:
        return version("open-interpreter")
    except PackageNotFoundError:
        return "0.0.0"


def send_telemetry(event_name: str, properties: dict | None = None) -> None:
    """Send telemetry data to PostHog."""

    payload: dict = {} if properties is None else dict(properties)
    payload["oi_version"] = _resolve_version()

    try:
        url = "https://app.posthog.com/capture"
        headers = {"Content-Type": "application/json"}
        data = {
            "api_key": "phc_6cmXy4MEbLfNGezqGjuUTY8abLu0sAwtGzZFpQW97lc",
            "event": event_name,
            "properties": payload,
            "distinct_id": user_id,
        }
        requests.post(url, headers=headers, data=json.dumps(data))
    except Exception:
        pass
