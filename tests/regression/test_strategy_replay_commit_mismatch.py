"""Regression coverage for exact strategy-study code-commit binding."""

from pathlib import Path

import pytest

from gemini_trading.strategy.artifacts import LocalStrategyStudyStore, build_study_artifacts
from gemini_trading.strategy.errors import StudyReplayMismatchError
from gemini_trading.strategy.evaluation import PromotionClassification
from gemini_trading.strategy.replay import StrategyStudyReplayService
from strategy_study_artifact_support import complete_payloads, complete_study_evidence

_RECORDED_COMMIT = "a" * 40
_CURRENT_COMMIT = "b" * 40


def test_strategy_replay_rejects_code_commit_mismatch(tmp_path: Path) -> None:
    artifacts = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=complete_payloads(),
        code_commit=_RECORDED_COMMIT,
    )
    LocalStrategyStudyStore(tmp_path).write(artifacts)

    with pytest.raises(StudyReplayMismatchError, match="code commit"):
        StrategyStudyReplayService(
            root=tmp_path,
            current_commit_resolver=lambda: _CURRENT_COMMIT,
        ).replay(artifacts.study_id)
