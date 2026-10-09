"""Candidate v0.4 policy identity and multi-timeframe contract tests."""

from collections.abc import Callable
from decimal import Decimal
from importlib import import_module, util
from typing import Protocol, cast

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.policy import CandidatePolicy, approved_candidate_policy

_CONTEXT_FEATURE_NAMES = (
    "ctx4h_ema_12_42_signed_atr24",
    "ctx4h_volatility_ratio_6_42",
    "ctx4h_true_range_ratio_24",
    "ctx4h_range_location_24",
    "ctx4h_median_distance_atr24",
    "ctx4h_ema12_slope_3_atr24",
)


class _V04PolicyView(Protocol):
    schema_version: str
    tactical_timeframe: str
    context_timeframe: str
    context_feature_names: tuple[str, ...]
    entry_percentile: Decimal
    entry_floor: Decimal
    minimum_entry_scores: int
    sensitivity_percentiles: tuple[Decimal, Decimal]
    indeterminate_tolerance_context_bars: int
    incompatible_tolerance_context_bars: int


class _V04PolicyConstructor(Protocol):
    def __call__(
        self,
        *,
        schema_version: str,
        tactical_timeframe: str,
        context_timeframe: str,
        context_feature_names: tuple[str, ...],
        entry_percentile: Decimal,
        entry_floor: Decimal,
        minimum_entry_scores: int,
        sensitivity_percentiles: tuple[Decimal, Decimal],
        indeterminate_tolerance_context_bars: int,
        incompatible_tolerance_context_bars: int,
    ) -> _V04PolicyView: ...


def _locked_v0_4() -> CandidatePolicy:
    constructor = cast(
        Callable[[], CandidatePolicy] | None,
        getattr(CandidatePolicy, "locked_v0_4", None),
    )
    assert constructor is not None, "Candidate v0.4 policy constructor is missing"
    return constructor()


def _adjunct_type() -> object:
    module_name = "gemini_trading.strategy.v0_4_policy"
    assert util.find_spec(module_name) is not None, (
        "Candidate v0.4 adjunct policy module is missing"
    )
    module = import_module(module_name)
    policy_type = getattr(module, "V04MultiTimeframePolicy", None)
    assert policy_type is not None, "Candidate v0.4 adjunct policy type is missing"
    return policy_type


def _locked_adjunct() -> _V04PolicyView:
    locked = cast(Callable[[], _V04PolicyView] | None, getattr(_adjunct_type(), "locked", None))
    assert locked is not None, "Candidate v0.4 adjunct locked constructor is missing"
    return locked()


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


def test_locked_v0_4_multitimeframe_adjunct_is_exact() -> None:
    policy = _locked_adjunct()

    assert policy.schema_version == "candidate-v0.4-multitimeframe-policy-v1"
    assert policy.tactical_timeframe == "1h"
    assert policy.context_timeframe == "4h"
    assert policy.context_feature_names == _CONTEXT_FEATURE_NAMES
    assert policy.entry_percentile == Decimal("0.75")
    assert policy.entry_floor == Decimal("0.50")
    assert policy.minimum_entry_scores == 160
    assert policy.sensitivity_percentiles == (Decimal("0.70"), Decimal("0.80"))
    assert policy.indeterminate_tolerance_context_bars == 1
    assert policy.incompatible_tolerance_context_bars == 2


def test_v0_4_multitimeframe_adjunct_serializes_canonically() -> None:
    module = import_module("gemini_trading.strategy.v0_4_policy")
    serializer = cast(
        Callable[[_V04PolicyView], bytes] | None,
        getattr(module, "serialize_v0_4_multitimeframe_policy", None),
    )
    assert serializer is not None, "Candidate v0.4 adjunct serializer is missing"

    expected = canonical_json_bytes(
        {
            "schema_version": "candidate-v0.4-multitimeframe-policy-v1",
            "tactical_timeframe": "1h",
            "context_timeframe": "4h",
            "context_feature_names": _CONTEXT_FEATURE_NAMES,
            "entry_percentile": Decimal("0.75"),
            "entry_floor": Decimal("0.50"),
            "minimum_entry_scores": 160,
            "sensitivity_percentiles": (Decimal("0.70"), Decimal("0.80")),
            "indeterminate_tolerance_context_bars": 1,
            "incompatible_tolerance_context_bars": 2,
        }
    )
    assert serializer(_locked_adjunct()) == expected


def test_v0_4_multitimeframe_adjunct_rejects_duplicate_context_names() -> None:
    constructor = cast(_V04PolicyConstructor, _adjunct_type())
    with pytest.raises(ValueError, match="context feature"):
        constructor(
            schema_version="candidate-v0.4-multitimeframe-policy-v1",
            tactical_timeframe="1h",
            context_timeframe="4h",
            context_feature_names=(_CONTEXT_FEATURE_NAMES[0], _CONTEXT_FEATURE_NAMES[0]),
            entry_percentile=Decimal("0.75"),
            entry_floor=Decimal("0.50"),
            minimum_entry_scores=160,
            sensitivity_percentiles=(Decimal("0.70"), Decimal("0.80")),
            indeterminate_tolerance_context_bars=1,
            incompatible_tolerance_context_bars=2,
        )
