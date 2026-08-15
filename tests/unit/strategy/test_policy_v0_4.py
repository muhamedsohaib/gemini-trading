"""Candidate v0.4 policy identity and multi-timeframe contract tests."""

from decimal import Decimal
from importlib import import_module, util

import pytest

from gemini_trading.strategy.policy import CandidatePolicy, approved_candidate_policy


def test_locked_v0_4_translates_real_time_contract_to_hourly_policy() -> None:
    policy = CandidatePolicy.locked_v0_4()

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
    assert policy == CandidatePolicy.locked_v0_4()

    with pytest.raises(ValueError, match="identity pair"):
        approved_candidate_policy(
            "candidate.multi_model.v0_4",
            "candidate-multi-model-v0.3",
        )


def test_locked_v0_4_multitimeframe_adjunct_is_exact_and_bounded() -> None:
    module_name = "gemini_trading.strategy.v0_4_policy"
    assert util.find_spec(module_name) is not None, (
        "Candidate v0.4 adjunct policy module is missing"
    )
    module = import_module(module_name)
    policy_type = getattr(module, "V04MultiTimeframePolicy")
    policy = policy_type.locked()

    assert policy.schema_version == "candidate-v0.4-multitimeframe-policy-v1"
    assert policy.tactical_timeframe == "1h"
    assert policy.context_timeframe == "4h"
    assert policy.context_feature_names == (
        "ctx4h_ema_12_42_signed_atr24",
        "ctx4h_volatility_ratio_6_42",
        "ctx4h_true_range_ratio_24",
        "ctx4h_range_location_24",
        "ctx4h_median_distance_atr24",
        "ctx4h_ema12_slope_3_atr24",
    )
    assert policy.entry_percentile == Decimal("0.75")
    assert policy.entry_floor == Decimal("0.50")
    assert policy.minimum_entry_scores == 160
    assert policy.sensitivity_percentiles == (Decimal("0.70"), Decimal("0.80"))
    assert policy.indeterminate_tolerance_context_bars == 1
    assert policy.incompatible_tolerance_context_bars == 2
