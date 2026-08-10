"""Immutable Candidate v0.2 development-qualification artifacts and verification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_execution import QualificationRun

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "candidate-v0.2-qualification-artifacts-v1"
_RESULT = "qualification-result.json"


@dataclass(frozen=True, slots=True)
class QualificationArtifactContext:
    """Exact source/workflow identities bound to one qualification run."""

    code_commit: str
    dataset_id: str
    dataset_handoff_inventory_root: str
    dataset_run_id: int
    workflow_run_id: int
    workflow_run_attempt: int

    def __post_init__(self) -> None:
        if _GIT_SHA.fullmatch(self.code_commit) is None:
            raise StudyArtifactError("invalid qualification code commit")
        for field_name in ("dataset_id", "dataset_handoff_inventory_root"):
            if _SHA256.fullmatch(getattr(self, field_name)) is None:
                raise StudyArtifactError(f"invalid qualification {field_name}")
        for field_name in ("dataset_run_id", "workflow_run_id", "workflow_run_attempt"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 1:
                raise StudyArtifactError(f"invalid qualification {field_name}")


@dataclass(frozen=True, slots=True)
class QualificationArtifacts:
    """Canonical immutable file set for one Candidate v0.2 qualification."""

    qualification_id: str
    inventory_root_sha256: str
    classification: QualificationClassification
    context: QualificationArtifactContext
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.qualification_id) is None:
            raise StudyArtifactError("invalid qualification ID")
        if _SHA256.fullmatch(self.inventory_root_sha256) is None:
            raise StudyArtifactError("invalid qualification inventory root")
        names = tuple(name for name, _ in self.files)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise StudyArtifactError("qualification artifact names must be unique and sorted")
        if _RESULT not in names:
            raise StudyArtifactError("qualification result artifact is missing")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _context_payload(context: QualificationArtifactContext) -> dict[str, object]:
    return asdict(context)


def _inventory_payload(files: tuple[tuple[str, bytes], ...]) -> list[dict[str, object]]:
    return [{"name": name, "sha256": _sha(raw), "size": len(raw)} for name, raw in sorted(files)]


def _inventory_root(files: tuple[tuple[str, bytes], ...]) -> str:
    return hashlib.sha256(canonical_json_bytes({"files": _inventory_payload(files)})).hexdigest()


def build_qualification_artifacts(
    run: QualificationRun,
    context: QualificationArtifactContext,
) -> QualificationArtifacts:
    """Build the canonical non-executable evidence set for one qualification run."""

    structural = {
        "schema_version": _SCHEMA,
        "context": _context_payload(context),
        "policy_sha256": run.policy_sha256,
        "configuration_sha256": run.configuration_sha256,
        "development_plan_sha256": run.development_plan_sha256,
        "classification": run.report.classification.value,
    }
    qualification_id = hashlib.sha256(canonical_json_bytes(structural)).hexdigest()
    core_files: tuple[tuple[str, bytes], ...] = tuple(
        sorted(
            (
                ("bootstrap.json", canonical_json_bytes(asdict(run.bootstrap))),
                (
                    "case-evidence.jsonl",
                    canonical_jsonl_bytes(
                        {
                            "case_id": item.case_id,
                            "phase": item.phase.value,
                            "fold_number": item.fold_number,
                            "terminal_status": item.terminal_status,
                            "experiment_id": item.experiment_id,
                            "evidence_sha256": item.evidence_sha256,
                        }
                        for item in run.case_evidence
                    ),
                ),
                (
                    "determinism-receipts.jsonl",
                    canonical_jsonl_bytes(asdict(item) for item in run.determinism_receipts),
                ),
                (
                    "qualification-gates.jsonl",
                    canonical_jsonl_bytes(asdict(item) for item in run.report.gates),
                ),
                (
                    "qualification-manifest.json",
                    canonical_json_bytes({**structural, "qualification_id": qualification_id}),
                ),
                (
                    "limitations.json",
                    canonical_json_bytes(
                        {
                            "research_only": True,
                            "future_profitability_not_established": True,
                            "execution_authorized": False,
                            "prospective_final_accessed": False,
                        }
                    ),
                ),
            )
        )
    )
    root = _inventory_root(core_files)
    result_payload = {
        "schema_version": _SCHEMA,
        "qualification_id": qualification_id,
        "classification": run.report.classification.value,
        "inventory_root_sha256": root,
        "artifacts": _inventory_payload(core_files),
    }
    all_files = tuple(sorted((*core_files, (_RESULT, canonical_json_bytes(result_payload)))))
    return QualificationArtifacts(
        qualification_id=qualification_id,
        inventory_root_sha256=root,
        classification=run.report.classification,
        context=context,
        files=all_files,
    )


@dataclass(frozen=True, slots=True)
class LocalQualificationStore:
    """Immutable local store for Candidate v0.2 qualification evidence."""

    root: Path

    def _directory(self, qualification_id: str) -> Path:
        if _SHA256.fullmatch(qualification_id) is None:
            raise StudyArtifactError("invalid qualification ID")
        return (
            self.root / "data" / "historical-validation" / "v0-2-qualification" / qualification_id
        )

    def write(self, artifacts: QualificationArtifacts) -> None:
        directory = self._directory(artifacts.qualification_id)
        for name, raw in artifacts.files:
            write_immutable(directory / name, raw)


def _load_json(raw: bytes, description: str) -> dict[str, object]:
    try:
        value: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyArtifactError(f"invalid qualification artifact: {description}") from None
    if not isinstance(value, dict):
        raise StudyArtifactError(f"invalid qualification artifact: {description}")
    return cast(dict[str, object], value)


def verify_qualification_artifacts(root: Path, qualification_id: str) -> QualificationArtifacts:
    """Verify qualification evidence byte-for-byte without provider or network access."""

    directory = LocalQualificationStore(root)._directory(qualification_id)
    try:
        result_raw = (directory / _RESULT).read_bytes()
    except OSError:
        raise StudyArtifactError("qualification artifact result is missing") from None
    result = _load_json(result_raw, "result")
    if (
        result.get("schema_version") != _SCHEMA
        or result.get("qualification_id") != qualification_id
    ):
        raise StudyArtifactError("qualification artifact result identity changed")
    raw_inventory = result.get("artifacts")
    if not isinstance(raw_inventory, list):
        raise StudyArtifactError("qualification artifact inventory is invalid")
    core_files: list[tuple[str, bytes]] = []
    for raw_entry in cast(list[object], raw_inventory):
        if not isinstance(raw_entry, dict):
            raise StudyArtifactError("qualification artifact inventory is invalid")
        entry = cast(dict[str, object], raw_entry)
        name = entry.get("name")
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size")
        if (
            not isinstance(name, str)
            or not isinstance(expected_sha, str)
            or not isinstance(expected_size, int)
        ):
            raise StudyArtifactError("qualification artifact inventory is invalid")
        try:
            raw = (directory / name).read_bytes()
        except OSError:
            raise StudyArtifactError(f"qualification artifact is missing: {name}") from None
        if len(raw) != expected_size or _sha(raw) != expected_sha:
            raise StudyArtifactError(f"qualification artifact changed: {name}")
        core_files.append((name, raw))
    core = tuple(sorted(core_files))
    root_sha = _inventory_root(core)
    if result.get("inventory_root_sha256") != root_sha:
        raise StudyArtifactError("qualification artifact inventory root changed")
    manifest = _load_json(dict(core)["qualification-manifest.json"], "manifest")
    if manifest.get("qualification_id") != qualification_id:
        raise StudyArtifactError("qualification artifact manifest identity changed")
    context_raw = manifest.get("context")
    if not isinstance(context_raw, dict):
        raise StudyArtifactError("qualification artifact context is invalid")
    context_map = cast(dict[str, object], context_raw)
    try:
        context = QualificationArtifactContext(
            code_commit=cast(str, context_map["code_commit"]),
            dataset_id=cast(str, context_map["dataset_id"]),
            dataset_handoff_inventory_root=cast(str, context_map["dataset_handoff_inventory_root"]),
            dataset_run_id=cast(int, context_map["dataset_run_id"]),
            workflow_run_id=cast(int, context_map["workflow_run_id"]),
            workflow_run_attempt=cast(int, context_map["workflow_run_attempt"]),
        )
        classification = QualificationClassification(cast(str, result["classification"]))
    except (KeyError, ValueError):
        raise StudyArtifactError("qualification artifact metadata is invalid") from None
    structural = {
        "schema_version": _SCHEMA,
        "context": _context_payload(context),
        "policy_sha256": manifest.get("policy_sha256"),
        "configuration_sha256": manifest.get("configuration_sha256"),
        "development_plan_sha256": manifest.get("development_plan_sha256"),
        "classification": classification.value,
    }
    if hashlib.sha256(canonical_json_bytes(structural)).hexdigest() != qualification_id:
        raise StudyArtifactError("qualification artifact structural identity changed")
    files = tuple(sorted((*core, (_RESULT, result_raw))))
    return QualificationArtifacts(
        qualification_id=qualification_id,
        inventory_root_sha256=root_sha,
        classification=classification,
        context=context,
        files=files,
    )


__all__ = [
    "LocalQualificationStore",
    "QualificationArtifactContext",
    "QualificationArtifacts",
    "build_qualification_artifacts",
    "verify_qualification_artifacts",
]
