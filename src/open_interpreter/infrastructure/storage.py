"""Filesystem helpers for interpreter configuration and persistence."""

from __future__ import annotations

import os
from typing import Optional

import platformdirs

OI_CONFIG_DIR = platformdirs.user_config_dir("open-interpreter")


def get_config_directory() -> str:
    """Return the root directory for interpreter configuration data."""

    return OI_CONFIG_DIR


def get_storage_path(subdirectory: Optional[str] = None) -> str:
    """Return the path to the storage subdirectory within the config dir."""

    if subdirectory is None:
        return OI_CONFIG_DIR
    return os.path.join(OI_CONFIG_DIR, subdirectory)


__all__ = ["OI_CONFIG_DIR", "get_config_directory", "get_storage_path"]
