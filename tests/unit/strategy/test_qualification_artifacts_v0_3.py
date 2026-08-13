"""RED contracts for immutable Candidate v0.3 qualification artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.entry_selectivity import EntryThresholdArtifact
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import BootstrapResult
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_artifacts_v0_3 import (
    V03LocalQualificationStore,
    V03QualificationArtifactContext,
    build_v0_3_qualification_artifacts,
    verify_v0_3_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution_v0_3 import V03QualificationRun
from gemini_trading.strategy.qualification_v0_3 import V03QualificationReport
from gemini_trading.strategy.v0_3_cases import V03FoldDiagnostics


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


def _threshold(percentile: str = "0.75") -> EntryThresholdArtifact:
    scores = tuple(Decimal("0.60") + Decimal(index) / Decimal("1000") for index in range(40))
    indices = tuple(range(40))
    return EntryThresholdArtifact(
        schema_version="candidate-v0.3-entry-threshold-v1",
        fold_number=1,
        specialist=SpecialistKind.TREND,
        percentile=Decimal(percentile),
        eligible_indices=indices,
        eligible_scores=scores,
        eligible_rows_sha256=hashlib.sha256(
            canonical_json_bytes(
                {
                    "schema_version": "candidate-v0.3-entry-eligible-rows-v1",
                    "fold_number": 1,
                    "specialist": "trend",
                    "eligible_indices": indices,
                }
            )
        ).hexdigest(),
        score_vector_sha256=hashlib.sha256(
            canonical_json_bytes(
                {
                    "schema_version": "candidate-v0.3-entry-score-vector-v1",
                    "fold_number": 1,
                    "specialist": "trend",
                    "eligible_indices": indices,
                    "eligible_scores": scores,
                }
            )
        ).hexdigest(),
        raw_quantile=Decimal("0.62925"),
        effective_threshold=Decimal("0.62925"),
        quantile_method="linear_n_minus_one",
    )


def _diagnostics() -> V03FoldDiagnostics:
    return V03FoldDiagnostics(
        schema_version="candidate-v0.3-fold-diagnostics-v1",
        fold_number=1,
        decision_indices=(10,),
        companion_indices=(10,),
        companion_probabilities=(Decimal("0.4"),),
        disagreement_indices=(10,),
        absolute_disagreements=(Decimal("0.2"),),
        companion_distribution_sha256="b" * 64,
        disagreement_distribution_sha256="c" * 64,
    )


def _run() -> V03QualificationRun:
    policy = canonical_json_bytes({"strategy_id": "candidate.multi_model.v0_3"})
    selectivity = canonical_json_bytes({"primary_percentile": "0.75"})
    config = canonical_json_bytes({"dataset_id": "2" * 64})
    plan = canonical_json_bytes({"folds": 12})
    return V03QualificationRun(
        policy_sha256=hashlib.sha256(policy).hexdigest(),
        selectivity_policy_sha256=hashlib.sha256(selectivity).hexdigest(),
        configuration_sha256=hashlib.sha256(config).hexdigest(),
        development_plan_sha256=hashlib.sha256(plan).hexdigest(),
        policy_bytes=policy,
        selectivity_policy_bytes=selectivity,
        configuration_bytes=config,
        development_plan_bytes=plan,
        report=V03QualificationReport(
            classification=QualificationClassification.QUALIFIED,
            gates=(),
        ),
        bootstrap=_bootstrap(),
        determinism_receipts=(),
        calibration_diagnostics=(),
        threshold_artifacts=(_threshold(),),
        fold_diagnostics=(_diagnostics(),),
        case_evidence=(),
    )


def _context() -> V03QualificationArtifactContext:
    return V03QualificationArtifactContext(
        code_commit="1" * 40,
        dataset_id="2" * 64,
        dataset_handoff_inventory_root="3" * 64,
        dataset_run_id=123,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )


def test_v0_3_artifacts_round_trip_and_bind_selectivity(tmp_path: Path) -> None:
    artifacts = build_v0_3_qualification_artifacts(_run(), _context())
    V03LocalQualificationStore(tmp_path).write(artifacts)
    verified = verify_v0_3_qualification_artifacts(tmp_path, artifacts.qualification_id)
    assert verified == artifacts
    assert {name for name, _ in verified.files} >= {
        "policy.json",
        "entry-selectivity-policy.json",
        "entry-thresholds.jsonl",
        "fold-diagnostics.jsonl",
        "qualification-result.json",
    }


def test_v0_3_artifacts_reject_threshold_tampering(tmp_path: Path) -> None:
    artifacts = build_v0_3_qualification_artifacts(_run(), _context())
    store = V03LocalQualificationStore(tmp_path)
    store.write(artifacts)
    target = store.directory(artifacts.qualification_id) / "entry-thresholds.jsonl"
    target.write_bytes(b"{}\n")
    with pytest.raises(StudyArtifactError, match="qualification artifact"):
        verify_v0_3_qualification_artifacts(tmp_path, artifacts.qualification_id)


def test_v0_3_artifacts_reject_noncanonical_result_tampering(tmp_path: Path) -> None:
    artifacts = build_v0_3_qualification_artifacts(_run(), _context())
    store = V03LocalQualificationStore(tmp_path)
    store.write(artifacts)
    target = store.directory(artifacts.qualification_id) / "qualification-result.json"
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(StudyArtifactError, match="result canonical bytes changed"):
        verify_v0_3_qualification_artifacts(tmp_path, artifacts.qualification_id)


def test_v0_3_qualification_id_changes_with_selectivity_bytes() -> None:
    first = build_v0_3_qualification_artifacts(_run(), _context())
    changed_bytes = canonical_json_bytes({"primary_percentile": "0.80"})
    changed = replace(
        _run(),
        selectivity_policy_bytes=changed_bytes,
        selectivity_policy_sha256=hashlib.sha256(changed_bytes).hexdigest(),
    )
    second = build_v0_3_qualification_artifacts(changed, _context())
    assert first.qualification_id != second.qualification_id
