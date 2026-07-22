"""Policy for paths that may be tracked in the public repository."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath


class RepositoryPolicyViolation(ValueError):
    """Raised when a prohibited path is tracked."""


_PROHIBITED_NAMES = {".env", ".env.local", "q_table.json", "config.json"}
_PROHIBITED_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".pyc"}
GENERATED_MARKET_DATA_PREFIXES = ("data/raw/", "data/canonical/")


def _reject_generated_market_data(raw_path: str) -> None:
    normalized = PurePosixPath(raw_path.replace("\\", "/")).as_posix()
    if normalized.startswith(GENERATED_MARKET_DATA_PREFIXES):
        raise RepositoryPolicyViolation(
            f"generated market data must not be tracked: {raw_path}"
        )


def validate_tracked_paths(paths: Iterable[str]) -> None:
    """Reject tracked paths that contain secrets, caches, or generated runtime state."""

    violations: list[str] = []
    for raw_path in paths:
        _reject_generated_market_data(raw_path)
        normalized = raw_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if normalized == ".env.example":
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
