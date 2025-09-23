"""Compatibility shim for storage path resolution."""

from __future__ import annotations

from open_interpreter.infrastructure.storage import get_storage_path as _get_storage_path

__all__ = ["get_storage_path"]


def get_storage_path(subdirectory=None):
    """Return storage locations via the modular infrastructure helper."""

    return _get_storage_path(subdirectory)
