"""Policy for paths that may be tracked in the public repository."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath


class RepositoryPolicyViolation(ValueError):
    """Raised when a prohibited path is tracked."""


_PROHIBITED_NAMES = {".env", ".env.local", "q_table.json", "config.json"}
_PROHIBITED_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".pyc"}


def validate_tracked_paths(paths: Iterable[str]) -> None:
    """Reject tracked paths that contain secrets, certificates, caches, or runtime state."""

    violations: list[str] = []
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        if raw_path == ".env.example":
            continue
        if path.name in _PROHIBITED_NAMES:
            violations.append(raw_path)
            continue
        if path.suffix.lower() in _PROHIBITED_SUFFIXES:
            violations.append(raw_path)
            continue
        if "__pycache__" in path.parts:
            violations.append(raw_path)

    if violations:
        joined = ", ".join(sorted(violations))
        raise RepositoryPolicyViolation(f"Prohibited tracked paths: {joined}")
