"""Immutable contracts shared by candidate-strategy research components."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


def _identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


class RegimeState(StrEnum):
    """Closed deterministic market-regime states."""

    UNSTABLE = "unstable"
    TRENDING = "trending"
    RANGING = "ranging"
    INDETERMINATE = "indeterminate"


class SpecialistKind(StrEnum):
    """Closed learned-specialist identities."""

    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"


class StrategyAction(StrEnum):
    """Permitted long-or-cash candidate actions."""

    ENTER_LONG = "enter_long"
    REMAIN_LONG = "remain_long"
    EXIT_TO_CASH = "exit_to_cash"
    REMAIN_IN_CASH = "remain_in_cash"


@dataclass(frozen=True, slots=True)
class IndexWindow:
    """One strict half-open chronological index window."""

    start_inclusive: int
    end_exclusive: int

    def __post_init__(self) -> None:
        if isinstance(self.start_inclusive, bool) or self.start_inclusive < 0:
            raise ValueError("start_inclusive must be a non-negative integer")
        if isinstance(self.end_exclusive, bool) or self.end_exclusive <= self.start_inclusive:
            raise ValueError("end_exclusive must be greater than start_inclusive")

    def contains(self, index: int) -> bool:
        """Return whether an integer index belongs to the window."""

        return self.start_inclusive <= index < self.end_exclusive


@dataclass(frozen=True, slots=True)
class SpecialistPrediction:
    """One immutable calibrated specialist output at a completed candle."""

    candle_index: int
    specialist: SpecialistKind
    raw_score_hex: str
    probability: Decimal
    expected_gross_return: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.candle_index, bool) or self.candle_index < 0:
            raise ValueError("candle_index must be a non-negative integer")
        raw_score_hex = _identifier(self.raw_score_hex, "raw_score_hex")
        try:
            raw_score = float.fromhex(raw_score_hex)
        except ValueError:
            raise ValueError("raw_score_hex must contain one hexadecimal float") from None
        if not (-float("inf") < raw_score < float("inf")):
            raise ValueError("raw_score_hex must contain a finite hexadecimal float")
        _finite(self.probability, "probability")
        if not Decimal("0") <= self.probability <= Decimal("1"):
            raise ValueError("probability must be within [0, 1]")
        _finite(self.expected_gross_return, "expected_gross_return")
        object.__setattr__(self, "raw_score_hex", raw_score_hex)


@dataclass(frozen=True, slots=True)
class GateResult:
    """One explicit immutable promotion-gate result."""

    gate_id: str
    passed: bool
    observed: str
    required: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", _identifier(self.gate_id, "gate_id"))
        object.__setattr__(self, "observed", _identifier(self.observed, "observed"))
        object.__setattr__(self, "required", _identifier(self.required, "required"))
        object.__setattr__(self, "reason", _identifier(self.reason, "reason"))
