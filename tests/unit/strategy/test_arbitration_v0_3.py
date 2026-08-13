"""Candidate v0.3 arbitration-overlay contract tests."""

from __future__ import annotations

import importlib
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from gemini_trading.strategy.arbitration import ArbitrationInput, MultiModelArbiter
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.policy import CandidatePolicy


def _overlay(**changes: object) -> Any:
    module = importlib.import_module("gemini_trading.strategy.arbitration")
    overlay_type = getattr(module, "ArbitrationOverlay", None)
    assert overlay_type is not None, "arbitration must define ArbitrationOverlay"
    return overlay_type(**changes)


def _flat(**changes: object) -> ArbitrationInput:
    source = ArbitrationInput(
        candle_index=100,
        regime=RegimeState.TRENDING,
        trend_probability=Decimal("0.62"),
        trend_expected_gross_return=Decimal("0.008"),
        mean_reversion_probability=Decimal("0.45"),
        mean_reversion_expected_gross_return=Decimal("0.001"),
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
    return replace(source, **changes)


def _long(**changes: object) -> ArbitrationInput:
    source = _flat(
        currently_long=True,
        active_specialist=SpecialistKind.TREND,
        hold_age=2,
        entry_price=Decimal("100"),
        highest_close_since_entry=Decimal("110"),
        current_close=Decimal("108"),
        current_low=Decimal("107"),
        current_stop=Decimal("100"),
        trend_probability=Decimal("0.50"),
    )
    return replace(source, **changes)


def _arbiter() -> MultiModelArbiter:
    return MultiModelArbiter(CandidatePolicy.locked_v0_3())


def test_overlay_defaults_preserve_existing_cash_decision_exactly() -> None:
    source = _flat()
    baseline = _arbiter().decide(source)
    overlaid = _arbiter().decide(source, _overlay())

    assert overlaid == baseline


def test_v0_3_overlay_makes_companion_and_disagreement_diagnostic_only() -> None:
    source = _flat(
        trend_probability=Decimal("0.58"),
        mean_reversion_probability=Decimal("0.20"),
    )
    baseline = _arbiter().decide(source)
    overlaid = _arbiter().decide(
        source,
        _overlay(
            entry_probability_threshold=Decimal("0.58"),
            enforce_companion_probability=False,
            enforce_disagreement=False,
        ),
    )

    assert baseline.action is StrategyAction.REMAIN_IN_CASH
    assert "active_probability_below_entry" in baseline.reasons
    assert "companion_probability_below_floor" in baseline.reasons
    assert "specialist_disagreement" in baseline.reasons
    assert overlaid.action is StrategyAction.ENTER_LONG
    assert overlaid.active_specialist is SpecialistKind.TREND


def test_v0_3_overlay_does_not_relax_expected_edge_gate() -> None:
    source = _flat(
        trend_probability=Decimal("0.58"),
        mean_reversion_probability=Decimal("0.20"),
        trend_expected_gross_return=Decimal("0.0070"),
    )
    decision = _arbiter().decide(
        source,
        _overlay(
            entry_probability_threshold=Decimal("0.58"),
            enforce_companion_probability=False,
            enforce_disagreement=False,
        ),
    )

    assert decision.action is StrategyAction.REMAIN_IN_CASH
    assert "expected_edge_below_entry_hurdle" in decision.reasons


def test_v0_3_overlay_does_not_relax_ranging_stretch_gate() -> None:
    source = _flat(
        regime=RegimeState.RANGING,
        trend_probability=Decimal("0.20"),
        mean_reversion_probability=Decimal("0.58"),
        mean_reversion_expected_gross_return=Decimal("0.008"),
    )
    overlay = _overlay(
        entry_probability_threshold=Decimal("0.58"),
        enforce_companion_probability=False,
        enforce_disagreement=False,
    )

    rejected = _arbiter().decide(source, overlay)
    accepted = _arbiter().decide(replace(source, stretch_active=True), overlay)

    assert rejected.action is StrategyAction.REMAIN_IN_CASH
    assert rejected.reasons == ("ranging_without_stretch",)
    assert accepted.action is StrategyAction.ENTER_LONG
    assert accepted.active_specialist is SpecialistKind.MEAN_REVERSION


def test_overlay_is_ignored_for_existing_long_state_machine() -> None:
    source = _long(trend_probability=Decimal("0.45"))
    baseline = _arbiter().decide(source)
    overlaid = _arbiter().decide(
        source,
        _overlay(
            entry_probability_threshold=Decimal("0.10"),
            enforce_companion_probability=False,
            enforce_disagreement=False,
        ),
    )

    assert baseline.action is StrategyAction.EXIT_TO_CASH
    assert overlaid == baseline


@pytest.mark.parametrize("threshold", (Decimal("-0.01"), Decimal("1.01"), Decimal("NaN")))
def test_overlay_rejects_invalid_entry_probability_threshold(threshold: Decimal) -> None:
    with pytest.raises(ValueError, match="entry_probability_threshold"):
        _overlay(entry_probability_threshold=threshold)
