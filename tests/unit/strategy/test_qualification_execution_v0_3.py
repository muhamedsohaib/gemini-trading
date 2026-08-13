"""Candidate v0.3 qualification execution contracts."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from gemini_trading.strategy.entry_selectivity import EntrySelectivityPolicy
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification_execution_v0_3 import (
    V03_INITIAL_CASH,
    V03QualificationRun,
    aggregate_path_metrics,
    locked_v0_3_simulation_config,
    qualification_case_ids,
    validate_v0_3_qualification_parameters,
)
from gemini_trading.strategy.v0_3_cases import V03_QUALIFICATION_CASE_IDS


def test_v0_3_qualification_case_ids_are_exact() -> None:
    policy = CandidatePolicy.locked_v0_3()
    assert qualification_case_ids(policy) == V03_QUALIFICATION_CASE_IDS


def test_v0_3_qualification_binds_separate_selectivity_identity() -> None:
    policy = CandidatePolicy.locked_v0_3()
    selectivity = EntrySelectivityPolicy.locked_v0_3()
    assert policy.strategy_id == "candidate.multi_model.v0_3"
    assert selectivity.primary_percentile == Decimal("0.75")
    assert selectivity.threshold_floor == Decimal("0.50")
    assert selectivity.minimum_eligible_scores == 40
    assert "selectivity_policy_sha256" in V03QualificationRun.__dataclass_fields__
    assert "threshold_artifacts" in V03QualificationRun.__dataclass_fields__
    assert "fold_diagnostics" in V03QualificationRun.__dataclass_fields__
    assert "prospective" not in " ".join(V03QualificationRun.__dataclass_fields__)


def test_v0_3_aggregate_path_metrics_preserve_existing_math() -> None:
    metrics = aggregate_path_metrics((Decimal("0.10"), Decimal("-0.10"), Decimal("0.05")))
    assert metrics.net_return == Decimal("0.0395")
    assert metrics.maximum_drawdown == Decimal("0.10")
    assert metrics.return_to_drawdown == Decimal("0.395")


def test_v0_3_qualification_economics_are_exact_and_fail_closed() -> None:
    simulation = locked_v0_3_simulation_config()
    validate_v0_3_qualification_parameters(simulation, V03_INITIAL_CASH)

    with pytest.raises(StudyArtifactError, match="simulation configuration"):
        validate_v0_3_qualification_parameters(
            replace(simulation, slippage_bps=Decimal("11")),
            V03_INITIAL_CASH,
        )

    with pytest.raises(StudyArtifactError, match="initial cash"):
        validate_v0_3_qualification_parameters(simulation, Decimal("9999"))
