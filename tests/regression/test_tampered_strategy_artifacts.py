"""Regression tests for incomplete and tampered strategy-study artifacts."""

from dataclasses import replace

import pytest

from gemini_trading.strategy.artifacts import build_study_artifacts
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import PromotionClassification
from strategy_study_artifact_support import complete_payloads, complete_study_evidence


def test_missing_fold_case_prevents_artifact_construction() -> None:
    evidence = complete_study_evidence()
    incomplete = replace(evidence, fold_records=evidence.fold_records[:-1])

    with pytest.raises(StudyArtifactError, match="incomplete development evidence"):
        build_study_artifacts(
            incomplete,
            classification=PromotionClassification.REJECTED,
            payloads=complete_payloads(),
        )


def test_missing_final_case_prevents_artifact_construction() -> None:
    evidence = complete_study_evidence()
    incomplete = replace(evidence, final_records=evidence.final_records[:-1])

    with pytest.raises(StudyArtifactError, match="incomplete final evidence"):
        build_study_artifacts(
            incomplete,
            classification=PromotionClassification.REJECTED,
            payloads=complete_payloads(),
        )
