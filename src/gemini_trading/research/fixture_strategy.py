"""Scripted non-production strategy used only to verify the research engine."""

from dataclasses import dataclass, field

from gemini_trading.domain.order import OrderIntent
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.research.errors import StrategyContractError
from gemini_trading.research.serialization import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class ScriptedFixtureStrategy:
    """Return predefined intents at exact candle indexes without prediction logic."""

    script: tuple[tuple[int, tuple[OrderIntent, ...]], ...]
    strategy_id: str = field(default="fixture.scripted.v1", init=False)
    production_eligible: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        indexes = tuple(candle_index for candle_index, _ in self.script)
        if any(candle_index < 0 for candle_index in indexes):
            raise StrategyContractError("script candle indexes must be non-negative")
        if len(indexes) != len(set(indexes)):
            raise StrategyContractError("script contains a duplicate candle index")
        object.__setattr__(self, "script", tuple(sorted(self.script, key=lambda item: item[0])))

    def configuration(self) -> tuple[tuple[str, str], ...]:
        """Return stable, human-readable configuration evidence."""

        entries: list[dict[str, object]] = []
        for candle_index, intents in self.script:
            entries.append(
                {
                    "candle_index": candle_index,
                    "intents": [
                        {
                            "side": intent.side.value,
                            "order_type": intent.order_type.value,
                            "quantity": intent.quantity,
                            "limit_price": intent.limit_price,
                            "time_in_force": intent.time_in_force.value,
                        }
                        for intent in intents
                    ],
                }
            )
        encoded = canonical_json_bytes({"entries": entries}).decode("utf-8").removesuffix("\n")
        return (("script", encoded),)

    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]:
        """Return only the immutable intents assigned to the current candle index."""

        for candle_index, intents in self.script:
            if candle_index == context.candle_index:
                return intents
            if candle_index > context.candle_index:
                break
        return ()
