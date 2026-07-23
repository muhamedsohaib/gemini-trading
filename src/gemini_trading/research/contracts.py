"""Read-only strategy contracts for deterministic completed-candle research."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.order import OrderIntent, SimulatedOrder
from gemini_trading.domain.time import require_utc
from gemini_trading.research.errors import StrategyContractError


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """The complete immutable state visible to one strategy decision."""

    candle_index: int
    candle: Candle
    account: AccountSnapshot
    active_orders: tuple[SimulatedOrder, ...]

    def __post_init__(self) -> None:
        if self.candle_index < 0:
            raise StrategyContractError("candle index must be non-negative")
        if not self.candle.completed:
            raise StrategyContractError("strategy context requires a completed candle")


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """One immutable strategy response recorded by the chronological engine."""

    decision_sequence: int
    candle_index: int
    candle_open_time: datetime
    intents: tuple[OrderIntent, ...]

    def __post_init__(self) -> None:
        if self.decision_sequence < 1:
            raise StrategyContractError("decision sequence must be positive")
        if self.candle_index < 0:
            raise StrategyContractError("candle index must be non-negative")
        try:
            require_utc(self.candle_open_time, "candle_open_time")
        except ValueError as error:
            raise StrategyContractError(str(error)) from None


class Strategy(Protocol):
    """Deterministic strategy interface shared by research engine implementations."""

    @property
    def strategy_id(self) -> str: ...

    @property
    def production_eligible(self) -> bool: ...

    def configuration(self) -> tuple[tuple[str, str], ...]: ...

    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]: ...
