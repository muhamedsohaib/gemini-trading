"""Bounded integration contracts for Candidate v0.3 qualification."""

from __future__ import annotations

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification_execution_v0_3 import qualification_case_ids
from gemini_trading.strategy.qualification_v0_3 import V03_QUALIFICATION_GATE_IDS
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
