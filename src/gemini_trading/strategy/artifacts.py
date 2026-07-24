"""Canonical immutable artifacts for complete Candidate strategy studies."""

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.evaluation import PromotionClassification
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    StrategyStudyEvidence,
    StudyCaseEvidence,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_JSONL_NAMES = {
    "feature-matrix.jsonl",
    "labels.jsonl",
    "folds.jsonl",
    "models.jsonl",
    "calibration.jsonl",
    "predictions.jsonl",
    "regimes.jsonl",
    "arbitration-decisions.jsonl",
}
_REQUIRED_PAYLOAD_NAMES = {
    "policy.json",
    "feature-registry.json",
    "feature-matrix.jsonl",
    "labels.jsonl",
    "split-plan.json",
    "folds.jsonl",
    "models.jsonl",
    "calibration.jsonl",
    "predictions.jsonl",
    "regimes.jsonl",
    "arbitration-decisions.jsonl",
    "baselines.json",
    "ablations.json",
    "negative-controls.json",
    "cost-stress.json",
    "parameter-sensitivity.json",
    "bootstrap.json",
    "promotion-gates.json",
    "limitations.json",
}
REQUIRED_STUDY_ARTIFACT_NAMES = tuple(
    sorted(
        {
            "study-manifest.json",
            "experiments.jsonl",
            "study-result-manifest.json",
            *_REQUIRED_PAYLOAD_NAMES,
        }
    )
)


def _case_payload(item: StudyCaseEvidence) -> dict[str, object]:
    return {
        "case_id": item.case_id,
        "phase": item.phase.value,
        "fold_number": item.fold_number,
        "terminal_status": item.terminal_status,
        "experiment_id": item.experiment_id,
        "evidence_sha256": item.evidence_sha256,
    }


def _validate_evidence(evidence: StrategyStudyEvidence) -> None:
    grouped: dict[int, list[StudyCaseEvidence]] = {}
    for record in evidence.fold_records:
        if record.fold_number is None:
            raise StudyArtifactError("development evidence is missing fold identity")
        grouped.setdefault(record.fold_number, []).append(record)
    if not grouped:
        raise StudyArtifactError("incomplete development evidence")
    required_development = set(REQUIRED_DEVELOPMENT_CASE_IDS)
    for fold_number, records in grouped.items():
        case_ids = tuple(item.case_id for item in records)
        if set(case_ids) != required_development or len(case_ids) != len(required_development):
            raise StudyArtifactError(f"incomplete development evidence for fold {fold_number}")
    final_case_ids = tuple(item.case_id for item in evidence.final_records)
    if set(final_case_ids) != set(REQUIRED_FINAL_CASE_IDS) or len(final_case_ids) != len(
        REQUIRED_FINAL_CASE_IDS
    ):
        raise StudyArtifactError("incomplete final evidence")
    if evidence.final_test_receipt.evaluation_count != 1:
        raise StudyArtifactError("final-test receipt must record exactly one evaluation")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StudyArtifactError(f"study payload must be a mapping: {name}")
    raw = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise StudyArtifactError(f"study payload keys must be strings: {name}")
    return cast(Mapping[str, object], raw)


def _encode_payload(name: str, value: object) -> bytes:
    if name in _JSONL_NAMES:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise StudyArtifactError(f"study JSONL payload must be a sequence: {name}")
        rows = tuple(_mapping(item, name) for item in cast(Sequence[object], value))
        return canonical_jsonl_bytes(rows)
    return canonical_json_bytes(_mapping(value, name))


@dataclass(frozen=True, slots=True)
class StrategyStudyArtifacts:
    """Complete canonical bytes and content identity for one strategy study."""

    study_id: str
    study_result_id: str
    classification: PromotionClassification
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if _SHA256_PATTERN.fullmatch(self.study_id) is None:
            raise ValueError("study_id must be a lowercase SHA-256 digest")
        if _SHA256_PATTERN.fullmatch(self.study_result_id) is None:
            raise ValueError("study_result_id must be a lowercase SHA-256 digest")
        names = tuple(name for name, _ in self.files)
        if names != REQUIRED_STUDY_ARTIFACT_NAMES:
            raise StudyArtifactError("strategy study artifact names are incomplete")

    @property
    def names(self) -> tuple[str, ...]:
        """Return the exact sorted artifact-name contract."""

        return tuple(name for name, _ in self.files)

    def artifact_bytes(self, name: str) -> bytes:
        """Return exact canonical bytes for one required artifact."""

        for artifact_name, content in self.files:
            if artifact_name == name:
                return content
        raise KeyError(name)


def build_study_artifacts(
    evidence: StrategyStudyEvidence,
    *,
    classification: PromotionClassification,
    payloads: Mapping[str, object],
) -> StrategyStudyArtifacts:
    """Build every required artifact and a self-excluding content-derived identity."""

    _validate_evidence(evidence)
    if set(payloads) != _REQUIRED_PAYLOAD_NAMES:
        raise StudyArtifactError("required study payloads are incomplete")
    study_manifest = canonical_json_bytes(
        {
            "schema_version": "strategy-study-v1",
            "study_id": evidence.study_id,
            "split_plan_sha256": evidence.split_plan_sha256,
            "policy_sha256": evidence.policy_sha256,
            "configuration_sha256": evidence.configuration_sha256,
            "final_test_receipt_id": evidence.final_test_receipt.receipt_id,
            "final_evaluation_count": evidence.final_test_receipt.evaluation_count,
        }
    )
    experiments = canonical_jsonl_bytes(
        _case_payload(item) for item in (*evidence.fold_records, *evidence.final_records)
    )
    core_files: dict[str, bytes] = {
        "study-manifest.json": study_manifest,
        "experiments.jsonl": experiments,
        **{name: _encode_payload(name, payloads[name]) for name in sorted(_REQUIRED_PAYLOAD_NAMES)},
    }
    artifact_hashes = tuple(
        sorted((name, hashlib.sha256(content).hexdigest()) for name, content in core_files.items())
    )
    identity_payload: dict[str, object] = {
        "schema_version": "strategy-study-result-v1",
        "study_id": evidence.study_id,
        "artifacts": [list(item) for item in artifact_hashes],
        "classification": classification.value,
    }
    result_id = hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest()
    result_manifest = canonical_json_bytes({**identity_payload, "study_result_id": result_id})
    files = tuple(sorted((*core_files.items(), ("study-result-manifest.json", result_manifest))))
    return StrategyStudyArtifacts(
        study_id=evidence.study_id,
        study_result_id=result_id,
        classification=classification,
        files=files,
    )


@dataclass(frozen=True, slots=True)
class LocalStrategyStudyStore:
    """Immutable local store rooted beneath data/strategy-studies."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _directory(self, study_id: str) -> Path:
        if _SHA256_PATTERN.fullmatch(study_id) is None:
            raise ValueError("invalid strategy study identity")
        return self.root / "data" / "strategy-studies" / study_id

    def write(self, artifacts: StrategyStudyArtifacts) -> tuple[tuple[str, Path], ...]:
        """Write once and accept only byte-identical reruns."""

        directory = self._directory(artifacts.study_id)
        paths: list[tuple[str, Path]] = []
        for name, content in artifacts.files:
            path = directory / name
            try:
                write_immutable(path, content)
            except RawStorageConflictError:
                raise StudyArtifactError(f"immutable study artifact conflicts: {name}") from None
            paths.append((name, path))
        return tuple(paths)

    def read_artifact(self, study_id: str, name: str) -> bytes:
        """Read one persisted study artifact."""

        if name not in REQUIRED_STUDY_ARTIFACT_NAMES:
            raise ValueError("invalid strategy study artifact name")
        return (self._directory(study_id) / name).read_bytes()


__all__ = [
    "REQUIRED_STUDY_ARTIFACT_NAMES",
    "LocalStrategyStudyStore",
    "StrategyStudyArtifacts",
    "build_study_artifacts",
]
