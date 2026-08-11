"""Independent provider-free verification of a Candidate v0.2 qualification bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.qualification_artifacts import (
    QualificationArtifacts,
    verify_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution import qualification_case_ids
from gemini_trading.strategy.study import StudyCaseEvidence, StudyPhase

_CASE_KEYS = {
    "case_id",
    "phase",
    "fold_number",
    "terminal_status",
    "experiment_id",
    "evidence_sha256",
}


def _case_records(raw: bytes) -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError("qualification case evidence is not UTF-8") from None
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError("qualification case evidence JSON is invalid") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError("qualification case evidence row is invalid")
        mapping = cast(dict[str, object], loaded)
        if set(mapping) != _CASE_KEYS:
            raise StudyArtifactError("qualification case evidence fields changed")
        case_id = mapping["case_id"]
        phase = mapping["phase"]
        fold_number = mapping["fold_number"]
        terminal_status = mapping["terminal_status"]
        experiment_id = mapping["experiment_id"]
        evidence_sha256 = mapping["evidence_sha256"]
        if (
            not isinstance(case_id, str)
            or not isinstance(phase, str)
            or isinstance(fold_number, bool)
            or not isinstance(fold_number, int)
            or not isinstance(terminal_status, str)
            or not isinstance(experiment_id, str)
            or not isinstance(evidence_sha256, str)
        ):
            raise StudyArtifactError("qualification case evidence types changed")
        try:
            record = StudyCaseEvidence(
                case_id=case_id,
                phase=StudyPhase(phase),
                fold_number=fold_number,
                terminal_status=terminal_status,
                experiment_id=experiment_id,
                evidence_sha256=evidence_sha256,
            )
        except ValueError:
            raise StudyArtifactError("qualification case evidence is invalid") from None
        if record.phase is not StudyPhase.DEVELOPMENT or record.terminal_status != "completed":
            raise StudyArtifactError(
                "qualification case evidence is not completed development evidence"
            )
        records.append(record)
    if not records:
        raise StudyArtifactError("qualification case evidence is empty")
    expected_cases = qualification_case_ids(CandidatePolicy.locked_v0_2())
    expected = {(fold, case_id) for fold in range(1, 13) for case_id in expected_cases}
    observed = {(record.fold_number, record.case_id) for record in records}
    if observed != expected or len(records) != len(expected):
        raise StudyArtifactError("qualification case evidence set is incomplete")
    return tuple(records)


def verify_qualification_bundle(
    root: Path,
    qualification_id: str,
    *,
    expected_commit: str,
) -> QualificationArtifacts:
    """Verify Stage 1, qualification artifacts, and every referenced experiment offline."""

    artifacts = verify_qualification_artifacts(root, qualification_id)
    if artifacts.context.code_commit != expected_commit:
        raise StudyArtifactError("qualification verification source commit changed")

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
        raise StudyArtifactError("qualification Stage 1 handoff is missing") from None
    verify_dataset_handoff(
        handoff,
        Path(root),
        expected_commit=expected_commit,
        expected_dataset_id=artifacts.context.dataset_id,
        expected_run_id=artifacts.context.dataset_run_id,
    )
    if handoff.inventory_root_sha256 != artifacts.context.dataset_handoff_inventory_root:
        raise StudyArtifactError("qualification Stage 1 inventory identity changed")

    mapping = dict(artifacts.files)
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
            raise StudyArtifactError("qualification referenced experiment verification changed")
    return artifacts


__all__ = ["verify_qualification_bundle"]
