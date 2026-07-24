"""Regression tests for exact completed-candle schedule alignment."""

from decimal import Decimal

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.research.contracts import StrategyContext
from gemini_trading.strategy.arbitration import ArbitrationInput, MultiModelArbiter
from gemini_trading.strategy.candidate import CandidateDecisionSchedule, CandidateMultiModelStrategy
from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.policy import CandidatePolicy
from strategy_fixture_support import btc_candle


def test_candidate_reads_only_the_exact_current_schedule_row() -> None:
    decision = MultiModelArbiter(CandidatePolicy.locked_v0_1()).decide(
        ArbitrationInput(
            candle_index=43,
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
    strategy = CandidateMultiModelStrategy(
        schedule=CandidateDecisionSchedule((decision,)),
        quantity_step=Decimal("0.001"),
        minimum_quantity=Decimal("0.001"),
        minimum_notional=Decimal("5"),
    )
    account = AccountSnapshot.initial(Decimal("10000"))

    prior = strategy.on_candle(
        StrategyContext(
            candle_index=42,
            candle=btc_candle(42, close=Decimal("100")),
            account=account,
            active_orders=(),
        )
    )
    current = strategy.on_candle(
        StrategyContext(
            candle_index=43,
            candle=btc_candle(43, close=Decimal("100")),
            account=account,
            active_orders=(),
        )
    )

    assert prior == ()
    assert len(current) == 1
