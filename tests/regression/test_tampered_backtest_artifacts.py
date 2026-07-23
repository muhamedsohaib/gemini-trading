"""Regression guards for tampered deterministic backtest evidence."""

from pathlib import Path

import pytest

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.errors import ReplayMismatchError
from gemini_trading.research.replay import ReplayService
from gemini_trading.research.verification import ResearchVerificationService
from research_fixture_support import write_completed_fixture_experiment


def test_verification_rejects_modified_fill_ledger(tmp_path: Path) -> None:
    recorded_commit = "1" * 40
    experiment_id, _ = write_completed_fixture_experiment(
        tmp_path,
        code_commit=recorded_commit,
    )
    path = tmp_path / "data" / "research" / experiment_id / "fills.jsonl"
    path.write_bytes(path.read_bytes() + b"{}\n")

    with pytest.raises(ReplayMismatchError, match="fills"):
        ResearchVerificationService(
            tmp_path,
            current_commit_resolver=lambda: recorded_commit,
        ).verify(experiment_id)


def test_replay_rejects_modified_simulation_configuration(tmp_path: Path) -> None:
    recorded_commit = "1" * 40
    experiment_id, _ = write_completed_fixture_experiment(
        tmp_path,
        code_commit=recorded_commit,
    )
    path = tmp_path / "data" / "research" / experiment_id / "simulation-config.json"
    path.write_bytes(path.read_bytes().replace(b'"0.001"', b'"0.002"', 1))

    with pytest.raises(ReplayMismatchError, match="simulation configuration"):
        ReplayService(
            LocalImmutableStore(tmp_path),
            LocalResearchStore(tmp_path),
            current_commit_resolver=lambda: recorded_commit,
        ).replay(experiment_id)


def test_replay_rejects_code_commit_mismatch(tmp_path: Path) -> None:
    experiment_id, _ = write_completed_fixture_experiment(
        tmp_path,
        code_commit="1" * 40,
    )

    with pytest.raises(ReplayMismatchError, match="code commit"):
        ReplayService(
            LocalImmutableStore(tmp_path),
            LocalResearchStore(tmp_path),
            current_commit_resolver=lambda: "2" * 40,
        ).replay(experiment_id)
