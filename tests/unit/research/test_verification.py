"""Tests for independent stored backtest evidence verification."""

from pathlib import Path

from gemini_trading.research.verification import ResearchVerificationService
from research_fixture_support import write_completed_fixture_experiment


def test_verification_recomputes_result_and_returns_sorted_checks(tmp_path: Path) -> None:
    recorded_commit = "1" * 40
    experiment_id, artifacts = write_completed_fixture_experiment(
        tmp_path,
        code_commit=recorded_commit,
    )

    verified = ResearchVerificationService(
        tmp_path,
        current_commit_resolver=lambda: recorded_commit,
    ).verify(experiment_id)

    assert verified.experiment_id == experiment_id
    assert verified.result_id == artifacts.result_id
    assert verified.terminal_status == "completed"
    assert verified.promotable is True
    assert verified.checks == tuple(sorted(verified.checks))
    assert {
        "accounting_reconciled",
        "artifact_hashes_verified",
        "dataset_verified",
        "experiment_identity_verified",
        "referential_integrity_verified",
        "replay_equivalent",
        "result_identity_verified",
    }.issubset(set(verified.checks))
