"""Integration tests for provider-free deterministic backtest replay."""

import socket
from pathlib import Path

import pytest

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.replay import ReplayService
from research_fixture_support import write_completed_fixture_experiment


def _fail_if_called(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("network access is forbidden during replay")


def test_replay_uses_no_network_and_reproduces_all_core_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_commit = "1" * 40
    experiment_id, recorded = write_completed_fixture_experiment(
        tmp_path,
        code_commit=recorded_commit,
    )
    monkeypatch.setattr(socket, "create_connection", _fail_if_called)

    replayed = ReplayService(
        LocalImmutableStore(tmp_path),
        LocalResearchStore(tmp_path),
        current_commit_resolver=lambda: recorded_commit,
    ).replay(experiment_id)

    assert replayed.experiment_id == experiment_id
    assert replayed.result_id == recorded.result_id
    assert replayed.files == recorded.files
