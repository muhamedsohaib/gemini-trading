"""Tests for canonical immutable Candidate study artifacts."""

import json
from pathlib import Path

import pytest

from gemini_trading.strategy.artifacts import (
    REQUIRED_STUDY_ARTIFACT_NAMES,
    LocalStrategyStudyStore,
    build_study_artifacts,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import PromotionClassification
from strategy_study_artifact_support import complete_payloads, complete_study_evidence


def test_required_files_and_identity_are_exact_and_deterministic() -> None:
    first = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=complete_payloads(),
    )
    second = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=complete_payloads(),
    )

    assert first == second
    assert first.names == REQUIRED_STUDY_ARTIFACT_NAMES
    assert len(first.study_result_id) == 64
    result = json.loads(first.artifact_bytes("study-result-manifest.json"))
    assert result["schema_version"] == "strategy-study-result-v1"
    assert result["study_id"] == first.study_id
    assert result["study_result_id"] == first.study_result_id
    assert result["classification"] == "REJECTED"
    assert "study-result-manifest.json" not in {item[0] for item in result["artifacts"]}


def test_local_store_accepts_identical_rerun_and_rejects_conflict(tmp_path: Path) -> None:
    artifacts = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=complete_payloads(),
    )
    store = LocalStrategyStudyStore(tmp_path)

    assert store.write(artifacts) == store.write(artifacts)
    model_path = (
        tmp_path
        / "data"
        / "strategy-studies"
        / artifacts.study_id
        / "models.jsonl"
    )
    model_path.write_bytes(b"{}\n")

    with pytest.raises(StudyArtifactError, match="models.jsonl"):
        store.write(artifacts)


def test_missing_required_payload_fails_closed() -> None:
    payloads = complete_payloads()
    del payloads["negative-controls.json"]

    with pytest.raises(StudyArtifactError, match="required study payloads"):
        build_study_artifacts(
            complete_study_evidence(),
            classification=PromotionClassification.REJECTED,
            payloads=payloads,
        )
