"""Tests for portable provider-free Candidate v0.2 qualification verification."""

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.calibration_evidence import CalibrationDiagnostic
from gemini_trading.strategy.evaluation import BootstrapResult
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification import QualificationClassification, QualificationReport
from gemini_trading.strategy.qualification_artifacts import (
    LocalQualificationStore,
    QualificationArtifactContext,
    build_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution import (
    QualificationRun,
    qualification_case_ids,
)
from gemini_trading.strategy.qualification_verification import verify_qualification_bundle
from gemini_trading.strategy.study import StudyCaseEvidence, StudyPhase

_CODE_COMMIT = "1" * 40
_DATASET_ID = "2" * 64
_HANDOFF_ROOT = "3" * 64


@dataclass(frozen=True, slots=True)
class _VerifiedExperiment:
    experiment_id: str
    result_id: str
    terminal_status: str = "completed"


@dataclass(frozen=True, slots=True)
class _Handoff:
    inventory_root_sha256: str = _HANDOFF_ROOT


def _bootstrap() -> BootstrapResult:
    return BootstrapResult(
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


def _diagnostics() -> tuple[CalibrationDiagnostic, ...]:
    return tuple(
        CalibrationDiagnostic(
            schema_version="candidate-v0.2-calibration-diagnostic-v1",
            fold_number=fold_number,
            specialist=specialist,
            calibration_rows_sha256="a" * 64,
            platt_schema_version="candidate-platt-v1",
            platt_slope_hex=(1.0).hex(),
            platt_intercept_hex=(0.0).hex(),
            platt_minimum_probability_hex=(0.1).hex(),
            platt_maximum_probability_hex=(0.9).hex(),
            observation_count=320,
            positive_count=128,
            negative_count=192,
            return_map_schema_version="candidate-expected-return-map-v1",
            return_map_intercept=Decimal("0"),
            return_map_slope=Decimal("0.01"),
            return_map_minimum_probability=Decimal("0.1"),
            return_map_maximum_probability=Decimal("0.9"),
            return_map_observation_count=320,
            brier_score=Decimal("0.20"),
            log_loss=Decimal("0.60"),
            expected_calibration_error=Decimal("0.05"),
        )
        for fold_number in range(1, 13)
        for specialist in ("trend", "mean_reversion")
    )


def _run() -> QualificationRun:
    records = tuple(
        StudyCaseEvidence(
            case_id=case_id,
            phase=StudyPhase.DEVELOPMENT,
            fold_number=fold_number,
            terminal_status="completed",
            experiment_id=hashlib.sha256(
                f"experiment:{fold_number}:{case_id}".encode()
            ).hexdigest(),
            evidence_sha256=hashlib.sha256(f"result:{fold_number}:{case_id}".encode()).hexdigest(),
        )
        for fold_number in range(1, 13)
        for case_id in qualification_case_ids(CandidatePolicy.locked_v0_2())
    )
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
        calibration_diagnostics=_diagnostics(),
        case_evidence=records,
    )


def test_portable_verification_rechecks_handoff_and_every_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run()
    context = QualificationArtifactContext(
        code_commit=_CODE_COMMIT,
        dataset_id=_DATASET_ID,
        dataset_handoff_inventory_root=_HANDOFF_ROOT,
        dataset_run_id=123,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )
    artifacts = build_qualification_artifacts(run, context)
    LocalQualificationStore(tmp_path).write(artifacts)
    handoff_path = (
        tmp_path
        / "data"
        / "historical-validation"
        / "handoff"
        / _DATASET_ID
        / "dataset-handoff.json"
    )
    handoff_path.parent.mkdir(parents=True)
    handoff_path.write_bytes(b"fixture")

    import gemini_trading.strategy.qualification_verification as module

    def fake_load_dataset_handoff(raw: bytes) -> _Handoff:
        assert raw == b"fixture"
        return _Handoff()

    monkeypatch.setattr(module, "load_dataset_handoff", fake_load_dataset_handoff)
    handoff_calls: list[tuple[str, str, int]] = []

    def fake_handoff_verify(
        handoff: object,
        root: Path,
        *,
        expected_commit: str,
        expected_dataset_id: str,
        expected_run_id: int,
    ) -> None:
        handoff_calls.append((expected_commit, expected_dataset_id, expected_run_id))

    monkeypatch.setattr(module, "verify_dataset_handoff", fake_handoff_verify)
    expected = {record.experiment_id: record.evidence_sha256 for record in run.case_evidence}
    observed: list[str] = []

    def fake_verify(self: object, experiment_id: str) -> _VerifiedExperiment:
        observed.append(experiment_id)
        return _VerifiedExperiment(experiment_id=experiment_id, result_id=expected[experiment_id])

    monkeypatch.setattr(module.ResearchVerificationService, "verify", fake_verify)

    verified = verify_qualification_bundle(
        tmp_path,
        artifacts.qualification_id,
        expected_commit=_CODE_COMMIT,
    )

    assert verified == artifacts
    assert handoff_calls == [(_CODE_COMMIT, _DATASET_ID, 123)]
    assert observed == [record.experiment_id for record in run.case_evidence]
