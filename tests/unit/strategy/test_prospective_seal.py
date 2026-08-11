"""Tests for Candidate v0.2 prospective final seal."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.prospective_seal import (
    LocalProspectiveFinalSealStore,
    ProspectiveFinalSealRequest,
)
from gemini_trading.strategy.qualification import QualificationClassification


def _request(classification: QualificationClassification) -> ProspectiveFinalSealRequest:
    return ProspectiveFinalSealRequest(
        code_commit="1" * 40,
        dataset_id="2" * 64,
        dataset_handoff_inventory_root="3" * 64,
        qualification_id="4" * 64,
        qualification_inventory_root="5" * 64,
        qualification_classification=classification,
        workflow_run_id=456,
        workflow_run_attempt=1,
        verified_at=datetime(2026, 8, 10, 16, 0, tzinfo=UTC),
        development_cutoff=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_qualified_evidence_creates_exactly_one_future_seal(tmp_path: Path) -> None:
    store = LocalProspectiveFinalSealStore(tmp_path)

    seal = store.create(_request(QualificationClassification.QUALIFIED))
    loaded = store.load(seal.seal_id)

    assert loaded == seal
    assert seal.strategy_id == "candidate.multi_model.v0_2"
    assert seal.policy_version == "candidate-multi-model-v0.2"
    assert seal.final_start == datetime(2026, 9, 1, tzinfo=UTC)
    assert seal.final_end == datetime(2028, 3, 1, tzinfo=UTC)
    assert seal.bridge_start == datetime(2026, 7, 1, tzinfo=UTC)
    assert seal.bridge_end == seal.final_start
    with pytest.raises(FinalAccessError, match="prospective final seal already exists"):
        store.create(_request(QualificationClassification.QUALIFIED))


@pytest.mark.parametrize(
    "classification",
    [QualificationClassification.REJECTED, QualificationClassification.INCONCLUSIVE],
)
def test_nonqualified_evidence_cannot_create_future_seal(
    tmp_path: Path,
    classification: QualificationClassification,
) -> None:
    with pytest.raises(FinalAccessError, match="QUALIFIED"):
        LocalProspectiveFinalSealStore(tmp_path).create(_request(classification))
