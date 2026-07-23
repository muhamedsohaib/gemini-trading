"""Immutable deterministic experiment identity contracts."""

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from gemini_trading.domain.order import TimeInForce

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _require_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


class TimingPolicy(StrEnum):
    """Supported strategy-decision timing policies."""

    NEXT_CANDLE = "next_candle"
    SAME_CLOSE_DIAGNOSTIC = "same_close_diagnostic"


class LimitFillPolicy(StrEnum):
    """Supported candle-only limit-fill assumptions."""

    CONSERVATIVE = "conservative"
    OPTIMISTIC_TOUCH_DIAGNOSTIC = "optimistic_touch_diagnostic"


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    """Deterministic inputs that identify one research experiment."""

    schema_version: str
    dataset_id: str
    canonical_sha256: str
    code_commit: str
    engine_version: str
    strategy_id: str
    strategy_config: tuple[tuple[str, str], ...]
    initial_cash: Decimal
    timing_policy: TimingPolicy
    limit_fill_policy: LimitFillPolicy
    default_time_in_force: TimeInForce
    max_active_candles: int
    random_seed: int
    simulation_config_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_identifier(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self,
            "engine_version",
            _require_identifier(self.engine_version, "engine_version"),
        )
        object.__setattr__(
            self,
            "strategy_id",
            _require_identifier(self.strategy_id, "strategy_id"),
        )
        _require_sha256(self.dataset_id, "dataset_id")
        _require_sha256(self.canonical_sha256, "canonical_sha256")
        _require_sha256(self.simulation_config_sha256, "simulation_config_sha256")
        if _GIT_COMMIT_PATTERN.fullmatch(self.code_commit) is None:
            raise ValueError("code_commit must be a 40-character lowercase Git commit")
        if not self.initial_cash.is_finite() or self.initial_cash <= 0:
            raise ValueError("initial_cash must be finite and positive")
        if self.max_active_candles < 1:
            raise ValueError("max_active_candles must be positive")
        if self.random_seed < 0:
            raise ValueError("random_seed must be non-negative")

        normalized_config: list[tuple[str, str]] = []
        keys: set[str] = set()
        for key, value in self.strategy_config:
            normalized_key = _require_identifier(key, "strategy_config key")
            normalized_value = _require_identifier(value, "strategy_config value")
            if normalized_key in keys:
                raise ValueError("strategy_config keys must be unique")
            keys.add(normalized_key)
            normalized_config.append((normalized_key, normalized_value))
        object.__setattr__(self, "strategy_config", tuple(normalized_config))
