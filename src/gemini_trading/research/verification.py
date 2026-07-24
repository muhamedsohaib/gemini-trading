"""Independent verification of stored deterministic research evidence."""

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.errors import ReplayMismatchError
from gemini_trading.research.identity import experiment_id
from gemini_trading.research.replay import (
    ReplayService,
    StrategyReconstructor,
    fixture_strategy_from_manifest,
    parse_experiment_manifest,
    parse_simulation_config,
    resolve_clean_git_commit,
)
from gemini_trading.research.serialization import canonical_json_bytes

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RESULT_KEYS = {
    "schema_version",
    "experiment_id",
    "artifacts",
    "terminal_status",
    "promotable",
    "result_id",
}


def _default_current_commit() -> str:
    return resolve_clean_git_commit(Path.cwd())


def _result_mapping(raw: bytes) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReplayMismatchError("invalid result manifest JSON") from None
    if not isinstance(loaded, dict):
        raise ReplayMismatchError("invalid result manifest JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise ReplayMismatchError("invalid result manifest JSON object")
    result = cast(dict[str, object], mapping)
    if set(result) != _RESULT_KEYS:
        raise ReplayMismatchError("result manifest fields do not match schema")
    return result


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ReplayMismatchError(f"invalid result manifest field: {key}")
    return value


def _artifact_hashes(mapping: dict[str, object]) -> tuple[tuple[str, str], ...]:
    raw_artifacts = mapping.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise ReplayMismatchError("invalid result manifest field: artifacts")
    artifacts: list[tuple[str, str]] = []
    for raw_item in cast(list[object], raw_artifacts):
        if not isinstance(raw_item, list):
            raise ReplayMismatchError("invalid result manifest artifact entry")
        pair = cast(list[object], raw_item)
        if len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            raise ReplayMismatchError("invalid result manifest artifact entry")
        name = cast(str, pair[0])
        digest = cast(str, pair[1])
        if _SHA256_PATTERN.fullmatch(digest) is None:
            raise ReplayMismatchError("invalid result manifest artifact hash")
        artifacts.append((name, digest))
    values = tuple(artifacts)
    if values != tuple(sorted(values)) or len(values) != len(set(values)):
        raise ReplayMismatchError("result manifest artifact entries are not uniquely sorted")
    return values


@dataclass(frozen=True, slots=True)
class ResearchVerificationResult:
    """Safe deterministic verification summary for one completed experiment."""

    experiment_id: str
    result_id: str
    terminal_status: str
    promotable: bool
    checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchVerificationService:
    """Verify persisted evidence, replay it offline, and compare every core byte."""

    root: Path
    current_commit_resolver: Callable[[], str] = _default_current_commit
    strategy_reconstructor: StrategyReconstructor = fixture_strategy_from_manifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def verify(self, experiment_id_value: str) -> ResearchVerificationResult:
        """Fail closed unless stored evidence and deterministic replay agree."""

        research_store = LocalResearchStore(self.root)
        canonical_store = LocalImmutableStore(self.root)
        try:
            result_manifest_bytes = research_store.read_artifact(
                experiment_id_value,
                "result-manifest.json",
            )
            experiment_manifest_bytes = research_store.read_artifact(
                experiment_id_value,
                "experiment-manifest.json",
            )
            simulation_config_bytes = research_store.read_artifact(
                experiment_id_value,
                "simulation-config.json",
            )
        except (OSError, ValueError):
            raise ReplayMismatchError("required verification evidence is missing") from None

        result_mapping = _result_mapping(result_manifest_bytes)
        if _required_str(result_mapping, "schema_version") != "research-result-v2":
            raise ReplayMismatchError("unsupported result manifest schema")
        if _required_str(result_mapping, "experiment_id") != experiment_id_value:
            raise ReplayMismatchError("result manifest experiment identity mismatch")
        terminal_status = _required_str(result_mapping, "terminal_status")
        if terminal_status != "completed":
            raise ReplayMismatchError("result manifest is not completed")
        promotable_value = result_mapping.get("promotable")
        if not isinstance(promotable_value, bool):
            raise ReplayMismatchError("invalid result manifest field: promotable")
        recorded_result_id = _required_str(result_mapping, "result_id")
        if _SHA256_PATTERN.fullmatch(recorded_result_id) is None:
            raise ReplayMismatchError("invalid result identity")

        manifest = parse_experiment_manifest(experiment_manifest_bytes)
        if experiment_id(manifest) != experiment_id_value:
            raise ReplayMismatchError("experiment identity does not match manifest")
        config = parse_simulation_config(simulation_config_bytes)
        if hashlib.sha256(simulation_config_bytes).hexdigest() != (
            manifest.simulation_config_sha256
        ):
            raise ReplayMismatchError("simulation configuration hash does not match manifest")
        if config.promotable != promotable_value:
            raise ReplayMismatchError("promotion evidence classification mismatch")

        artifact_hashes = _artifact_hashes(result_mapping)
        for name, expected_hash in artifact_hashes:
            try:
                content = research_store.read_artifact(experiment_id_value, name)
            except (OSError, ValueError):
                raise ReplayMismatchError(f"stored artifact is missing: {name}") from None
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ReplayMismatchError(f"stored artifact hash does not match: {name}")

        identity_payload: dict[str, object] = {
            "schema_version": "research-result-v2",
            "experiment_id": experiment_id_value,
            "artifacts": [list(item) for item in artifact_hashes],
            "terminal_status": terminal_status,
            "promotable": promotable_value,
        }
        recomputed_result_id = hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest()
        if recomputed_result_id != recorded_result_id:
            raise ReplayMismatchError("result identity does not match artifact hashes")
        if canonical_json_bytes({**identity_payload, "result_id": recorded_result_id}) != (
            result_manifest_bytes
        ):
            raise ReplayMismatchError("result manifest canonical bytes do not match")

        replayed = ReplayService(
            canonical_store,
            research_store,
            current_commit_resolver=self.current_commit_resolver,
            strategy_reconstructor=self.strategy_reconstructor,
        ).replay(experiment_id_value)
        if replayed.result_id != recorded_result_id:
            raise ReplayMismatchError("replayed result identity does not match")

        checks = tuple(
            sorted(
                {
                    "accounting_reconciled",
                    "artifact_hashes_verified",
                    "dataset_verified",
                    "experiment_identity_verified",
                    "metrics_recomputed",
                    "referential_integrity_verified",
                    "replay_equivalent",
                    "result_identity_verified",
                    "simulation_configuration_verified",
                }
            )
        )
        return ResearchVerificationResult(
            experiment_id=experiment_id_value,
            result_id=recorded_result_id,
            terminal_status=terminal_status,
            promotable=promotable_value,
            checks=checks,
        )


__all__ = ["ResearchVerificationResult", "ResearchVerificationService"]
