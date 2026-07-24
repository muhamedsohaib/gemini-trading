"""Content-addressed identities for deterministic strategy studies."""

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from gemini_trading.research.serialization import canonical_json_bytes

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


def component_id(schema_version: str, payload: Mapping[str, object]) -> str:
    """Return a stable SHA-256 identity for one canonical component payload."""

    schema = _identifier(schema_version, "schema_version")
    encoded = canonical_json_bytes(
        {
            "payload": dict(payload),
            "schema_version": schema,
        }
    )
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategyStudyManifest:
    """Every immutable trust-boundary identity for one strategy study."""

    schema_version: str
    dataset_id: str
    canonical_sha256: str
    code_commit: str
    policy_id: str
    simulation_config_id: str
    feature_registry_id: str
    label_policy_id: str
    split_plan_id: str
    random_seed_policy_id: str
    initial_cash: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _identifier(self.schema_version, "schema_version"),
        )
        for field_name in (
            "dataset_id",
            "canonical_sha256",
            "policy_id",
            "simulation_config_id",
            "feature_registry_id",
            "label_policy_id",
            "split_plan_id",
            "random_seed_policy_id",
        ):
            _sha256(getattr(self, field_name), field_name)
        if _GIT_COMMIT_PATTERN.fullmatch(self.code_commit) is None:
            raise ValueError("code_commit must be a 40-character lowercase Git commit")
        if not self.initial_cash.is_finite() or self.initial_cash <= 0:
            raise ValueError("initial_cash must be finite and positive")


def serialize_study_manifest(manifest: StrategyStudyManifest) -> bytes:
    """Return canonical bytes for a complete strategy study manifest."""

    return canonical_json_bytes(
        {
            "canonical_sha256": manifest.canonical_sha256,
            "code_commit": manifest.code_commit,
            "dataset_id": manifest.dataset_id,
            "feature_registry_id": manifest.feature_registry_id,
            "initial_cash": manifest.initial_cash,
            "label_policy_id": manifest.label_policy_id,
            "policy_id": manifest.policy_id,
            "random_seed_policy_id": manifest.random_seed_policy_id,
            "schema_version": manifest.schema_version,
            "simulation_config_id": manifest.simulation_config_id,
            "split_plan_id": manifest.split_plan_id,
        }
    )


def study_id(manifest: StrategyStudyManifest) -> str:
    """Return the content-derived identity of one complete strategy study."""

    return hashlib.sha256(serialize_study_manifest(manifest)).hexdigest()
