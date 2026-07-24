"""Independent verification coverage for immutable Candidate strategy studies."""

from dataclasses import dataclass
from inspect import signature
from pathlib import Path

import pytest

from gemini_trading.research.replay import ReplayService
from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.strategy.artifacts import LocalStrategyStudyStore, build_study_artifacts
from gemini_trading.strategy.errors import StudyReplayMismatchError
from gemini_trading.strategy.evaluation import MANDATORY_GATE_IDS, PromotionClassification
from gemini_trading.strategy.replay import (
    SUPPORTED_REPLAY_STRATEGY_IDS,
    validate_replay_strategy_id,
)
from gemini_trading.strategy.verification import StrategyStudyVerificationService
from strategy_study_artifact_support import complete_payloads, complete_study_evidence

_CODE_COMMIT = "a" * 40


@dataclass(frozen=True, slots=True)
class _VerifiedExperiment:
    result_id: str


def _payloads_with_exact_gates() -> dict[str, object]:
    payloads = complete_payloads()
    payloads["promotion-gates.json"] = {
        "classification": PromotionClassification.REJECTED.value,
        "gates": [{"gate_id": gate_id} for gate_id in MANDATORY_GATE_IDS],
    }
    return payloads


def test_shared_research_services_accept_strategy_reconstructor() -> None:
    assert "strategy_reconstructor" in signature(ReplayService).parameters
    assert "strategy_reconstructor" in signature(ResearchVerificationService).parameters
    assert (
        "research_strategy_reconstructor" in signature(StrategyStudyVerificationService).parameters
    )


def test_closed_reconstruction_registry_is_exact() -> None:
    assert SUPPORTED_REPLAY_STRATEGY_IDS == (
        "fixture.scripted.v1",
        "candidate.multi_model.v0_1",
        "cash.v1",
        "buy_hold.v1",
        "ema_20_50.v1",
        "donchian_20_10.v1",
        "mean_reversion_z24.v1",
    )
    for strategy_id in SUPPORTED_REPLAY_STRATEGY_IDS:
        assert validate_replay_strategy_id(strategy_id) == strategy_id
    with pytest.raises(StudyReplayMismatchError, match="unsupported replay strategy"):
        validate_replay_strategy_id("unknown.strategy.v1")


def test_strategy_study_verification_returns_safe_complete_checks(tmp_path: Path) -> None:
    evidence = complete_study_evidence()
    artifacts = build_study_artifacts(
        evidence,
        classification=PromotionClassification.REJECTED,
        payloads=_payloads_with_exact_gates(),
        code_commit=_CODE_COMMIT,
    )
    LocalStrategyStudyStore(tmp_path).write(artifacts)
    expected_results = {
        record.experiment_id: record.evidence_sha256
        for record in (*evidence.fold_records, *evidence.final_records)
    }

    result = StrategyStudyVerificationService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
        research_verifier=lambda experiment_id: _VerifiedExperiment(
            result_id=expected_results[experiment_id]
        ),
    ).verify(artifacts.study_id)

    assert result.study_id == artifacts.study_id
    assert result.study_result_id == artifacts.study_result_id
    assert result.classification is PromotionClassification.REJECTED
    assert result.promotable is False
    assert result.checks == tuple(sorted(result.checks))
    assert set(result.checks) == {
        "artifact_hashes_verified",
        "closed_reconstruction_registry_verified",
        "code_commit_verified",
        "final_test_receipt_verified",
        "mandatory_gates_verified",
        "referenced_experiments_verified",
        "replay_equivalent",
        "study_identity_verified",
        "study_result_identity_verified",
    }
