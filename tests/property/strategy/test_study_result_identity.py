"""Property tests for content-derived strategy-study result identity."""

from copy import deepcopy

import pytest

from gemini_trading.strategy.artifacts import build_study_artifacts
from gemini_trading.strategy.evaluation import PromotionClassification
from strategy_study_artifact_support import complete_payloads, complete_study_evidence


@pytest.mark.parametrize(
    "artifact_name",
    ("models.jsonl", "predictions.jsonl", "promotion-gates.json"),
)
def test_core_artifact_change_changes_study_result_identity(artifact_name: str) -> None:
    original_payloads = complete_payloads()
    changed_payloads = deepcopy(original_payloads)
    changed_payloads[artifact_name] = [{"changed": True}] if artifact_name.endswith(".jsonl") else {"changed": True}

    original = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=original_payloads,
    )
    changed = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.REJECTED,
        payloads=changed_payloads,
    )

    assert original.study_result_id != changed.study_result_id
