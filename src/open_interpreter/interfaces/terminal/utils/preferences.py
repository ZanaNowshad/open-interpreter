"""Lightweight helpers for persisting terminal interface preferences."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .local_storage_path import get_storage_path

PREFERENCES_FILENAME = "preferences.json"


def _preferences_path() -> str:
    return os.path.join(get_storage_path(), PREFERENCES_FILENAME)


def load_preferences() -> Dict[str, Any]:
    """Load persisted preferences from disk."""

    path = _preferences_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return {}


def save_preferences(data: Dict[str, Any]) -> None:
    """Persist the entire preferences mapping to disk."""

    path = _preferences_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def update_preferences(section: str, values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge a section into the stored preferences file."""

    preferences = load_preferences()
    if values is None:
        preferences.pop(section, None)
    else:
        preferences[section] = values
    save_preferences(preferences)
    return preferences


__all__ = ["load_preferences", "save_preferences", "update_preferences", "PREFERENCES_FILENAME"]
