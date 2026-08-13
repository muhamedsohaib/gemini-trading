"""Immutable Candidate v0.3 qualification artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.entry_selectivity import EntryThresholdArtifact
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_execution_v0_3 import V03QualificationRun
from gemini_trading.strategy.v0_3_cases import V03FoldDiagnostics

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "candidate-v0.3-qualification-result-v1"
_RESULT = "qualification-result.json"
_MANIFEST = "qualification-manifest.json"
_POLICY = "policy.json"
_SELECTIVITY = "entry-selectivity-policy.json"
_CONFIGURATION = "configuration.json"
_DEVELOPMENT_PLAN = "development-plan.json"
_THRESHOLDS = "entry-thresholds.jsonl"
_DIAGNOSTICS = "fold-diagnostics.jsonl"


@dataclass(frozen=True, slots=True)
class V03QualificationArtifactContext:
    """Exact source and Stage 1 identities bound to one v0.3 qualification."""

    code_commit: str
    dataset_id: str
    dataset_handoff_inventory_root: str
    dataset_run_id: int
    workflow_run_id: int
    workflow_run_attempt: int

    def __post_init__(self) -> None:
        if _GIT_SHA.fullmatch(self.code_commit) is None:
            raise StudyArtifactError("invalid v0.3 qualification code commit")
        for field_name in ("dataset_id", "dataset_handoff_inventory_root"):
            if _SHA256.fullmatch(getattr(self, field_name)) is None:
                raise StudyArtifactError(f"invalid v0.3 qualification {field_name}")
        for field_name in ("dataset_run_id", "workflow_run_id", "workflow_run_attempt"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 1:
                raise StudyArtifactError(f"invalid v0.3 qualification {field_name}")


@dataclass(frozen=True, slots=True)
class V03QualificationArtifacts:
    """Canonical immutable file set for one Candidate v0.3 qualification."""

    qualification_id: str
    inventory_root_sha256: str
    classification: QualificationClassification
    context: V03QualificationArtifactContext
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.qualification_id) is None:
            raise StudyArtifactError("invalid v0.3 qualification ID")
        if _SHA256.fullmatch(self.inventory_root_sha256) is None:
            raise StudyArtifactError("invalid v0.3 qualification inventory root")
        names = tuple(name for name, _ in self.files)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise StudyArtifactError("v0.3 qualification artifact names must be unique and sorted")
        if _RESULT not in names:
            raise StudyArtifactError("v0.3 qualification result artifact is missing")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _context_payload(context: V03QualificationArtifactContext) -> dict[str, object]:
    return asdict(context)


def _inventory_payload(files: tuple[tuple[str, bytes], ...]) -> list[dict[str, object]]:
    return [
        {"name": name, "sha256": _sha(raw), "size": len(raw)}
        for name, raw in sorted(files)
    ]


def _inventory_root(files: tuple[tuple[str, bytes], ...]) -> str:
    return hashlib.sha256(canonical_json_bytes({"files": _inventory_payload(files)})).hexdigest()


def _validate_run_identity_bytes(run: V03QualificationRun) -> None:
    for raw, expected, description in (
        (run.policy_bytes, run.policy_sha256, "policy"),
        (run.selectivity_policy_bytes, run.selectivity_policy_sha256, "selectivity policy"),
        (run.configuration_bytes, run.configuration_sha256, "configuration"),
        (run.development_plan_bytes, run.development_plan_sha256, "development plan"),
    ):
        if _sha(raw) != expected:
            raise StudyArtifactError(f"v0.3 qualification {description} identity changed")


def _structural_identity(
    *,
    context: V03QualificationArtifactContext,
    classification: QualificationClassification,
    policy_sha256: str,
    selectivity_policy_sha256: str,
    configuration_sha256: str,
    development_plan_sha256: str,
    inventory_root_sha256: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA,
        "context": _context_payload(context),
        "policy_sha256": policy_sha256,
        "selectivity_policy_sha256": selectivity_policy_sha256,
        "configuration_sha256": configuration_sha256,
        "development_plan_sha256": development_plan_sha256,
        "classification": classification.value,
        "inventory_root_sha256": inventory_root_sha256,
    }


def build_v0_3_qualification_artifacts(
    run: V03QualificationRun,
    context: V03QualificationArtifactContext,
) -> V03QualificationArtifacts:
    """Build the canonical portable evidence set for one v0.3 qualification run."""

    _validate_run_identity_bytes(run)
    manifest_payload = {
        "schema_version": _SCHEMA,
        "context": _context_payload(context),
        "policy_sha256": run.policy_sha256,
        "selectivity_policy_sha256": run.selectivity_policy_sha256,
        "configuration_sha256": run.configuration_sha256,
        "development_plan_sha256": run.development_plan_sha256,
        "classification": run.report.classification.value,
    }
    core_files: tuple[tuple[str, bytes], ...] = tuple(
        sorted(
            (
                ("bootstrap.json", canonical_json_bytes(asdict(run.bootstrap))),
                (
                    "calibration-diagnostics.jsonl",
                    canonical_jsonl_bytes(asdict(item) for item in run.calibration_diagnostics),
                ),
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
                (_CONFIGURATION, run.configuration_bytes),
                (
                    "determinism-receipts.jsonl",
                    canonical_jsonl_bytes(asdict(item) for item in run.determinism_receipts),
                ),
                (_DEVELOPMENT_PLAN, run.development_plan_bytes),
                (_SELECTIVITY, run.selectivity_policy_bytes),
                (_THRESHOLDS, canonical_jsonl_bytes(asdict(item) for item in run.threshold_artifacts)),
                (_DIAGNOSTICS, canonical_jsonl_bytes(asdict(item) for item in run.fold_diagnostics)),
                (
                    "qualification-gates.jsonl",
                    canonical_jsonl_bytes(asdict(item) for item in run.report.gates),
                ),
                (
                    "qualification-report.json",
                    canonical_json_bytes(
                        {
                            "classification": run.report.classification.value,
                            "gate_ids": tuple(item.gate_id for item in run.report.gates),
                        }
                    ),
                ),
                (_MANIFEST, canonical_json_bytes(manifest_payload)),
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
                (_POLICY, run.policy_bytes),
            )
        )
    )
    root = _inventory_root(core_files)
    structural = _structural_identity(
        context=context,
        classification=run.report.classification,
        policy_sha256=run.policy_sha256,
        selectivity_policy_sha256=run.selectivity_policy_sha256,
        configuration_sha256=run.configuration_sha256,
        development_plan_sha256=run.development_plan_sha256,
        inventory_root_sha256=root,
    )
    qualification_id = hashlib.sha256(canonical_json_bytes(structural)).hexdigest()
    result_payload = {
        "schema_version": _SCHEMA,
        "qualification_id": qualification_id,
        "classification": run.report.classification.value,
        "inventory_root_sha256": root,
        "artifacts": _inventory_payload(core_files),
    }
    all_files = tuple(sorted((*core_files, (_RESULT, canonical_json_bytes(result_payload)))))
    return V03QualificationArtifacts(
        qualification_id=qualification_id,
        inventory_root_sha256=root,
        classification=run.report.classification,
        context=context,
        files=all_files,
    )


@dataclass(frozen=True, slots=True)
class V03LocalQualificationStore:
    """Immutable local store for Candidate v0.3 qualification evidence."""

    root: Path

    def directory(self, qualification_id: str) -> Path:
        if _SHA256.fullmatch(qualification_id) is None:
            raise StudyArtifactError("invalid v0.3 qualification ID")
        return (
            self.root / "data" / "historical-validation" / "v0-3-qualification" / qualification_id
        )

    def write(self, artifacts: V03QualificationArtifacts) -> None:
        directory = self.directory(artifacts.qualification_id)
        for name, raw in artifacts.files:
            write_immutable(directory / name, raw)


def _load_json(raw: bytes, description: str) -> dict[str, object]:
    try:
        value: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyArtifactError(f"invalid v0.3 qualification artifact: {description}") from None
    if not isinstance(value, dict):
        raise StudyArtifactError(f"invalid v0.3 qualification artifact: {description}")
    return cast(dict[str, object], value)


def _required_sha(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StudyArtifactError(f"v0.3 qualification artifact {description} is invalid")
    return value


def parse_entry_threshold_artifacts(raw: bytes) -> tuple[EntryThresholdArtifact, ...]:
    """Parse canonical threshold rows without accessing a provider."""

    rows: list[EntryThresholdArtifact] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError("v0.3 entry threshold artifacts are not UTF-8") from None
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError("invalid v0.3 entry threshold JSON") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError("invalid v0.3 entry threshold row")
        item = cast(dict[str, object], loaded)
        try:
            rows.append(
                EntryThresholdArtifact(
                    schema_version=cast(str, item["schema_version"]),
                    fold_number=cast(int, item["fold_number"]),
                    specialist=SpecialistKind(cast(str, item["specialist"])),
                    percentile=Decimal(cast(str, item["percentile"])),
                    eligible_indices=tuple(cast(list[int], item["eligible_indices"])),
                    eligible_scores=tuple(
                        Decimal(cast(str, value))
                        for value in cast(list[object], item["eligible_scores"])
                    ),
                    eligible_rows_sha256=cast(str, item["eligible_rows_sha256"]),
                    score_vector_sha256=cast(str, item["score_vector_sha256"]),
                    raw_quantile=Decimal(cast(str, item["raw_quantile"])),
                    effective_threshold=Decimal(cast(str, item["effective_threshold"])),
                    quantile_method=cast(str, item["quantile_method"]),
                )
            )
        except (KeyError, ValueError, InvalidOperation, TypeError):
            raise StudyArtifactError("invalid v0.3 entry threshold value") from None
    return tuple(rows)


def parse_fold_diagnostics(raw: bytes) -> tuple[V03FoldDiagnostics, ...]:
    """Parse canonical diagnostic-only fold evidence."""

    rows: list[V03FoldDiagnostics] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyArtifactError("v0.3 fold diagnostics are not UTF-8") from None
    for line in text.splitlines():
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            raise StudyArtifactError("invalid v0.3 fold diagnostic JSON") from None
        if not isinstance(loaded, dict):
            raise StudyArtifactError("invalid v0.3 fold diagnostic row")
        item = cast(dict[str, object], loaded)
        try:
            rows.append(
                V03FoldDiagnostics(
                    schema_version=cast(str, item["schema_version"]),
                    fold_number=cast(int, item["fold_number"]),
                    decision_indices=tuple(cast(list[int], item["decision_indices"])),
                    companion_indices=tuple(cast(list[int], item["companion_indices"])),
                    companion_probabilities=tuple(
                        Decimal(cast(str, value))
                        for value in cast(list[object], item["companion_probabilities"])
                    ),
                    disagreement_indices=tuple(cast(list[int], item["disagreement_indices"])),
                    absolute_disagreements=tuple(
                        Decimal(cast(str, value))
                        for value in cast(list[object], item["absolute_disagreements"])
                    ),
                    companion_distribution_sha256=cast(str, item["companion_distribution_sha256"]),
                    disagreement_distribution_sha256=cast(str, item["disagreement_distribution_sha256"]),
                )
            )
        except (KeyError, ValueError, InvalidOperation, TypeError):
            raise StudyArtifactError("invalid v0.3 fold diagnostic value") from None
    return tuple(rows)


def verify_v0_3_qualification_artifacts(
    root: Path,
    qualification_id: str,
) -> V03QualificationArtifacts:
    """Verify v0.3 qualification evidence byte-for-byte without network access."""

    directory = V03LocalQualificationStore(root).directory(qualification_id)
    try:
        result_raw = (directory / _RESULT).read_bytes()
    except OSError:
        raise StudyArtifactError("v0.3 qualification artifact result is missing") from None
    result = _load_json(result_raw, "result")
    if result.get("schema_version") != _SCHEMA or result.get("qualification_id") != qualification_id:
        raise StudyArtifactError("v0.3 qualification artifact result identity changed")
    inventory = result.get("artifacts")
    if not isinstance(inventory, list):
        raise StudyArtifactError("v0.3 qualification artifact inventory is invalid")
    core_files: list[tuple[str, bytes]] = []
    for raw_entry in cast(list[object], inventory):
        if not isinstance(raw_entry, dict):
            raise StudyArtifactError("v0.3 qualification artifact inventory is invalid")
        entry = cast(dict[str, object], raw_entry)
        name = entry.get("name")
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size")
        if (
            not isinstance(name, str)
            or not isinstance(expected_sha, str)
            or not isinstance(expected_size, int)
        ):
            raise StudyArtifactError("v0.3 qualification artifact inventory is invalid")
        try:
            raw = (directory / name).read_bytes()
        except OSError:
            raise StudyArtifactError(f"v0.3 qualification artifact is missing: {name}") from None
        if len(raw) != expected_size or _sha(raw) != expected_sha:
            raise StudyArtifactError(f"v0.3 qualification artifact changed: {name}")
        core_files.append((name, raw))
    core = tuple(sorted(core_files))
    expected_names = tuple(
        sorted(
            (
                "bootstrap.json",
                "calibration-diagnostics.jsonl",
                "case-evidence.jsonl",
                _CONFIGURATION,
                "determinism-receipts.jsonl",
                _DEVELOPMENT_PLAN,
                _SELECTIVITY,
                _THRESHOLDS,
                _DIAGNOSTICS,
                "qualification-gates.jsonl",
                "qualification-report.json",
                _MANIFEST,
                "limitations.json",
                _POLICY,
            )
        )
    )
    if tuple(name for name, _ in core) != expected_names:
        raise StudyArtifactError("v0.3 qualification artifact inventory names changed")
    root_sha = _inventory_root(core)
    if result.get("inventory_root_sha256") != root_sha:
        raise StudyArtifactError("v0.3 qualification artifact inventory root changed")
    mapping = dict(core)

    thresholds = parse_entry_threshold_artifacts(mapping[_THRESHOLDS])
    if canonical_jsonl_bytes(asdict(item) for item in thresholds) != mapping[_THRESHOLDS]:
        raise StudyArtifactError("v0.3 entry threshold canonical bytes changed")
    diagnostics = parse_fold_diagnostics(mapping[_DIAGNOSTICS])
    if canonical_jsonl_bytes(asdict(item) for item in diagnostics) != mapping[_DIAGNOSTICS]:
        raise StudyArtifactError("v0.3 fold diagnostic canonical bytes changed")

    manifest = _load_json(mapping[_MANIFEST], "manifest")
    if manifest.get("schema_version") != _SCHEMA:
        raise StudyArtifactError("v0.3 qualification manifest schema changed")
    context_raw = manifest.get("context")
    if not isinstance(context_raw, dict):
        raise StudyArtifactError("v0.3 qualification context is invalid")
    context_map = cast(dict[str, object], context_raw)
    try:
        context = V03QualificationArtifactContext(
            code_commit=cast(str, context_map["code_commit"]),
            dataset_id=cast(str, context_map["dataset_id"]),
            dataset_handoff_inventory_root=cast(str, context_map["dataset_handoff_inventory_root"]),
            dataset_run_id=cast(int, context_map["dataset_run_id"]),
            workflow_run_id=cast(int, context_map["workflow_run_id"]),
            workflow_run_attempt=cast(int, context_map["workflow_run_attempt"]),
        )
        classification = QualificationClassification(cast(str, result["classification"]))
    except (KeyError, ValueError):
        raise StudyArtifactError("v0.3 qualification metadata is invalid") from None
    if manifest.get("classification") != classification.value:
        raise StudyArtifactError("v0.3 qualification classification changed")
    policy_sha256 = _required_sha(manifest, "policy_sha256", "policy identity")
    selectivity_policy_sha256 = _required_sha(
        manifest, "selectivity_policy_sha256", "selectivity policy identity"
    )
    configuration_sha256 = _required_sha(manifest, "configuration_sha256", "configuration identity")
    development_plan_sha256 = _required_sha(
        manifest, "development_plan_sha256", "development plan identity"
    )
    for name, expected, description in (
        (_POLICY, policy_sha256, "policy"),
        (_SELECTIVITY, selectivity_policy_sha256, "selectivity policy"),
        (_CONFIGURATION, configuration_sha256, "configuration"),
        (_DEVELOPMENT_PLAN, development_plan_sha256, "development plan"),
    ):
        if _sha(mapping[name]) != expected:
            raise StudyArtifactError(f"v0.3 qualification artifact {description} identity changed")
    expected_manifest = canonical_json_bytes(
        {
            "schema_version": _SCHEMA,
            "context": _context_payload(context),
            "policy_sha256": policy_sha256,
            "selectivity_policy_sha256": selectivity_policy_sha256,
            "configuration_sha256": configuration_sha256,
            "development_plan_sha256": development_plan_sha256,
            "classification": classification.value,
        }
    )
    if mapping[_MANIFEST] != expected_manifest:
        raise StudyArtifactError("v0.3 qualification manifest canonical bytes changed")
    structural = _structural_identity(
        context=context,
        classification=classification,
        policy_sha256=policy_sha256,
        selectivity_policy_sha256=selectivity_policy_sha256,
        configuration_sha256=configuration_sha256,
        development_plan_sha256=development_plan_sha256,
        inventory_root_sha256=root_sha,
    )
    if hashlib.sha256(canonical_json_bytes(structural)).hexdigest() != qualification_id:
        raise StudyArtifactError("v0.3 qualification structural identity changed")
    files = tuple(sorted((*core, (_RESULT, result_raw))))
    return V03QualificationArtifacts(
        qualification_id=qualification_id,
        inventory_root_sha256=root_sha,
        classification=classification,
        context=context,
        files=files,
    )


__all__ = [
    "V03LocalQualificationStore",
    "V03QualificationArtifactContext",
    "V03QualificationArtifacts",
    "build_v0_3_qualification_artifacts",
    "parse_entry_threshold_artifacts",
    "parse_fold_diagnostics",
    "verify_v0_3_qualification_artifacts",
]
