"""Regression tests for the Candidate final-test seal."""

from datetime import UTC, datetime

import pytest

from gemini_trading.strategy.errors import FinalTestSealError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import DevelopmentSelector, FinalTestSeal
from strategy_fixture_support import calendar_candles


def _split_plan() -> ChronologicalSplitPlan:
    candles = calendar_candles(
        start=datetime(2018, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return ChronologicalSplitPlan.build(
        candles,
        tuple(range(42, len(candles) - 4)),
        CandidatePolicy.locked_v0_1(),
    )


def test_development_selector_cannot_read_final_test() -> None:
    plan = _split_plan()
    seal = FinalTestSeal.create(
        plan,
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )

    with pytest.raises(FinalTestSealError, match="final test"):
        DevelopmentSelector(seal).read_predictions(plan.final_test)


def test_final_evaluation_is_authorized_exactly_once() -> None:
    plan = _split_plan()
    seal = FinalTestSeal.create(
        plan,
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )

    receipt = seal.authorize_final(
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )

    assert receipt.evaluation_count == 1
    assert receipt.final_test == plan.final_test
    with pytest.raises(FinalTestSealError, match="already evaluated"):
        seal.authorize_final(
            policy_sha256="a" * 64,
            configuration_sha256="b" * 64,
        )


def test_post_seal_identity_change_is_rejected() -> None:
    plan = _split_plan()
    seal = FinalTestSeal.create(
        plan,
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )

    with pytest.raises(FinalTestSealError, match="identity"):
        seal.authorize_final(
            policy_sha256="c" * 64,
            configuration_sha256="b" * 64,
        )
