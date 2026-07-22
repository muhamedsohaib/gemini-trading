"""Runtime mode policy that refuses all exchange submission."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class ExecutionMode(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"


class UnsafeExecutionModeError(RuntimeError):
    """Raised when configuration requests a prohibited execution mode."""


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    mode: ExecutionMode
    exchange_submission_allowed: bool = False


def load_runtime_policy(environment: dict[str, str] | None = None) -> RuntimePolicy:
    source = os.environ if environment is None else environment
    raw_mode = source.get("GEMINI_TRADING_MODE", ExecutionMode.PAPER.value)
    normalized = raw_mode.strip().lower()

    try:
        mode = ExecutionMode(normalized)
    except ValueError as exc:
        raise UnsafeExecutionModeError(
            f"Execution mode {raw_mode!r} is prohibited; only research and paper are allowed."
        ) from exc

    return RuntimePolicy(mode=mode)
