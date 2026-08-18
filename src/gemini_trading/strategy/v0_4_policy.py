"""Version-isolated multi-timeframe policy surface for Candidate v0.4."""

from dataclasses import asdict, dataclass
from decimal import Decimal

from gemini_trading.research.serialization import canonical_json_bytes

_ZERO = Decimal("0")
_ONE = Decimal("1")

_CONTEXT_FEATURE_NAMES = (
    "ctx4h_ema_12_42_signed_atr24",
    "ctx4h_volatility_ratio_6_42",
    "ctx4h_true_range_ratio_24",
    "ctx4h_range_location_24",
    "ctx4h_median_distance_atr24",
    "ctx4h_ema12_slope_3_atr24",
)


@dataclass(frozen=True, slots=True)
class V04MultiTimeframePolicy:
    """Frozen Candidate v0.4 multi-timeframe adjunct policy."""

    schema_version: str
    tactical_timeframe: str
    context_timeframe: str
    context_feature_names: tuple[str, ...]
    entry_percentile: Decimal
    entry_floor: Decimal
    minimum_entry_scores: int
    sensitivity_percentiles: tuple[Decimal, Decimal]
    indeterminate_tolerance_context_bars: int
    incompatible_tolerance_context_bars: int

    def __post_init__(self) -> None:
        for field_name in ("schema_version", "tactical_timeframe", "context_timeframe"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if not self.context_feature_names:
            raise ValueError("context feature names must not be empty")
        if any(not name.strip() for name in self.context_feature_names):
            raise ValueError("context feature names must not contain empty values")
        if len(self.context_feature_names) != len(set(self.context_feature_names)):
            raise ValueError("context feature names must be unique")
        for field_name, value in (
            ("entry_percentile", self.entry_percentile),
            ("entry_floor", self.entry_floor),
            ("sensitivity_percentile_low", self.sensitivity_percentiles[0]),
            ("sensitivity_percentile_high", self.sensitivity_percentiles[1]),
        ):
            if not value.is_finite() or value < _ZERO or value > _ONE:
                raise ValueError(f"{field_name} must be finite and within [0, 1]")
        if isinstance(self.minimum_entry_scores, bool) or self.minimum_entry_scores < 1:
            raise ValueError("minimum_entry_scores must be positive")
        for field_name in (
            "indeterminate_tolerance_context_bars",
            "incompatible_tolerance_context_bars",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")

    @classmethod
    def locked(cls) -> "V04MultiTimeframePolicy":
        """Return the exact preregistered Candidate v0.4 adjunct policy."""

        return cls(
            schema_version="candidate-v0.4-multitimeframe-policy-v1",
            tactical_timeframe="1h",
            context_timeframe="4h",
            context_feature_names=_CONTEXT_FEATURE_NAMES,
            entry_percentile=Decimal("0.75"),
            entry_floor=Decimal("0.50"),
            minimum_entry_scores=160,
            sensitivity_percentiles=(Decimal("0.70"), Decimal("0.80")),
            indeterminate_tolerance_context_bars=1,
            incompatible_tolerance_context_bars=2,
        )


def serialize_v0_4_multitimeframe_policy(policy: V04MultiTimeframePolicy) -> bytes:
    """Return canonical bytes for one Candidate v0.4 adjunct policy."""

    return canonical_json_bytes(asdict(policy))


__all__ = ["V04MultiTimeframePolicy", "serialize_v0_4_multitimeframe_policy"]
