"""Conservative point-in-time labels aligned to official simulator economics."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import OrderSide
from gemini_trading.execution.simulator.costs import market_fill_costs
from gemini_trading.execution.simulator.precision import round_fill_price
from gemini_trading.research.config import SimulationConfig

_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)
_BASIS_POINTS = Decimal("10000")
_ONE = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class LabelObservation:
    """One immutable cost-aware outcome aligned to a completed decision candle."""

    decision_candle_index: int
    entry_candle_index: int
    exit_candle_index: int
    entry_reference_price: Decimal
    exit_reference_price: Decimal
    entry_fill_price: Decimal
    exit_fill_price: Decimal
    gross_return: Decimal
    net_return: Decimal
    hurdle_bps: Decimal
    positive: bool

    def __post_init__(self) -> None:
        if isinstance(self.decision_candle_index, bool) or self.decision_candle_index < 0:
            raise ValueError("decision_candle_index must be a non-negative integer")
        if self.entry_candle_index != self.decision_candle_index + 1:
            raise ValueError("entry_candle_index must be the next candle")
        if self.exit_candle_index <= self.entry_candle_index:
            raise ValueError("exit_candle_index must be after entry_candle_index")
        for field_name in (
            "entry_reference_price",
            "exit_reference_price",
            "entry_fill_price",
            "exit_fill_price",
        ):
            value = getattr(self, field_name)
            if not value.is_finite() or value <= 0:
                raise ValueError(f"{field_name} must be finite and positive")
        for field_name in ("gross_return", "net_return", "hurdle_bps"):
            value = getattr(self, field_name)
            if not value.is_finite():
                raise ValueError(f"{field_name} must be finite")
        if self.hurdle_bps < 0:
            raise ValueError("hurdle_bps must be non-negative")


@dataclass(frozen=True, slots=True)
class LabelVector:
    """Ordered immutable labels for one locked policy and canonical dataset."""

    schema_version: str
    horizon_candles: int
    hurdle_bps: Decimal
    observations: tuple[LabelObservation, ...]

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("label vector schema_version must not be empty")
        if isinstance(self.horizon_candles, bool) or self.horizon_candles < 1:
            raise ValueError("horizon_candles must be positive")
        if not self.hurdle_bps.is_finite() or self.hurdle_bps < 0:
            raise ValueError("hurdle_bps must be finite and non-negative")
        indexes = tuple(item.decision_candle_index for item in self.observations)
        if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
            raise ValueError("label observations must have unique ordered indexes")
        if any(item.hurdle_bps != self.hurdle_bps for item in self.observations):
            raise ValueError("label observations must use the vector hurdle")
        if any(
            item.exit_candle_index - item.entry_candle_index != self.horizon_candles
            for item in self.observations
        ):
            raise ValueError("label observations must use the vector horizon")

    def for_index(self, decision_candle_index: int) -> LabelObservation:
        """Return one label by exact decision-candle index."""

        for observation in self.observations:
            if observation.decision_candle_index == decision_candle_index:
                return observation
        raise KeyError(f"label is unavailable for candle index {decision_candle_index}")


@dataclass(frozen=True, slots=True)
class LabelPolicy:
    """Locked Candidate v0.1 label timing and execution-cost assumptions."""

    schema_version: str
    simulation: SimulationConfig
    horizon_candles: int
    extra_hurdle_bps: Decimal

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("label policy schema_version must not be empty")
        if isinstance(self.horizon_candles, bool) or self.horizon_candles < 1:
            raise ValueError("horizon_candles must be positive")
        if not self.extra_hurdle_bps.is_finite() or self.extra_hurdle_bps < 0:
            raise ValueError("extra_hurdle_bps must be finite and non-negative")
        if self.simulation.timing_policy is not TimingPolicy.NEXT_CANDLE:
            raise ValueError("label policy requires next-candle timing")
        if self.simulation.limit_fill_policy is not LimitFillPolicy.CONSERVATIVE:
            raise ValueError("label policy requires conservative fills")
        if not self.simulation.promotable:
            raise ValueError("label policy requires a promotable simulation policy")

    @classmethod
    def locked_v0_1(cls, simulation: SimulationConfig) -> "LabelPolicy":
        """Return the approved three-candle label policy."""

        return cls(
            schema_version="candidate-label-policy-v1",
            simulation=simulation,
            horizon_candles=3,
            extra_hurdle_bps=Decimal("10"),
        )

    @property
    def hurdle_bps(self) -> Decimal:
        """Return the round-trip execution hurdle plus the approved edge buffer."""

        one_side = (
            self.simulation.taker_fee_rate * _BASIS_POINTS
            + self.simulation.half_spread_bps
            + self.simulation.slippage_bps
        )
        return one_side * Decimal("2") + self.extra_hurdle_bps

    def build(
        self,
        candles: tuple[Candle, ...],
        *,
        eligible_indices: tuple[int, ...],
    ) -> LabelVector:
        """Build labels whose complete future outcome is available locally."""

        _validate_candles(candles)
        observations: list[LabelObservation] = []
        seen: set[int] = set()
        with localcontext(_CONTEXT):
            for decision_index in sorted(eligible_indices):
                if isinstance(decision_index, bool) or decision_index < 0:
                    raise ValueError("eligible label indexes must be non-negative integers")
                if decision_index in seen:
                    raise ValueError("eligible label indexes must be unique")
                seen.add(decision_index)
                entry_index = decision_index + 1
                exit_index = entry_index + self.horizon_candles
                if exit_index >= len(candles):
                    continue
                observations.append(
                    self._observation(
                        decision_index=decision_index,
                        entry_index=entry_index,
                        exit_index=exit_index,
                        candles=candles,
                    )
                )
        return LabelVector(
            schema_version="candidate-label-vector-v1",
            horizon_candles=self.horizon_candles,
            hurdle_bps=self.hurdle_bps,
            observations=tuple(observations),
        )

    def _observation(
        self,
        *,
        decision_index: int,
        entry_index: int,
        exit_index: int,
        candles: tuple[Candle, ...],
    ) -> LabelObservation:
        entry_reference = candles[entry_index].open
        exit_reference = candles[exit_index].open
        quantity = _ONE
        buy_costs = market_fill_costs(
            reference_price=entry_reference,
            quantity=quantity,
            side=OrderSide.BUY,
            half_spread_bps=self.simulation.half_spread_bps,
            slippage_bps=self.simulation.slippage_bps,
            fee_rate=self.simulation.taker_fee_rate,
        )
        sell_costs = market_fill_costs(
            reference_price=exit_reference,
            quantity=quantity,
            side=OrderSide.SELL_TO_CLOSE,
            half_spread_bps=self.simulation.half_spread_bps,
            slippage_bps=self.simulation.slippage_bps,
            fee_rate=self.simulation.taker_fee_rate,
        )
        entry_fill = round_fill_price(
            buy_costs.fill_price,
            self.simulation.price_tick,
            OrderSide.BUY,
        )
        exit_fill = round_fill_price(
            sell_costs.fill_price,
            self.simulation.price_tick,
            OrderSide.SELL_TO_CLOSE,
        )
        buy_notional = entry_fill * quantity
        sell_notional = exit_fill * quantity
        buy_fee = buy_notional * self.simulation.taker_fee_rate
        sell_fee = sell_notional * self.simulation.taker_fee_rate
        entry_cost = buy_notional + buy_fee
        exit_proceeds = sell_notional - sell_fee
        if entry_cost <= 0:
            raise ValueError("label entry cost must be positive")
        gross_return = exit_fill / entry_fill - _ONE
        net_return = (exit_proceeds - entry_cost) / entry_cost
        hurdle_rate = self.hurdle_bps / _BASIS_POINTS
        return LabelObservation(
            decision_candle_index=decision_index,
            entry_candle_index=entry_index,
            exit_candle_index=exit_index,
            entry_reference_price=entry_reference,
            exit_reference_price=exit_reference,
            entry_fill_price=entry_fill,
            exit_fill_price=exit_fill,
            gross_return=gross_return,
            net_return=net_return,
            hurdle_bps=self.hurdle_bps,
            positive=net_return > hurdle_rate,
        )


def _validate_candles(candles: tuple[Candle, ...]) -> None:
    if not candles:
        return
    first = candles[0]
    prior_open_time = None
    for candle in candles:
        if not candle.completed:
            raise ValueError("label computation requires completed candles")
        if candle.instrument != first.instrument or candle.timeframe != first.timeframe:
            raise ValueError("label candles must share instrument and timeframe")
        if prior_open_time is not None and candle.open_time <= prior_open_time:
            raise ValueError("label candles must be strictly chronological")
        prior_open_time = candle.open_time
        for field_name, value in (
            ("open", candle.open),
            ("high", candle.high),
            ("low", candle.low),
            ("close", candle.close),
            ("volume", candle.volume),
        ):
            if not value.is_finite():
                raise ValueError(f"label candle {field_name} must be finite")
        if candle.open <= _ZERO:
            raise ValueError("label candle open must be positive")
