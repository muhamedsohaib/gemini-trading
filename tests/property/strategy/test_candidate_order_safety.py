"""Property tests for Candidate v0.1 long-only order safety."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.order import OrderSide
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.strategy.arbitration import (
    ArbitrationDecision,
    ArbitrationInput,
    MultiModelArbiter,
)
from gemini_trading.strategy.candidate import CandidateDecisionSchedule, CandidateMultiModelStrategy
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import btc_candle


def candidate(decision: ArbitrationDecision) -> CandidateMultiModelStrategy:
    return CandidateMultiModelStrategy(
        schedule=CandidateDecisionSchedule((decision,)),
        quantity_step=Decimal("0.001"),
        minimum_quantity=Decimal("0.001"),
        minimum_notional=Decimal("1"),
    )


def entering_decision() -> ArbitrationDecision:
    return MultiModelArbiter(CandidatePolicy.locked_v0_1()).decide(
        ArbitrationInput(
            candle_index=42,
            regime=RegimeState.TRENDING,
            trend_probability=Decimal("0.62"),
            trend_expected_gross_return=Decimal("0.0071"),
            mean_reversion_probability=Decimal("0.45"),
            mean_reversion_expected_gross_return=Decimal("0"),
            currently_long=False,
            active_specialist=None,
            hold_age=0,
            cooldown_remaining=0,
            indeterminate_streak=0,
            entry_price=None,
            highest_close_since_entry=None,
            current_close=Decimal("100"),
            current_low=Decimal("99"),
            atr24=Decimal("2"),
            current_stop=None,
            stretch_active=False,
            base_hurdle_bps=Decimal("60"),
        )
    )


def exiting_decision() -> ArbitrationDecision:
    return MultiModelArbiter(CandidatePolicy.locked_v0_1()).decide(
        ArbitrationInput(
            candle_index=42,
            regime=RegimeState.TRENDING,
            trend_probability=Decimal("0.45"),
            trend_expected_gross_return=Decimal("0"),
            mean_reversion_probability=Decimal("0.50"),
            mean_reversion_expected_gross_return=Decimal("0"),
            currently_long=True,
            active_specialist=SpecialistKind.TREND,
            hold_age=2,
            cooldown_remaining=0,
            indeterminate_streak=0,
            entry_price=Decimal("100"),
            highest_close_since_entry=Decimal("102"),
            current_close=Decimal("100"),
            current_low=Decimal("99"),
            atr24=Decimal("2"),
            current_stop=Decimal("90"),
            stretch_active=False,
            base_hurdle_bps=Decimal("60"),
        )
    )


@given(
    cash_units=st.integers(min_value=1000, max_value=10_000_000),
    price_units=st.integers(min_value=100, max_value=1_000_000),
)
def test_buy_quantity_never_exceeds_available_cash_at_completed_close(
    cash_units: int,
    price_units: int,
) -> None:
    cash = Decimal(cash_units) / Decimal("100")
    price = Decimal(price_units) / Decimal("100")
    strategy = candidate(entering_decision())
    intents = strategy.on_candle(
        StrategyContext(
            candle_index=42,
            candle=btc_candle(42, close=price),
            account=AccountSnapshot.initial(cash),
            active_orders=(),
        )
    )

    if intents:
        assert intents[0].side is OrderSide.BUY
        assert intents[0].quantity * price <= cash


@given(quantity_units=st.integers(min_value=1, max_value=1_000_000))
def test_sell_quantity_equals_and_never_exceeds_position(quantity_units: int) -> None:
    quantity = Decimal(quantity_units) / Decimal("1000")
    cash = Decimal("100")
    equity = cash + quantity * Decimal("100")
    account = AccountSnapshot(
        cash=cash,
        reserved_cash=Decimal("0"),
        position_quantity=quantity,
        average_entry_price=Decimal("100"),
        realized_pnl=Decimal("0"),
        cumulative_fees=Decimal("0"),
        cumulative_execution_costs=Decimal("0"),
        marked_equity=equity,
        peak_equity=equity,
        drawdown=Decimal("0"),
    )
    intents = candidate(exiting_decision()).on_candle(
        StrategyContext(
            candle_index=42,
            candle=btc_candle(42, close=Decimal("100")),
            account=account,
            active_orders=(),
        )
    )

    assert len(intents) == 1
    assert intents[0].side is OrderSide.SELL_TO_CLOSE
    assert intents[0].quantity == quantity
