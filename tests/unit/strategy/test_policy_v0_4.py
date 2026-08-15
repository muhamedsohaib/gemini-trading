"""Candidate v0.4 policy identity and multi-timeframe contract tests."""

from collections.abc import Callable
from importlib import util
from typing import cast

import pytest

from gemini_trading.strategy.policy import CandidatePolicy, approved_candidate_policy


def _locked_v0_4() -> CandidatePolicy:
    constructor = cast(
        Callable[[], CandidatePolicy] | None,
        getattr(CandidatePolicy, "locked_v0_4", None),
    )
    assert constructor is not None, "Candidate v0.4 policy constructor is missing"
    return constructor()


def test_locked_v0_4_translates_real_time_contract_to_hourly_policy() -> None:
    policy = _locked_v0_4()

    assert policy.strategy_id == "candidate.multi_model.v0_4"
    assert policy.policy_version == "candidate-multi-model-v0.4"
    assert policy.schema_version == "candidate-strategy-policy-v4"
    assert (policy.instrument_symbol, policy.timeframe) == ("BTCUSDT", "1h")
    assert policy.label_horizon_candles == 12
    assert policy.maximum_feature_lookback_candles == 42
    assert policy.minimum_hold_candles == 8
    assert policy.maximum_hold_candles == 72
    assert policy.cooldown_candles == 8
    assert policy.purge_candles == 12
    assert policy.embargo_candles == 12
    assert policy.calibration_minimum_observations == 800
    assert policy.calibration_minimum_positive == 160
    assert policy.calibration_minimum_negative == 160
    assert policy.bootstrap_block_candles == 168


def test_approved_candidate_policy_accepts_only_exact_v0_4_identity_pair() -> None:
    policy = approved_candidate_policy(
        "candidate.multi_model.v0_4",
        "candidate-multi-model-v0.4",
    )
    assert policy == _locked_v0_4()

    with pytest.raises(ValueError, match="identity pair"):
        approved_candidate_policy(
            "candidate.multi_model.v0_4",
            "candidate-multi-model-v0.3",
        )


def test_v0_4_multitimeframe_adjunct_module_is_required() -> None:
    module_name = "gemini_trading.strategy.v0_4_policy"
    assert util.find_spec(module_name) is not None, (
        "Candidate v0.4 adjunct policy module is missing"
    )
