"""Immutable pre-final evidence for sealed Candidate historical validation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.errors import PreFinalArtifactError
from gemini_trading.strategy.handoff import DatasetHandoffManifest
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    StudyCaseEvidence,
    StudyPhase,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PRE_FINAL_SCHEMA = "candidate-pre-final-v1"
_PRE_FINAL_RESULT_SCHEMA = "candidate-pre-final-result-v1"
REQUIRED_PRE_FINAL_NAMES = (
    "configuration.json",
    "development-experiments.jsonl",
    "handoff-reference.json",
    "policy.json",
    "pre-final-manifest.json",
    "pre-final-result-manifest.json",
    "split-plan.json",
)
_CORE_NAMES = tuple(
    name for name in REQUIRED_PRE_FINAL_NAMES if name != "pre-final-result-manifest.json"
)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _require_sha256(value: str, field_name: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise PreFinalArtifactError(f"invalid {field_name}")
    return value


def _case_payload(record: StudyCaseEvidence) -> dict[str, object]:
    return {
        "case_id": record.case_id,
        "phase": record.phase.value,
        "fold_number": record.fold_number,
        "terminal_status": record.terminal_status,
        "experiment_id": record.experiment_id,
        "evidence_sha256": record.evidence_sha256,
    }


def _handoff_reference(handoff: DatasetHandoffManifest) -> dict[str, object]:
    return {
        "schema_version": "dataset-handoff-reference-v1",
        "dataset_id": handoff.dataset_id,
        "inventory_root_sha256": handoff.inventory_root_sha256,
        "source_commit": handoff.source_commit,
        "workflow_run_id": handoff.workflow_run_id,
        "workflow_run_attempt": handoff.workflow_run_attempt,
        "retrieval_run_id": handoff.run_id,
    }


def _identity_payload(
    *,
    dataset_id: str,
    handoff_inventory_root: str,
    code_commit: str,
    policy_sha256: str,
    configuration_sha256: str,
    split_plan_sha256: str,
    development_records: tuple[StudyCaseEvidence, ...],
) -> dict[str, object]:
    return {
        "schema_version": _PRE_FINAL_SCHEMA,
        "dataset_id": dataset_id,
        "handoff_inventory_root": handoff_inventory_root,
        "code_commit": code_commit,
        "policy_sha256": policy_sha256,
        "configuration_sha256": configuration_sha256,
        "split_plan_sha256": split_plan_sha256,
        "required_development_case_ids": list(REQUIRED_DEVELOPMENT_CASE_IDS),
        "development_experiments": [_case_payload(item) for item in development_records],
    }


def _validate_development_records(records: tuple[StudyCaseEvidence, ...]) -> None:
    if not records:
        raise PreFinalArtifactError("pre-final evidence has no development experiments")
    grouped: dict[int, list[StudyCaseEvidence]] = defaultdict(list)
    for record in records:
        if record.phase is not StudyPhase.DEVELOPMENT or record.fold_number is None:
            raise PreFinalArtifactError("pre-final evidence contains a final-phase record")
        grouped[record.fold_number].append(record)
    expected = set(REQUIRED_DEVELOPMENT_CASE_IDS)
    for fold_number in sorted(grouped):
        records_for_fold = grouped[fold_number]
        case_ids = tuple(item.case_id for item in records_for_fold)
        if len(case_ids) != len(expected) or set(case_ids) != expected:
            raise PreFinalArtifactError(f"incomplete development evidence for fold {fold_number}")


@dataclass(frozen=True, slots=True)
class PreFinalArtifacts:
    """Exact canonical bytes and identity for all development-only evidence."""

    pre_final_id: str
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        _require_sha256(self.pre_final_id, "pre-final ID")
        if tuple(name for name, _ in self.files) != REQUIRED_PRE_FINAL_NAMES:
            raise PreFinalArtifactError("pre-final artifact names are incomplete")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.files)

    def artifact_bytes(self, name: str) -> bytes:
        for artifact_name, content in self.files:
            if artifact_name == name:
                return content
        raise KeyError(name)


def build_pre_final_artifacts(
    *,
    dataset_id: str,
    handoff: DatasetHandoffManifest,
    code_commit: str,
    policy_bytes: bytes,
    configuration_bytes: bytes,
    split_plan_bytes: bytes,
    split_plan_sha256: str,
    development_records: tuple[StudyCaseEvidence, ...],
) -> PreFinalArtifacts:
    """Build the exact immutable development-only evidence contract."""

    _require_sha256(dataset_id, "dataset ID")
    _require_sha256(split_plan_sha256, "split-plan SHA-256")
    if _GIT_COMMIT_PATTERN.fullmatch(code_commit) is None:
        raise PreFinalArtifactError("invalid code commit")
    if handoff.dataset_id != dataset_id:
        raise PreFinalArtifactError("pre-final dataset handoff identity mismatch")
    if handoff.source_commit != code_commit:
        raise PreFinalArtifactError("pre-final source commit mismatch")
    _validate_development_records(development_records)
    policy_sha256 = _sha256_bytes(policy_bytes)
    configuration_sha256 = _sha256_bytes(configuration_bytes)
    identity = _identity_payload(
        dataset_id=dataset_id,
        handoff_inventory_root=handoff.inventory_root_sha256,
        code_commit=code_commit,
        policy_sha256=policy_sha256,
        configuration_sha256=configuration_sha256,
        split_plan_sha256=split_plan_sha256,
        development_records=development_records,
    )
    pre_final_id = _sha256_bytes(canonical_json_bytes(identity))
    manifest_bytes = canonical_json_bytes({**identity, "pre_final_id": pre_final_id})
    core_files: dict[str, bytes] = {
        "configuration.json": configuration_bytes,
        "development-experiments.jsonl": canonical_jsonl_bytes(
            _case_payload(item) for item in development_records
        ),
        "handoff-reference.json": canonical_json_bytes(_handoff_reference(handoff)),
        "policy.json": policy_bytes,
        "pre-final-manifest.json": manifest_bytes,
        "split-plan.json": split_plan_bytes,
    }
    artifact_hashes = tuple(sorted((name, _sha256_bytes(core_files[name])) for name in _CORE_NAMES))
    result_manifest = canonical_json_bytes(
        {
            "schema_version": _PRE_FINAL_RESULT_SCHEMA,
            "pre_final_id": pre_final_id,
            "artifacts": [list(item) for item in artifact_hashes],
        }
    )
    files = tuple(
        sorted((*core_files.items(), ("pre-final-result-manifest.json", result_manifest)))
    )
    return PreFinalArtifacts(pre_final_id=pre_final_id, files=files)


@dataclass(frozen=True, slots=True)
class LocalPreFinalStore:
    """Immutable local store rooted beneath data/historical-validation/pre-final."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _directory(self, pre_final_id: str) -> Path:
        _require_sha256(pre_final_id, "pre-final ID")
        return self.root / "data" / "historical-validation" / "pre-final" / pre_final_id

    def write(self, artifacts: PreFinalArtifacts) -> tuple[tuple[str, Path], ...]:
        paths: list[tuple[str, Path]] = []
        for name, content in artifacts.files:
            path = self._directory(artifacts.pre_final_id) / name
            try:
                write_immutable(path, content)
            except RawStorageConflictError:
                raise PreFinalArtifactError(
                    f"immutable pre-final artifact conflicts: {name}"
                ) from None
            paths.append((name, path))
        return tuple(paths)

    def load(self, pre_final_id: str) -> PreFinalArtifacts:
        directory = self._directory(pre_final_id)
        files: list[tuple[str, bytes]] = []
        for name in REQUIRED_PRE_FINAL_NAMES:
            try:
                content = (directory / name).read_bytes()
            except OSError:
                raise PreFinalArtifactError(f"pre-final artifact is missing: {name}") from None
            files.append((name, content))
        return PreFinalArtifacts(pre_final_id=pre_final_id, files=tuple(files))


def _json_mapping(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PreFinalArtifactError(f"invalid {description} JSON") from None
    if not isinstance(loaded, dict):
        raise PreFinalArtifactError(f"invalid {description} JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise PreFinalArtifactError(f"invalid {description} JSON object")
    return cast(dict[str, object], mapping)


def _jsonl_mappings(raw: bytes, description: str) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        rows.append(_json_mapping(line, description))
    return tuple(rows)


def _required_str(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise PreFinalArtifactError(f"invalid pre-final field: {key}")
    return value


def _required_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PreFinalArtifactError(f"invalid pre-final field: {key}")
    return value


def _records_from_bytes(raw: bytes) -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    for row in _jsonl_mappings(raw, "development experiment"):
        if set(row) != {
            "case_id",
            "phase",
            "fold_number",
            "terminal_status",
            "experiment_id",
            "evidence_sha256",
        }:
            raise PreFinalArtifactError("invalid development experiment fields")
        try:
            phase = StudyPhase(_required_str(row, "phase"))
        except ValueError:
            raise PreFinalArtifactError("invalid development experiment phase") from None
        records.append(
            StudyCaseEvidence(
                case_id=_required_str(row, "case_id"),
                phase=phase,
                fold_number=_required_int(row, "fold_number"),
                terminal_status=_required_str(row, "terminal_status"),
                experiment_id=_required_str(row, "experiment_id"),
                evidence_sha256=_required_str(row, "evidence_sha256"),
            )
        )
    return tuple(records)


def verify_pre_final_artifacts(
    artifacts: PreFinalArtifacts,
    *,
    expected_handoff: DatasetHandoffManifest | None = None,
    expected_code_commit: str | None = None,
    expected_dataset_id: str | None = None,
) -> tuple[str, ...]:
    """Parse and recompute every byte, hash, experiment set, and identity."""

    file_map = dict(artifacts.files)
    result = _json_mapping(file_map["pre-final-result-manifest.json"], "pre-final result")
    if set(result) != {"schema_version", "pre_final_id", "artifacts"}:
        raise PreFinalArtifactError("invalid pre-final result fields")
    if _required_str(result, "schema_version") != _PRE_FINAL_RESULT_SCHEMA:
        raise PreFinalArtifactError("unsupported pre-final result schema")
    if _required_str(result, "pre_final_id") != artifacts.pre_final_id:
        raise PreFinalArtifactError("pre-final result identity mismatch")
    raw_hashes = result.get("artifacts")
    if not isinstance(raw_hashes, list):
        raise PreFinalArtifactError("invalid pre-final artifact hash inventory")
    expected_hashes = tuple(sorted((name, _sha256_bytes(file_map[name])) for name in _CORE_NAMES))
    parsed_hashes: list[tuple[str, str]] = []
    for raw_pair in cast(list[object], raw_hashes):
        if not isinstance(raw_pair, list):
            raise PreFinalArtifactError("invalid pre-final artifact hash inventory")
        pair = cast(list[object], raw_pair)
        if len(pair) != 2:
            raise PreFinalArtifactError("invalid pre-final artifact hash inventory")
        name, digest = pair
        if not isinstance(name, str) or not isinstance(digest, str):
            raise PreFinalArtifactError("invalid pre-final artifact hash inventory")
        parsed_hashes.append((name, digest))
    if tuple(parsed_hashes) != expected_hashes:
        raise PreFinalArtifactError("pre-final artifact hash mismatch")

    manifest = _json_mapping(file_map["pre-final-manifest.json"], "pre-final manifest")
    required_manifest_fields = {
        "schema_version",
        "dataset_id",
        "handoff_inventory_root",
        "code_commit",
        "policy_sha256",
        "configuration_sha256",
        "split_plan_sha256",
        "required_development_case_ids",
        "development_experiments",
        "pre_final_id",
    }
    if set(manifest) != required_manifest_fields:
        raise PreFinalArtifactError("invalid pre-final manifest fields")
    if _required_str(manifest, "schema_version") != _PRE_FINAL_SCHEMA:
        raise PreFinalArtifactError("unsupported pre-final schema")
    dataset_id = _required_str(manifest, "dataset_id")
    code_commit = _required_str(manifest, "code_commit")
    handoff_root = _required_str(manifest, "handoff_inventory_root")
    if expected_dataset_id is not None and dataset_id != expected_dataset_id:
        raise PreFinalArtifactError("pre-final dataset identity mismatch")
    if expected_code_commit is not None and code_commit != expected_code_commit:
        raise PreFinalArtifactError("pre-final code commit mismatch")
    if _sha256_bytes(file_map["policy.json"]) != _required_str(manifest, "policy_sha256"):
        raise PreFinalArtifactError("pre-final policy hash mismatch")
    if _sha256_bytes(file_map["configuration.json"]) != _required_str(
        manifest, "configuration_sha256"
    ):
        raise PreFinalArtifactError("pre-final configuration hash mismatch")
    if _sha256_bytes(file_map["split-plan.json"]) != _required_str(manifest, "split_plan_sha256"):
        raise PreFinalArtifactError("pre-final split-plan hash mismatch")

    records = _records_from_bytes(file_map["development-experiments.jsonl"])
    _validate_development_records(records)
    if manifest.get("required_development_case_ids") != list(REQUIRED_DEVELOPMENT_CASE_IDS):
        raise PreFinalArtifactError("pre-final required case list mismatch")
    if manifest.get("development_experiments") != [_case_payload(item) for item in records]:
        raise PreFinalArtifactError("pre-final development evidence mismatch")

    handoff_reference = _json_mapping(file_map["handoff-reference.json"], "handoff reference")
    if handoff_reference.get("dataset_id") != dataset_id:
        raise PreFinalArtifactError("pre-final handoff dataset mismatch")
    if handoff_reference.get("inventory_root_sha256") != handoff_root:
        raise PreFinalArtifactError("pre-final handoff inventory mismatch")
    if handoff_reference.get("source_commit") != code_commit:
        raise PreFinalArtifactError("pre-final handoff commit mismatch")
    if expected_handoff is not None and handoff_reference != _handoff_reference(expected_handoff):
        raise PreFinalArtifactError("pre-final handoff reference mismatch")

    identity = _identity_payload(
        dataset_id=dataset_id,
        handoff_inventory_root=handoff_root,
        code_commit=code_commit,
        policy_sha256=_required_str(manifest, "policy_sha256"),
        configuration_sha256=_required_str(manifest, "configuration_sha256"),
        split_plan_sha256=_required_str(manifest, "split_plan_sha256"),
        development_records=records,
    )
    rebuilt_id = _sha256_bytes(canonical_json_bytes(identity))
    if (
        rebuilt_id != artifacts.pre_final_id
        or _required_str(manifest, "pre_final_id") != rebuilt_id
    ):
        raise PreFinalArtifactError("pre-final identity mismatch")
    return (
        "pre_final_files_verified",
        "pre_final_hashes_verified",
        "pre_final_development_only_verified",
        "pre_final_identity_verified",
    )


__all__ = [
    "REQUIRED_PRE_FINAL_NAMES",
    "LocalPreFinalStore",
    "PreFinalArtifacts",
    "build_pre_final_artifacts",
    "verify_pre_final_artifacts",
]
