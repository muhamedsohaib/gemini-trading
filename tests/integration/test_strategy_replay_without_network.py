"""Offline replay coverage for immutable Candidate strategy studies."""

import socket
import urllib.request
from pathlib import Path
from typing import NoReturn

from _pytest.monkeypatch import MonkeyPatch

from gemini_trading.strategy.artifacts import LocalStrategyStudyStore, build_study_artifacts
from gemini_trading.strategy.evaluation import PromotionClassification
from gemini_trading.strategy.replay import StrategyStudyReplayService
from strategy_study_artifact_support import complete_payloads, complete_study_evidence

_CODE_COMMIT = "a" * 40


def _forbid_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("strategy-study replay attempted network access")


def test_strategy_study_replays_without_network(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    artifacts = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=complete_payloads(),
        code_commit=_CODE_COMMIT,
    )
    LocalStrategyStudyStore(tmp_path).write(artifacts)
    monkeypatch.setattr(socket, "socket", _forbid_network)
    monkeypatch.setattr(socket, "create_connection", _forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid_network)

    replayed = StrategyStudyReplayService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
    ).replay(artifacts.study_id)

    assert replayed.study_result_id == artifacts.study_result_id
    assert replayed.files == artifacts.files
