from __future__ import annotations

import atexit
import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


EnsurePathCallable = Callable[[], str]


@dataclass
class Artifact:
    """Metadata for a generated artifact."""

    id: int
    kind: str
    description: str
    ensure_path: EnsurePathCallable
    is_temporary: bool = True
    size_bytes: Optional[int] = None
    preview_label: Optional[str] = None
    _cached_path: Optional[str] = field(default=None, init=False, repr=False)

    def ensure_cached_path(self) -> str:
        """Return a local path to the artifact, materialising it if necessary."""

        if self._cached_path and os.path.exists(self._cached_path):
            return self._cached_path

        path = self.ensure_path()
        self._cached_path = path
        return path

    def cleanup(self) -> None:
        """Remove any temporary files owned by this artifact."""

        if not self.is_temporary:
            return

        path = self._cached_path
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


class ArtifactManager:
    """Tracks artifacts created during a terminal session."""

    def __init__(self) -> None:
        self._artifacts: Dict[int, Artifact] = {}
        self._counter: int = 1
        atexit.register(self.cleanup)

    def register(
        self,
        kind: str,
        description: str,
        ensure_path: EnsurePathCallable,
        *,
        is_temporary: bool = True,
        size_bytes: Optional[int] = None,
        preview_label: Optional[str] = None,
    ) -> Artifact:
        """Register a new artifact and return its metadata."""

        artifact_id = self._counter
        self._counter += 1

        artifact = Artifact(
            id=artifact_id,
            kind=kind,
            description=description,
            ensure_path=ensure_path,
            is_temporary=is_temporary,
            size_bytes=size_bytes,
            preview_label=preview_label,
        )

        self._artifacts[artifact_id] = artifact
        return artifact

    def get(self, artifact_id: int) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)

    def discard(self, artifact_id: int) -> bool:
        artifact = self._artifacts.pop(artifact_id, None)
        if not artifact:
            return False

        artifact.cleanup()
        return True

    def cleanup(self) -> None:
        for artifact_id in list(self._artifacts.keys()):
            self.discard(artifact_id)

    def save(self, artifact_id: int, destination: str) -> Optional[str]:
        artifact = self.get(artifact_id)
        if not artifact:
            return None

        source_path = artifact.ensure_cached_path()
        destination = os.path.expanduser(destination)
        destination = os.path.abspath(destination)

        if os.path.isdir(destination):
            basename = os.path.basename(source_path)
            destination = os.path.join(destination, basename)

        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source_path, destination)
        return destination
