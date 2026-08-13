"""Bounded integration contracts for Candidate v0.3 qualification."""

from __future__ import annotations

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_execution_v0_3 import qualification_case_ids
from gemini_trading.strategy.qualification_v0_3 import (
    V03_QUALIFICATION_GATE_IDS,
    V03QualificationEvidence,
    evaluate_v0_3_development_qualification,
)
from gemini_trading.strategy.v0_3_cases import V03_QUALIFICATION_CASE_IDS


def test_v0_3_qualification_inventory_is_development_only_and_complete() -> None:
    case_ids = qualification_case_ids(CandidatePolicy.locked_v0_3())
    assert case_ids == V03_QUALIFICATION_CASE_IDS
    assert "candidate.multi_model.v0_3" in case_ids
    assert "sensitivity.entry_percentile_0_70" in case_ids
    assert "sensitivity.entry_percentile_0_80" in case_ids
    assert "ablation.no_percentile_selectivity.v1" in case_ids
    assert "bootstrap.seed_1788" in case_ids
    assert all("final" not in gate_id for gate_id in V03_QUALIFICATION_GATE_IDS)


def test_explicit_mandatory_gate_failure_is_terminal_rejected_not_inconclusive() -> None:
    evidence = V03QualificationEvidence(
        integrity_verified=False,
        trend_determinism=None,
        calibration_complete=None,
        selectivity_replay=None,
        development_folds=(),
        shuffled_labels_safe=None,
        delayed_features_component_supported=None,
        primary_return_to_drawdown=None,
        primary_aggregate_net_return=None,
        primary_aggregate_max_drawdown=None,
        no_percentile_selectivity_return_to_drawdown=None,
        no_percentile_selectivity_max_drawdown=None,
        volume_component_supported=None,
        protection_component_supported=None,
        cost_1_5x=None,
        cost_2x=None,
        neighbors=None,
        bootstrap=None,
        replay_verified=None,
        independent_verified=None,
    )
    report = evaluate_v0_3_development_qualification(evidence)

    assert report.classification is QualificationClassification.REJECTED
    integrity = next(gate for gate in report.gates if gate.gate_id == "integrity.verified")
    assert integrity.passed is False
    assert integrity.observed == "False"
