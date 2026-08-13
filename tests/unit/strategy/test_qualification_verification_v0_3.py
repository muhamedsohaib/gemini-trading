"""Contracts for provider-free Candidate v0.3 qualification verification."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest

from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.entry_selectivity import EntryThresholdArtifact
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.qualification_replay_v0_3 import parse_simulation_config
from gemini_trading.strategy.qualification_verification_v0_3 import (
    replay_entry_threshold_artifact,
)


def _artifact() -> EntryThresholdArtifact:
    indices = tuple(range(40))
    scores = tuple(Decimal("0.50") + Decimal(index) / Decimal("100") for index in range(40))
    rows = {
        "schema_version": "candidate-v0.3-entry-eligible-rows-v1",
        "fold_number": 1,
        "specialist": "trend",
        "eligible_indices": indices,
    }
    vector = {
        "schema_version": "candidate-v0.3-entry-score-vector-v1",
        "fold_number": 1,
        "specialist": "trend",
        "eligible_indices": indices,
        "eligible_scores": scores,
    }
    return EntryThresholdArtifact(
        schema_version="candidate-v0.3-entry-threshold-v1",
        fold_number=1,
        specialist=SpecialistKind.TREND,
        percentile=Decimal("0.75"),
        eligible_indices=indices,
        eligible_scores=scores,
        eligible_rows_sha256=hashlib.sha256(canonical_json_bytes(rows)).hexdigest(),
        score_vector_sha256=hashlib.sha256(canonical_json_bytes(vector)).hexdigest(),
        raw_quantile=Decimal("0.7925"),
        effective_threshold=Decimal("0.7925"),
        quantile_method="linear_n_minus_one",
    )


def test_threshold_replay_recomputes_every_identity() -> None:
    receipt = replay_entry_threshold_artifact(_artifact())
    assert receipt.exact_match is True


def test_threshold_replay_rejects_quantile_tampering() -> None:
    bad = replace(_artifact(), raw_quantile=Decimal("0.70"), effective_threshold=Decimal("0.70"))
    receipt = replay_entry_threshold_artifact(bad)
    assert receipt.raw_quantile_match is False
    assert receipt.exact_match is False


def test_threshold_replay_rejects_unregistered_percentile() -> None:
    with pytest.raises((ValueError, StudyArtifactError)):
        replay_entry_threshold_artifact(replace(_artifact(), percentile=Decimal("0.65")))


def test_simulation_config_replay_is_exact() -> None:
    simulation = SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.000001"),
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        max_volume_participation=Decimal("0.01"),
    )
    raw = serialize_simulation_config(simulation)
    assert parse_simulation_config(raw) == simulation
