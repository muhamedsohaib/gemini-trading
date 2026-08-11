"""Tests for immutable Candidate v0.2 qualification evidence."""

import hashlib
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import BootstrapResult
from gemini_trading.strategy.qualification import QualificationClassification, QualificationReport
from gemini_trading.strategy.qualification_artifacts import (
    LocalQualificationStore,
    QualificationArtifactContext,
    build_qualification_artifacts,
    verify_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution import QualificationRun


def _bootstrap(*, median: str = "0.01") -> BootstrapResult:
    return BootstrapResult(
        seed=1788,
        replicate_count=1000,
        block_length=42,
        sampled_start_matrix_sha256="a" * 64,
        net_return_difference_median=Decimal(median),
        net_return_difference_p05=Decimal("-0.01"),
        net_return_difference_p95=Decimal("0.03"),
        drawdown_difference_median=Decimal("0"),
        drawdown_difference_p05=Decimal("-0.02"),
        drawdown_difference_p95=Decimal("0.02"),
        return_to_drawdown_difference_median=Decimal("0.1"),
        return_to_drawdown_difference_p05=Decimal("-0.01"),
        return_to_drawdown_difference_p95=Decimal("0.2"),
    )


def _run() -> QualificationRun:
    policy_bytes = canonical_json_bytes({"strategy_id": "candidate.multi_model.v0_2"})
    configuration_bytes = canonical_json_bytes({"initial_cash": "10000"})
    development_plan_bytes = canonical_json_bytes({"folds": 12})
    return QualificationRun(
        policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        development_plan_sha256=hashlib.sha256(development_plan_bytes).hexdigest(),
        policy_bytes=policy_bytes,
        configuration_bytes=configuration_bytes,
        development_plan_bytes=development_plan_bytes,
        report=QualificationReport(
            classification=QualificationClassification.QUALIFIED,
            gates=(),
        ),
        bootstrap=_bootstrap(),
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
    assert {name for name, _ in verified.files} >= {
        "policy.json",
        "configuration.json",
        "development-plan.json",
    }


def test_qualification_id_binds_core_evidence_bytes() -> None:
    first = build_qualification_artifacts(_run(), _context())
    changed = replace(_run(), bootstrap=_bootstrap(median="0.02"))
    second = build_qualification_artifacts(changed, _context())

    assert first.qualification_id != second.qualification_id
    assert first.inventory_root_sha256 != second.inventory_root_sha256


def test_qualification_artifacts_reject_tampering(tmp_path: Path) -> None:
    artifacts = build_qualification_artifacts(_run(), _context())
    store = LocalQualificationStore(tmp_path)
    store.write(artifacts)
    target = store.directory(artifacts.qualification_id) / "bootstrap.json"
    target.write_bytes(b"{}\n")

    with pytest.raises(StudyArtifactError, match="qualification artifact"):
        verify_qualification_artifacts(tmp_path, artifacts.qualification_id)


def test_qualification_artifacts_reject_policy_identity_mismatch() -> None:
    run = replace(_run(), policy_sha256="f" * 64)

    with pytest.raises(StudyArtifactError, match="policy identity"):
        build_qualification_artifacts(run, _context())
