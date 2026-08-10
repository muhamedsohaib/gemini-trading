"""RED tests for immutable Candidate v0.2 qualification evidence."""

from pathlib import Path

import pytest

from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.qualification import QualificationClassification, QualificationReport
from gemini_trading.strategy.qualification_artifacts import (
    LocalQualificationStore,
    QualificationArtifactContext,
    build_qualification_artifacts,
    verify_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution import QualificationRun
from gemini_trading.strategy.evaluation import BootstrapResult
from decimal import Decimal


def _run() -> QualificationRun:
    bootstrap = BootstrapResult(
        seed=1788,
        replicate_count=1000,
        block_length=42,
        sampled_start_matrix_sha256="a" * 64,
        net_return_difference_median=Decimal("0.01"),
        net_return_difference_p05=Decimal("-0.01"),
        net_return_difference_p95=Decimal("0.03"),
        drawdown_difference_median=Decimal("0"),
        drawdown_difference_p05=Decimal("-0.02"),
        drawdown_difference_p95=Decimal("0.02"),
        return_to_drawdown_difference_median=Decimal("0.1"),
        return_to_drawdown_difference_p05=Decimal("-0.01"),
        return_to_drawdown_difference_p95=Decimal("0.2"),
    )
    return QualificationRun(
        policy_sha256="b" * 64,
        configuration_sha256="c" * 64,
        development_plan_sha256="d" * 64,
        report=QualificationReport(
            classification=QualificationClassification.QUALIFIED,
            gates=(),
        ),
        bootstrap=bootstrap,
        determinism_receipts=(),
        case_evidence=(),
    )


def _context() -> QualificationArtifactContext:
    return QualificationArtifactContext(
        code_commit="1" * 40,
        dataset_id="2" * 64,
        dataset_handoff_inventory_root="3" * 64,
        dataset_run_id=123,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )


def test_qualification_artifacts_round_trip_provider_free(tmp_path: Path) -> None:
    artifacts = build_qualification_artifacts(_run(), _context())
    store = LocalQualificationStore(tmp_path)

    store.write(artifacts)
    verified = verify_qualification_artifacts(tmp_path, artifacts.qualification_id)

    assert verified == artifacts
    assert verified.classification is QualificationClassification.QUALIFIED
    assert len(verified.qualification_id) == 64
    assert len(verified.inventory_root_sha256) == 64


def test_qualification_artifacts_reject_tampering(tmp_path: Path) -> None:
    artifacts = build_qualification_artifacts(_run(), _context())
    store = LocalQualificationStore(tmp_path)
    store.write(artifacts)
    target = (
        tmp_path
        / "data"
        / "historical-validation"
        / "v0-2-qualification"
        / artifacts.qualification_id
        / "bootstrap.json"
    )
    target.write_bytes(b"{}\n")

    with pytest.raises(StudyArtifactError, match="qualification artifact"):
        verify_qualification_artifacts(tmp_path, artifacts.qualification_id)
