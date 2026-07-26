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
    "excluded_provider_row_sha256",
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


@dataclass(frozen=True, slots=True)
class StoredStrategyStudyManifest:
    """Strict canonical study-level trust-boundary manifest."""

    study_id: str
    split_plan_sha256: str
    policy_sha256: str
    configuration_sha256: str
    code_commit: str
    final_test_receipt_id: str
    final_evaluation_count: int
    pre_final_id: str | None = None
    dataset_handoff_inventory_root: str | None = None
    durable_final_access_receipt_id: str | None = None
    dataset_schema_version: str | None = None
    closure_manifest_sha256: str | None = None
    exclusion_manifest_sha256: str | None = None
    segment_manifest_sha256: str | None = None
    closure_count: int | None = None
    exclusion_count: int | None = None
    segment_count: int | None = None
    closure_ids: tuple[str, ...] = ()
    excluded_provider_row_sha256: str | None = None
    segment_boundary_indices: tuple[int, ...] = ()


def parse_study_manifest(raw: bytes) -> StoredStrategyStudyManifest:
    """Parse either the exact legacy schema or exact sealed extension."""

    mapping = _json_object(raw, "strategy study manifest")
    fields = set(mapping)
    valid_fields = {
        frozenset(_LEGACY_STUDY_MANIFEST_KEYS),
        frozenset(_SEALED_STUDY_MANIFEST_KEYS),
    }
    if frozenset(fields) not in valid_fields:
        raise StudyReplayMismatchError("strategy study manifest fields do not match schema")
    sealed = fields == _SEALED_STUDY_MANIFEST_KEYS
    if _required_str(mapping, "schema_version", "strategy study manifest") != "strategy-study-v1":
        raise StudyReplayMismatchError("unsupported strategy study manifest schema")
    manifest = StoredStrategyStudyManifest(
        study_id=_sha256(
            _required_str(mapping, "study_id", "strategy study manifest"),
            "strategy study identity",
        ),
        split_plan_sha256=_sha256(
            _required_str(mapping, "split_plan_sha256", "strategy study manifest"),
            "split plan identity",
        ),
        policy_sha256=_sha256(
            _required_str(mapping, "policy_sha256", "strategy study manifest"),
            "policy identity",
        ),
        configuration_sha256=_sha256(
            _required_str(mapping, "configuration_sha256", "strategy study manifest"),
            "configuration identity",
        ),
        code_commit=_required_str(mapping, "code_commit", "strategy study manifest"),
        final_test_receipt_id=_sha256(
            _required_str(mapping, "final_test_receipt_id", "strategy study manifest"),
            "final test receipt identity",
        ),
        final_evaluation_count=_required_int(
            mapping,
            "final_evaluation_count",
            "strategy study manifest",
        ),
        pre_final_id=(
            _sha256(
                _required_str(mapping, "pre_final_id", "strategy study manifest"),
                "pre-final identity",
            )
            if sealed
            else None
        ),
        dataset_handoff_inventory_root=(
            _sha256(
                _required_str(
                    mapping,
                    "dataset_handoff_inventory_root",
                    "strategy study manifest",
                ),
                "dataset handoff inventory root",
            )
            if sealed
            else None
        ),
        durable_final_access_receipt_id=(
            _sha256(
                _required_str(
                    mapping,
                    "durable_final_access_receipt_id",
                    "strategy study manifest",
                ),
                "durable final-access receipt identity",
            )
            if sealed
            else None
        ),
        dataset_schema_version=(
            _required_str(mapping, "dataset_schema_version", "strategy study manifest")
            if sealed
            else None
        ),
        closure_manifest_sha256=(
            _sha256(
                _required_str(mapping, "closure_manifest_sha256", "strategy study manifest"),
                "closure manifest identity",
            )
            if sealed
            else None
        ),
        exclusion_manifest_sha256=(
            _sha256(
                _required_str(mapping, "exclusion_manifest_sha256", "strategy study manifest"),
                "exclusion manifest identity",
            )
            if sealed
            else None
        ),
        segment_manifest_sha256=(
            _sha256(
                _required_str(mapping, "segment_manifest_sha256", "strategy study manifest"),
                "segment manifest identity",
            )
            if sealed
            else None
        ),
        closure_count=(
            _required_int(mapping, "closure_count", "strategy study manifest") if sealed else None
        ),
        exclusion_count=(
            _required_int(mapping, "exclusion_count", "strategy study manifest") if sealed else None
        ),
        segment_count=(
            _required_int(mapping, "segment_count", "strategy study manifest") if sealed else None
        ),
        closure_ids=(
            _required_string_tuple(mapping, "closure_ids", "strategy study manifest")
            if sealed
            else ()
        ),
        excluded_provider_row_sha256=(
            _sha256(
                _required_str(
                    mapping,
                    "excluded_provider_row_sha256",
                    "strategy study manifest",
                ),
                "excluded provider-row identity",
            )
            if sealed
            else None
        ),
        segment_boundary_indices=(
            _required_positive_int_tuple(
                mapping, "segment_boundary_indices", "strategy study manifest"
            )
            if sealed
            else ()
        ),
    )
    if _GIT_COMMIT_PATTERN.fullmatch(manifest.code_commit) is None:
        raise StudyReplayMismatchError("invalid strategy study code commit")
    if manifest.final_evaluation_count != 1:
        raise StudyReplayMismatchError("final-test receipt must record exactly one evaluation")
    if sealed:
        if manifest.dataset_schema_version != "candle-dataset-v3":
            raise StudyReplayMismatchError("sealed study requires candle-dataset-v3")
        if manifest.closure_count is None or manifest.closure_count < 1:
            raise StudyReplayMismatchError("invalid sealed study closure count")
        if manifest.exclusion_count != manifest.closure_count:
            raise StudyReplayMismatchError("invalid sealed study exclusion count")
        if manifest.segment_count != manifest.closure_count + 1:
            raise StudyReplayMismatchError("invalid sealed study segment count")
        if manifest.excluded_provider_row_sha256 is None:
            raise StudyReplayMismatchError("sealed study lacks excluded row identity")
        if len(manifest.closure_ids) != manifest.closure_count:
            raise StudyReplayMismatchError("invalid sealed study closure IDs")
        if len(manifest.segment_boundary_indices) != manifest.closure_count:
            raise StudyReplayMismatchError("invalid sealed study segment boundaries")
    if canonical_json_bytes(mapping) != raw:
        raise StudyReplayMismatchError("strategy study manifest canonical bytes do not match")
    return manifest


def parse_study_case_evidence(raw: bytes) -> tuple[StudyCaseEvidence, ...]:
    """Parse and complete-check every referenced development and final case."""

    records: list[StudyCaseEvidence] = []
    for mapping in _jsonl_objects(raw, "strategy study experiments"):
        if set(mapping) != _CASE_KEYS:
            raise StudyReplayMismatchError("strategy study experiment fields do not match schema")
        fold_value = mapping.get("fold_number")
        if fold_value is not None and (
            isinstance(fold_value, bool) or not isinstance(fold_value, int)
        ):
            raise StudyReplayMismatchError("invalid strategy study experiment fold_number")
        try:
            records.append(
                StudyCaseEvidence(
                    case_id=_required_str(mapping, "case_id", "strategy study experiment"),
                    phase=StudyPhase(_required_str(mapping, "phase", "strategy study experiment")),
                    fold_number=fold_value,
                    terminal_status=_required_str(
                        mapping,
                        "terminal_status",
                        "strategy study experiment",
                    ),
                    experiment_id=_required_str(
                        mapping,
                        "experiment_id",
                        "strategy study experiment",
                    ),
                    evidence_sha256=_required_str(
                        mapping,
                        "evidence_sha256",
                        "strategy study experiment",
                    ),
                )
            )
        except ValueError as error:
            raise StudyReplayMismatchError(f"invalid strategy study experiment: {error}") from None

    grouped: dict[int, list[StudyCaseEvidence]] = {}
    final_records: list[StudyCaseEvidence] = []
    for record in records:
        if record.phase is StudyPhase.DEVELOPMENT:
            if record.fold_number is None:
                raise StudyReplayMismatchError("development experiment is missing fold identity")
            grouped.setdefault(record.fold_number, []).append(record)
        else:
            final_records.append(record)
    if not grouped:
        raise StudyReplayMismatchError("strategy study has no development folds")
    required_development = set(REQUIRED_DEVELOPMENT_CASE_IDS)
    for fold_number, fold_records in grouped.items():
        case_ids = tuple(item.case_id for item in fold_records)
        if set(case_ids) != required_development or len(case_ids) != len(required_development):
            raise StudyReplayMismatchError(
                f"strategy study development evidence is incomplete for fold {fold_number}"
            )
    final_case_ids = tuple(item.case_id for item in final_records)
    if set(final_case_ids) != set(REQUIRED_FINAL_CASE_IDS) or len(final_case_ids) != len(
        REQUIRED_FINAL_CASE_IDS
    ):
        raise StudyReplayMismatchError("strategy study final evidence is incomplete")
    active_ids = set(SUPPORTED_REPLAY_STRATEGY_IDS) - {"fixture.scripted.v1"}
    if not active_ids.issubset({item.case_id for item in records}):
        raise StudyReplayMismatchError("strategy study replay registry evidence is incomplete")
    for strategy_id in sorted(active_ids):
        validate_replay_strategy_id(strategy_id)
    return tuple(records)


def _artifact_hashes(mapping: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    raw_artifacts = mapping.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise StudyReplayMismatchError("invalid strategy study result artifacts")
    values: list[tuple[str, str]] = []
    for raw_item in cast(list[object], raw_artifacts):
        if not isinstance(raw_item, list):
            raise StudyReplayMismatchError("invalid strategy study result artifact entry")
        pair = cast(list[object], raw_item)
        if len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            raise StudyReplayMismatchError("invalid strategy study result artifact entry")
        values.append(
            (
                cast(str, pair[0]),
                _sha256(cast(str, pair[1]), "strategy study artifact hash"),
            )
        )
    result = tuple(values)
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        raise StudyReplayMismatchError("strategy study result artifacts are not uniquely sorted")
    expected_names = tuple(
        name for name in REQUIRED_STUDY_ARTIFACT_NAMES if name != "study-result-manifest.json"
    )
    if tuple(name for name, _ in result) != expected_names:
        raise StudyReplayMismatchError("strategy study result artifact names are incomplete")
    return result


@dataclass(frozen=True, slots=True)
class StrategyStudyReplayService:
    """Reconstruct one stored study from canonical bytes without provider access."""

    root: Path
    current_commit_resolver: Callable[[], str] = _default_current_commit

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def replay(self, study_id: str) -> StrategyStudyArtifacts:
        """Fail closed unless every stored artifact and identity is canonical."""

        _sha256(study_id, "strategy study identity")
        store = LocalStrategyStudyStore(self.root)
        files: list[tuple[str, bytes]] = []
        for name in REQUIRED_STUDY_ARTIFACT_NAMES:
            try:
                files.append((name, store.read_artifact(study_id, name)))
            except (OSError, ValueError):
                raise StudyReplayMismatchError(
                    f"required strategy study replay artifact is missing: {name}"
                ) from None
        file_mapping = dict(files)
        result_bytes = file_mapping["study-result-manifest.json"]
        result_mapping = _json_object(result_bytes, "strategy study result manifest")
        if set(result_mapping) != _RESULT_KEYS:
            raise StudyReplayMismatchError(
                "strategy study result manifest fields do not match schema"
            )
        if (
            _required_str(result_mapping, "schema_version", "strategy study result manifest")
            != "strategy-study-result-v1"
        ):
            raise StudyReplayMismatchError("unsupported strategy study result schema")
        if _required_str(result_mapping, "study_id", "strategy study result manifest") != study_id:
            raise StudyReplayMismatchError("strategy study result identity does not match study")
        try:
            classification = PromotionClassification(
                _required_str(result_mapping, "classification", "strategy study result manifest")
            )
        except ValueError:
            raise StudyReplayMismatchError("invalid strategy study classification") from None
        artifact_hashes = _artifact_hashes(result_mapping)
        for name, expected_hash in artifact_hashes:
            if hashlib.sha256(file_mapping[name]).hexdigest() != expected_hash:
                raise StudyReplayMismatchError(
                    f"strategy study artifact hash does not match: {name}"
                )
        identity_payload: dict[str, object] = {
            "schema_version": "strategy-study-result-v1",
            "study_id": study_id,
            "artifacts": [list(item) for item in artifact_hashes],
            "classification": classification.value,
        }
        result_id = hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest()
        recorded_result_id = _required_str(
            result_mapping,
            "study_result_id",
            "strategy study result manifest",
        )
        if result_id != recorded_result_id:
            raise StudyReplayMismatchError(
                "strategy study result identity does not match artifacts"
            )
        if canonical_json_bytes({**identity_payload, "study_result_id": result_id}) != result_bytes:
            raise StudyReplayMismatchError(
                "strategy study result manifest canonical bytes do not match"
            )
        manifest = parse_study_manifest(file_mapping["study-manifest.json"])
        if manifest.study_id != study_id:
            raise StudyReplayMismatchError("strategy study identity does not match manifest")
        if self.current_commit_resolver() != manifest.code_commit:
            raise StudyReplayMismatchError("code commit does not match strategy study manifest")
        parse_study_case_evidence(file_mapping["experiments.jsonl"])
        return StrategyStudyArtifacts(
            study_id=study_id,
            study_result_id=result_id,
            classification=classification,
            files=tuple(files),
        )


__all__ = [
    "SUPPORTED_REPLAY_STRATEGY_IDS",
    "StoredStrategyStudyManifest",
    "StrategyStudyReplayService",
    "parse_study_case_evidence",
    "parse_study_manifest",
    "validate_replay_strategy_id",
]
