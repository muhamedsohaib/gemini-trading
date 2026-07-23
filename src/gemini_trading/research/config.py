"""Validated deterministic backtesting simulation configuration."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import TimeInForce
from gemini_trading.research.errors import InvalidExperimentConfigError
from gemini_trading.research.serialization import canonical_json_bytes


def _non_negative(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value < 0:
        raise InvalidExperimentConfigError(f"{field_name} must be finite and non-negative")


def _positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise InvalidExperimentConfigError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """All deterministic execution assumptions for one backtest."""

    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    half_spread_bps: Decimal
    slippage_bps: Decimal
    latency_bars: int
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_volume_participation: Decimal
    max_active_candles: int
    timing_policy: TimingPolicy
    limit_fill_policy: LimitFillPolicy
    default_time_in_force: TimeInForce
    promotable: bool

    def __post_init__(self) -> None:
        for field_name, value in (
            ("maker_fee_rate", self.maker_fee_rate),
            ("taker_fee_rate", self.taker_fee_rate),
            ("half_spread_bps", self.half_spread_bps),
            ("slippage_bps", self.slippage_bps),
        ):
            _non_negative(value, field_name)
        for field_name, value in (
            ("price_tick", self.price_tick),
            ("quantity_step", self.quantity_step),
            ("min_quantity", self.min_quantity),
            ("min_notional", self.min_notional),
        ):
            _positive(value, field_name)
        if isinstance(self.latency_bars, bool) or self.latency_bars < 0:
            raise InvalidExperimentConfigError("latency_bars must be a non-negative integer")
        if isinstance(self.max_active_candles, bool) or self.max_active_candles < 1:
            raise InvalidExperimentConfigError("max_active_candles must be a positive integer")
        if (
            not self.max_volume_participation.is_finite()
            or not Decimal("0") < self.max_volume_participation <= Decimal("1")
        ):
            raise InvalidExperimentConfigError(
                "max_volume_participation must be greater than zero and no greater than one"
            )

        diagnostic = (
            self.timing_policy is not TimingPolicy.NEXT_CANDLE
            or self.limit_fill_policy is not LimitFillPolicy.CONSERVATIVE
        )
        if diagnostic:
            object.__setattr__(self, "promotable", False)
        if self.promotable and all(
            value == 0
            for value in (
                self.maker_fee_rate,
                self.taker_fee_rate,
                self.half_spread_bps,
                self.slippage_bps,
            )
        ):
            raise InvalidExperimentConfigError(
                "official promotable configuration requires non-zero trading costs"
            )

    @classmethod
    def official(
        cls,
        *,
        maker_fee_rate: Decimal,
        taker_fee_rate: Decimal,
        half_spread_bps: Decimal,
        slippage_bps: Decimal,
        latency_bars: int,
        price_tick: Decimal,
        quantity_step: Decimal,
        min_quantity: Decimal,
        min_notional: Decimal,
        max_volume_participation: Decimal,
        max_active_candles: int = 3,
        timing_policy: TimingPolicy = TimingPolicy.NEXT_CANDLE,
        limit_fill_policy: LimitFillPolicy = LimitFillPolicy.CONSERVATIVE,
        default_time_in_force: TimeInForce = TimeInForce.BAR,
        promotable: bool = True,
    ) -> Self:
        """Build the conservative official policy, allowing explicit diagnostics."""

        return cls(
            maker_fee_rate=maker_fee_rate,
            taker_fee_rate=taker_fee_rate,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
            latency_bars=latency_bars,
            price_tick=price_tick,
            quantity_step=quantity_step,
            min_quantity=min_quantity,
            min_notional=min_notional,
            max_volume_participation=max_volume_participation,
            max_active_candles=max_active_candles,
            timing_policy=timing_policy,
            limit_fill_policy=limit_fill_policy,
            default_time_in_force=default_time_in_force,
            promotable=promotable,
        )


def serialize_simulation_config(config: SimulationConfig) -> bytes:
    """Return canonical bytes for all simulation assumptions."""

    return canonical_json_bytes(
        {
            "maker_fee_rate": config.maker_fee_rate,
            "taker_fee_rate": config.taker_fee_rate,
            "half_spread_bps": config.half_spread_bps,
            "slippage_bps": config.slippage_bps,
            "latency_bars": config.latency_bars,
            "price_tick": config.price_tick,
            "quantity_step": config.quantity_step,
            "min_quantity": config.min_quantity,
            "min_notional": config.min_notional,
            "max_volume_participation": config.max_volume_participation,
            "max_active_candles": config.max_active_candles,
            "timing_policy": config.timing_policy.value,
            "limit_fill_policy": config.limit_fill_policy.value,
            "default_time_in_force": config.default_time_in_force.value,
            "promotable": config.promotable,
        }
    )
