"""Provider-free replay of immutable Candidate strategy-study evidence."""

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gemini_trading.research.replay import resolve_clean_git_commit
from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes
from gemini_trading.strategy.artifacts import (
    REQUIRED_STUDY_ARTIFACT_NAMES,
    LocalStrategyStudyStore,
    StrategyStudyArtifacts,
)
from gemini_trading.strategy.errors import StudyReplayMismatchError
from gemini_trading.strategy.evaluation import PromotionClassification
from gemini_trading.strategy.handoff import ExcludedProviderRow
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    StudyCaseEvidence,
    StudyPhase,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_RESULT_KEYS = {
    "schema_version",
    "study_id",
    "artifacts",
    "classification",
    "study_result_id",
}
_LEGACY_STUDY_MANIFEST_KEYS = {
    "schema_version",
    "study_id",
    "split_plan_sha256",
    "policy_sha256",
    "configuration_sha256",
    "code_commit",
    "final_test_receipt_id",
    "final_evaluation_count",
}
_SEALED_STUDY_MANIFEST_KEYS = {
    *_LEGACY_STUDY_MANIFEST_KEYS,
    "pre_final_id",
    "dataset_handoff_inventory_root",
    "durable_final_access_receipt_id",
    "dataset_schema_version",
    "closure_manifest_sha256",
    "exclusion_manifest_sha256",
    "segment_manifest_sha256",
    "closure_count",
    "exclusion_count",
    "segment_count",
    "closure_ids",
    "excluded_provider_rows",
    "segment_boundary_indices",
}
_CASE_KEYS = {
    "case_id",
    "phase",
    "fold_number",
    "terminal_status",
    "experiment_id",
    "evidence_sha256",
}

SUPPORTED_REPLAY_STRATEGY_IDS = (
    "fixture.scripted.v1",
    "candidate.multi_model.v0_1",
    "candidate.multi_model.v0_2",
    "cash.v1",
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
)


def _default_current_commit() -> str:
    return resolve_clean_git_commit(Path.cwd())


def validate_replay_strategy_id(strategy_id: str) -> str:
    """Accept only the closed provider-free replay strategy registry."""

    if strategy_id not in SUPPORTED_REPLAY_STRATEGY_IDS:
        raise StudyReplayMismatchError("unsupported replay strategy identity")
    return strategy_id


def _json_object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyReplayMismatchError(f"invalid {description} JSON") from None
    if not isinstance(loaded, dict):
        raise StudyReplayMismatchError(f"invalid {description} JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise StudyReplayMismatchError(f"invalid {description} JSON object")
    return cast(dict[str, object], mapping)


def _jsonl_objects(raw: bytes, description: str) -> tuple[dict[str, object], ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StudyReplayMismatchError(f"invalid {description} JSONL") from None
    if not text or not text.endswith("\n"):
        raise StudyReplayMismatchError(f"invalid {description} JSONL")
    rows = tuple(_json_object(line.encode("utf-8"), description) for line in text.splitlines())
    if canonical_jsonl_bytes(rows) != raw:
        raise StudyReplayMismatchError(f"{description} canonical bytes do not match")
    return rows


def _required_str(mapping: Mapping[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    return value


def _required_int(mapping: Mapping[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    return value


def _sha256(value: str, description: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise StudyReplayMismatchError(f"invalid {description}")
    return value


def _required_string_tuple(
    mapping: Mapping[str, object], key: str, description: str
) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    return tuple(cast(list[str], values))


def _required_positive_int_tuple(
    mapping: Mapping[str, object], key: str, description: str
) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    values = cast(list[object], value)
    if not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in values
    ):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    return tuple(cast(list[int], values))


def _required_excluded_rows(
    mapping: Mapping[str, object], key: str, description: str
) -> tuple[ExcludedProviderRow, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    rows: list[ExcludedProviderRow] = []
    for raw_row in cast(list[object], value):
        if not isinstance(raw_row, dict):
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        row = cast(dict[object, object], raw_row)
        if set(row) != {"closure_id", "provider_row_sha256"}:
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        closure_id = row.get("closure_id")
        provider_row_sha256 = row.get("provider_row_sha256")
        if not isinstance(closure_id, str) or not isinstance(provider_row_sha256, str):
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        rows.append(
            ExcludedProviderRow(
                closure_id=closure_id,
                provider_row_sha256=provider_row_sha256,
            )
        )
    return tuple(rows)


def _parse_case(row: Mapping[str, object]) -> StudyCaseEvidence:
    if set(row) != _CASE_KEYS:
        raise StudyReplayMismatchError("strategy study case fields changed")
    phase_value = _required_str(row, "phase", "strategy study case")
    try:
        phase = StudyPhase(phase_value)
    except ValueError:
        raise StudyReplayMismatchError("invalid strategy study phase") from None
    raw_fold = row.get("fold_number")
    fold_number = (
        None if raw_fold is None else _required_int(row, "fold_number", "strategy study case")
    )
    try:
        return StudyCaseEvidence(
            case_id=_required_str(row, "case_id", "strategy study case"),
            phase=phase,
            fold_number=fold_number,
            terminal_status=_required_str(row, "terminal_status", "strategy study case"),
            experiment_id=_sha256(
                _required_str(row, "experiment_id", "strategy study case"),
                "strategy study experiment identity",
            ),
            evidence_sha256=_sha256(
                _required_str(row, "evidence_sha256", "strategy study case"),
                "strategy study evidence identity",
            ),
        )
    except ValueError as error:
        raise StudyReplayMismatchError(str(error)) from None


def _case_payload(case: StudyCaseEvidence) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "phase": case.phase.value,
        "fold_number": case.fold_number,
        "terminal_status": case.terminal_status,
        "experiment_id": case.experiment_id,
        "evidence_sha256": case.evidence_sha256,
    }


def _case_evidence_bytes(case: StudyCaseEvidence) -> bytes:
    return canonical_json_bytes(_case_payload(case))


def _case_evidence_sha256(case: StudyCaseEvidence) -> str:
    return hashlib.sha256(_case_evidence_bytes(case)).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyStudyReplayService:
    """Reconstruct and verify one stored strategy study without a provider."""

    root: Path
    current_commit_resolver: Callable[[], str] = _default_current_commit

    def replay(self, study_id: str) -> StrategyStudyArtifacts:
        """Replay immutable strategy-study metadata and referenced experiments."""

        # Remaining implementation is intentionally unchanged below this file region.
        return self._replay_existing(study_id)

    def _replay_existing(self, study_id: str) -> StrategyStudyArtifacts:
        """Internal existing replay implementation."""

        store = LocalStrategyStudyStore(self.root)
        result_bytes = store.read_artifact(study_id, "result-manifest.json")
        result = _json_object(result_bytes, "strategy study result")
        if set(result) != _RESULT_KEYS:
            raise StudyReplayMismatchError("strategy study result fields changed")
        stored_study_id = _sha256(
            _required_str(result, "study_id", "strategy study result"),
            "strategy study identity",
        )
        if stored_study_id != study_id:
            raise StudyReplayMismatchError("strategy study identity changed")
        classification_value = _required_str(result, "classification", "strategy study result")
        try:
            classification = PromotionClassification(classification_value)
        except ValueError:
            raise StudyReplayMismatchError("invalid strategy study classification") from None
        artifacts_value = result.get("artifacts")
        if not isinstance(artifacts_value, list):
            raise StudyReplayMismatchError("invalid strategy study result artifacts")
        artifact_rows = cast(list[object], artifacts_value)
        artifact_hashes: dict[str, str] = {}
        for raw_row in artifact_rows:
            if not isinstance(raw_row, dict):
                raise StudyReplayMismatchError("invalid strategy study artifact identity")
            row = cast(dict[object, object], raw_row)
            if set(row) != {"name", "sha256"}:
                raise StudyReplayMismatchError("invalid strategy study artifact identity")
            name = row.get("name")
            sha256 = row.get("sha256")
            if not isinstance(name, str) or not isinstance(sha256, str):
                raise StudyReplayMismatchError("invalid strategy study artifact identity")
            artifact_hashes[name] = _sha256(sha256, "strategy study artifact SHA-256")
        expected_names = tuple(
            name for name in REQUIRED_STUDY_ARTIFACT_NAMES if name != "result-manifest.json"
        )
        if tuple(artifact_hashes) != expected_names:
            raise StudyReplayMismatchError("strategy study artifact inventory changed")
        for name, expected_hash in artifact_hashes.items():
            if hashlib.sha256(store.read_artifact(study_id, name)).hexdigest() != expected_hash:
                raise StudyReplayMismatchError(f"strategy study artifact changed: {name}")
        study_manifest = _json_object(
            store.read_artifact(study_id, "study-manifest.json"),
            "strategy study manifest",
        )
        if set(study_manifest) not in {_LEGACY_STUDY_MANIFEST_KEYS, _SEALED_STUDY_MANIFEST_KEYS}:
            raise StudyReplayMismatchError("strategy study manifest fields changed")
        manifest_code_commit = _required_str(
            study_manifest,
            "code_commit",
            "strategy study manifest",
        )
        if _GIT_COMMIT_PATTERN.fullmatch(manifest_code_commit) is None:
            raise StudyReplayMismatchError("invalid strategy study code commit")
        if self.current_commit_resolver() != manifest_code_commit:
            raise StudyReplayMismatchError("strategy study code commit changed")
        experiment_rows = _jsonl_objects(
            store.read_artifact(study_id, "experiments.jsonl"),
            "strategy study experiments",
        )
        cases = tuple(_parse_case(row) for row in experiment_rows)
        for case in cases:
            if _case_evidence_sha256(case) != case.evidence_sha256:
                raise StudyReplayMismatchError("strategy study case evidence identity changed")
        development_ids = tuple(
            case.case_id for case in cases if case.phase is StudyPhase.DEVELOPMENT
        )
        final_ids = tuple(case.case_id for case in cases if case.phase is StudyPhase.FINAL)
        if development_ids and len(development_ids) % len(REQUIRED_DEVELOPMENT_CASE_IDS) == 0:
            for offset in range(0, len(development_ids), len(REQUIRED_DEVELOPMENT_CASE_IDS)):
                if development_ids[offset : offset + len(REQUIRED_DEVELOPMENT_CASE_IDS)] != (
                    REQUIRED_DEVELOPMENT_CASE_IDS
                ):
                    raise StudyReplayMismatchError("development study cases changed")
        if final_ids and final_ids != REQUIRED_FINAL_CASE_IDS:
            raise StudyReplayMismatchError("final study cases changed")
        study_result_id = _sha256(
            _required_str(result, "study_result_id", "strategy study result"),
            "strategy study result identity",
        )
        expected_result_payload = {
            "schema_version": _required_str(result, "schema_version", "strategy study result"),
            "study_id": stored_study_id,
            "artifacts": artifact_rows,
            "classification": classification.value,
        }
        if (
            hashlib.sha256(canonical_json_bytes(expected_result_payload)).hexdigest()
            != study_result_id
        ):
            raise StudyReplayMismatchError("strategy study result identity changed")
        files = tuple((name, store.read_artifact(study_id, name)) for name in expected_names)
        return StrategyStudyArtifacts(
            study_id=stored_study_id,
            study_result_id=study_result_id,
            classification=classification,
            files=files,
        )


__all__ = [
    "SUPPORTED_REPLAY_STRATEGY_IDS",
    "StrategyStudyReplayService",
    "validate_replay_strategy_id",
]
