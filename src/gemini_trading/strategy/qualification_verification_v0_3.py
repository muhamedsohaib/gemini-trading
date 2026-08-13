"""Independent provider-free verification for Candidate v0.3 qualification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.entry_selectivity import (
    EntrySelectivityPolicy,
    EntryThresholdArtifact,
    linear_quantile,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.qualification_artifacts_v0_3 import (
    V03QualificationArtifacts,
    parse_entry_threshold_artifacts,
    parse_fold_diagnostics,
    verify_v0_3_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution_v0_3 import qualification_case_ids
from gemini_trading.strategy.qualification_v0_3 import (
    V03_QUALIFICATION_GATE_IDS,
    SelectivityReplayReceipt,
)
from gemini_trading.strategy.study import StudyCaseEvidence, StudyPhase

_CASE_KEYS = {
    "case_id",
    "phase",
    "fold_number",
    "terminal_status",
    "experiment_id",
    "evidence_sha256",
}


def _sha(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def replay_entry_threshold_artifact(
    artifact: EntryThresholdArtifact,
) -> SelectivityReplayReceipt:
    """Recompute one persisted threshold from its portable eligible calibration evidence."""

    selectivity = EntrySelectivityPolicy.locked_v0_3()
    allowed = {selectivity.primary_percentile, *selectivity.sensitivity_percentiles}
    if artifact.percentile not in allowed:
        raise StudyArtifactError("v0.3 threshold replay percentile is not preregistered")
    rows_sha = _sha(
        {
            "schema_version": "candidate-v0.3-entry-eligible-rows-v1",
            "fold_number": artifact.fold_number,
            "specialist": artifact.specialist.value,
            "eligible_indices": artifact.eligible_indices,
        }
    )
    vector_sha = _sha(
        {
            "schema_version": "candidate-v0.3-entry-score-vector-v1",
            "fold_number": artifact.fold_number,
            "specialist": artifact.specialist.value,
            "eligible_indices": artifact.eligible_indices,
            "eligible_scores": artifact.eligible_scores,
        }
    )
    raw_quantile = linear_quantile(artifact.eligible_scores, artifact.percentile)
    effective_threshold = max(raw_quantile, selectivity.threshold_floor)
    rebuilt = EntryThresholdArtifact(
        schema_version=artifact.schema_version,
        fold_number=artifact.fold_number,
        specialist=artifact.specialist,
        percentile=artifact.percentile,
        eligible_indices=artifact.eligible_indices,
        eligible_scores=artifact.eligible_scores,
        eligible_rows_sha256=rows_sha,
        score_vector_sha256=vector_sha,
        raw_quantile=raw_quantile,
        effective_threshold=effective_threshold,
        quantile_method="linear_n_minus_one",
    )
    return SelectivityReplayReceipt(
        fold_number=artifact.fold_number,
        specialist=artifact.specialist,
        percentile=artifact.percentile,
        eligible_rows_match=rows_sha == artifact.eligible_rows_sha256,
        score_vector_match=vector_sha == artifact.score_vector_sha256,
        raw_quantile_match=raw_quantile == artifact.raw_quantile,
        effective_threshold_match=effective_threshold == artifact.effective_threshold,
        canonical_bytes_match=canonical_json_bytes(asdict(rebuilt))
        == canonical_json_bytes(asdict(artifact)),
    )


def _case_records(raw: bytes) -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError("v0.3 qualification case evidence is not UTF-8") from None
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError("v0.3 qualification case evidence JSON is invalid") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError("v0.3 qualification case evidence row is invalid")
        mapping = cast(dict[str, object], loaded)
        if set(mapping) != _CASE_KEYS:
            raise StudyArtifactError("v0.3 qualification case evidence fields changed")
        try:
            record = StudyCaseEvidence(
                case_id=cast(str, mapping["case_id"]),
                phase=StudyPhase(cast(str, mapping["phase"])),
                fold_number=cast(int, mapping["fold_number"]),
                terminal_status=cast(str, mapping["terminal_status"]),
                experiment_id=cast(str, mapping["experiment_id"]),
                evidence_sha256=cast(str, mapping["evidence_sha256"]),
            )
        except (KeyError, ValueError, TypeError):
            raise StudyArtifactError("v0.3 qualification case evidence is invalid") from None
        if record.phase is not StudyPhase.DEVELOPMENT or record.terminal_status != "completed":
            raise StudyArtifactError(
                "v0.3 qualification case is not completed development evidence"
            )
        records.append(record)
    expected_cases = qualification_case_ids(CandidatePolicy.locked_v0_3())
    expected = {(fold, case_id) for fold in range(1, 13) for case_id in expected_cases}
    observed = {(record.fold_number, record.case_id) for record in records}
    if observed != expected or len(records) != len(expected):
        raise StudyArtifactError("v0.3 qualification case evidence set is incomplete")
    return tuple(records)


def _verify_locked_identities(mapping: dict[str, bytes]) -> None:
    expected_policy = serialize_candidate_policy(CandidatePolicy.locked_v0_3())
    if mapping["policy.json"] != expected_policy:
        raise StudyArtifactError("v0.3 qualification policy is not the locked candidate")
    expected_selectivity = canonical_json_bytes(asdict(EntrySelectivityPolicy.locked_v0_3()))
    if mapping["entry-selectivity-policy.json"] != expected_selectivity:
        raise StudyArtifactError("v0.3 qualification selectivity policy changed")
    try:
        config_obj: object = json.loads(mapping["configuration.json"])
    except json.JSONDecodeError:
        raise StudyArtifactError("v0.3 qualification configuration is invalid") from None
    if not isinstance(config_obj, dict):
        raise StudyArtifactError("v0.3 qualification configuration is invalid")
    config = cast(dict[str, object], config_obj)
    if (
        config.get("schema_version") != "candidate-v0.3-qualification-config-v1"
        or config.get("development_start") != "2018-01-01T00:00:00Z"
        or config.get("development_end_exclusive") != "2026-08-01T00:00:00Z"
        or config.get("strategy_id") != "candidate.multi_model.v0_3"
        or config.get("policy_version") != "candidate-multi-model-v0.3"
    ):
        raise StudyArtifactError("v0.3 qualification configuration boundary changed")
    expected_selectivity_sha = hashlib.sha256(expected_selectivity).hexdigest()
    if config.get("selectivity_policy_sha256") != expected_selectivity_sha:
        raise StudyArtifactError("v0.3 qualification selectivity identity is not bound")


def _verify_report(mapping: dict[str, bytes], artifacts: V03QualificationArtifacts) -> None:
    try:
        report_obj: object = json.loads(mapping["qualification-report.json"])
    except json.JSONDecodeError:
        raise StudyArtifactError("v0.3 qualification report is invalid") from None
    if not isinstance(report_obj, dict):
        raise StudyArtifactError("v0.3 qualification report is invalid")
    report = cast(dict[str, object], report_obj)
    gate_ids = report.get("gate_ids")
    if gate_ids != list(V03_QUALIFICATION_GATE_IDS):
        raise StudyArtifactError("v0.3 qualification gate inventory changed")
    if report.get("classification") != artifacts.classification.value:
        raise StudyArtifactError("v0.3 qualification report classification changed")


def verify_candidate_v0_3_qualification(
    root: Path,
    qualification_id: str,
    *,
    expected_commit: str,
) -> V03QualificationArtifacts:
    """Verify Stage 1, portable v0.3 evidence, thresholds, and every experiment offline."""

    artifacts = verify_v0_3_qualification_artifacts(root, qualification_id)
    if artifacts.context.code_commit != expected_commit:
        raise StudyArtifactError("v0.3 qualification verification source commit changed")
    mapping = dict(artifacts.files)
    _verify_locked_identities(mapping)

    thresholds = parse_entry_threshold_artifacts(mapping["entry-thresholds.jsonl"])
    expected_threshold_keys = {
        (fold, specialist, percentile)
        for fold in range(1, 13)
        for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
        for percentile in (Decimal("0.70"), Decimal("0.75"), Decimal("0.80"))
    }
    observed_threshold_keys = {
        (item.fold_number, item.specialist, item.percentile) for item in thresholds
    }
    if len(thresholds) != 72 or observed_threshold_keys != expected_threshold_keys:
        raise StudyArtifactError("v0.3 qualification threshold inventory is incomplete")
    if not all(replay_entry_threshold_artifact(item).exact_match for item in thresholds):
        raise StudyArtifactError("v0.3 qualification threshold replay mismatch")
    diagnostics = parse_fold_diagnostics(mapping["fold-diagnostics.jsonl"])
    if tuple(item.fold_number for item in diagnostics) != tuple(range(1, 13)):
        raise StudyArtifactError("v0.3 qualification fold diagnostic inventory is incomplete")
    _verify_report(mapping, artifacts)

    handoff_path = (
        Path(root)
        / "data"
        / "historical-validation"
        / "handoff"
        / artifacts.context.dataset_id
        / "dataset-handoff.json"
    )
    try:
        handoff = load_dataset_handoff(handoff_path.read_bytes())
    except OSError:
        raise StudyArtifactError("v0.3 qualification Stage 1 handoff is missing") from None
    verify_dataset_handoff(
        handoff,
        Path(root),
        expected_commit=expected_commit,
        expected_dataset_id=artifacts.context.dataset_id,
        expected_run_id=artifacts.context.dataset_run_id,
    )
    if handoff.inventory_root_sha256 != artifacts.context.dataset_handoff_inventory_root:
        raise StudyArtifactError("v0.3 qualification Stage 1 inventory identity changed")

    records = _case_records(mapping["case-evidence.jsonl"])
    verifier = ResearchVerificationService(
        root=Path(root),
        current_commit_resolver=lambda: expected_commit,
        strategy_reconstructor=reconstruct_study_strategy,
    )
    for record in records:
        result = verifier.verify(record.experiment_id)
        if (
            result.experiment_id != record.experiment_id
            or result.result_id != record.evidence_sha256
            or result.terminal_status != "completed"
        ):
            raise StudyArtifactError(
                "v0.3 qualification referenced experiment verification changed"
            )
    return artifacts


__all__ = ["replay_entry_threshold_artifact", "verify_candidate_v0_3_qualification"]
