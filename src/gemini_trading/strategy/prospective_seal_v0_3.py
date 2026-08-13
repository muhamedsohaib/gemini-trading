"""Prospective-final seal for independently verified Candidate v0.3 qualification evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.entry_selectivity import EntrySelectivityPolicy
from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy
from gemini_trading.strategy.prospective_final import ProspectiveFinalWindow
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_artifacts_v0_3 import V03QualificationArtifacts

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "candidate-v0.3-prospective-final-seal-v1"
_QUALIFICATION_SCHEMA = "candidate-v0.3-qualification-result-v1"
_STRATEGY_ID = "candidate.multi_model.v0_3"
_POLICY_VERSION = "candidate-multi-model-v0.3"
_DEVELOPMENT_CUTOFF = datetime(2026, 8, 1, tzinfo=UTC)


def _verification_milestone_utc() -> datetime:
    """Observe sealing time internally after independent verification succeeds."""

    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class V03ProspectiveFinalSeal:
    """Canonical future-window identity containing no market rows or performance."""

    schema_version: str
    seal_id: str
    strategy_id: str
    policy_version: str
    code_commit: str
    dataset_id: str
    dataset_handoff_inventory_root: str
    policy_sha256: str
    selectivity_policy_sha256: str
    qualification_id: str
    qualification_inventory_root: str
    workflow_run_id: int
    workflow_run_attempt: int
    verified_at: datetime
    development_cutoff: datetime
    bridge_start: datetime
    bridge_end: datetime
    final_start: datetime
    final_end: datetime

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA:
            raise FinalAccessError("unsupported v0.3 prospective seal schema")
        if self.strategy_id != _STRATEGY_ID or self.policy_version != _POLICY_VERSION:
            raise FinalAccessError("v0.3 prospective seal candidate identity changed")
        if _GIT_SHA.fullmatch(self.code_commit) is None:
            raise FinalAccessError("invalid v0.3 prospective seal source commit")
        for field_name in (
            "dataset_id",
            "dataset_handoff_inventory_root",
            "policy_sha256",
            "selectivity_policy_sha256",
            "qualification_id",
            "qualification_inventory_root",
        ):
            if _SHA256.fullmatch(getattr(self, field_name)) is None:
                raise FinalAccessError(f"invalid v0.3 prospective seal {field_name}")
        for field_name in ("workflow_run_id", "workflow_run_attempt"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 1:
                raise FinalAccessError(f"invalid v0.3 prospective seal {field_name}")
        if self.development_cutoff != _DEVELOPMENT_CUTOFF:
            raise FinalAccessError("v0.3 prospective seal development cutoff changed")
        try:
            expected = ProspectiveFinalWindow.from_verified_at(
                development_cutoff=self.development_cutoff,
                verified_at=self.verified_at,
            )
        except ValueError as error:
            raise FinalAccessError(str(error)) from None
        if (
            self.bridge_start != expected.bridge_start
            or self.bridge_end != expected.bridge_end
            or self.final_start != expected.final_start
            or self.final_end != expected.final_end
        ):
            raise FinalAccessError("v0.3 prospective seal window changed")
        if _SHA256.fullmatch(self.seal_id) is None:
            raise FinalAccessError("invalid v0.3 prospective seal ID")
        if _seal_id(_seal_core(self)) != self.seal_id:
            raise FinalAccessError("v0.3 prospective seal identity mismatch")


def _mapping(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FinalAccessError(f"invalid v0.3 {description} JSON") from None
    if not isinstance(loaded, dict):
        raise FinalAccessError(f"invalid v0.3 {description} JSON")
    return cast(dict[str, object], loaded)


def _locked_artifact_identities(artifacts: V03QualificationArtifacts) -> tuple[str, str]:
    if artifacts.classification is not QualificationClassification.QUALIFIED:
        raise FinalAccessError("v0.3 prospective seal requires QUALIFIED evidence")
    mapping = dict(artifacts.files)
    required = {
        "configuration.json",
        "entry-selectivity-policy.json",
        "policy.json",
        "qualification-manifest.json",
        "qualification-result.json",
    }
    if not required.issubset(mapping):
        raise FinalAccessError("v0.3 qualification evidence required for sealing is incomplete")

    policy_bytes = serialize_candidate_policy(CandidatePolicy.locked_v0_3())
    selectivity_bytes = canonical_json_bytes(asdict(EntrySelectivityPolicy.locked_v0_3()))
    if mapping["policy.json"] != policy_bytes:
        raise FinalAccessError("v0.3 prospective seal policy identity changed")
    if mapping["entry-selectivity-policy.json"] != selectivity_bytes:
        raise FinalAccessError("v0.3 prospective seal selectivity identity changed")
    policy_sha = hashlib.sha256(policy_bytes).hexdigest()
    selectivity_sha = hashlib.sha256(selectivity_bytes).hexdigest()

    manifest = _mapping(mapping["qualification-manifest.json"], "qualification manifest")
    if manifest.get("schema_version") != _QUALIFICATION_SCHEMA:
        raise FinalAccessError("v0.3 qualification schema is not sealable")
    if manifest.get("classification") != QualificationClassification.QUALIFIED.value:
        raise FinalAccessError("v0.3 prospective seal requires QUALIFIED evidence")
    if manifest.get("policy_sha256") != policy_sha:
        raise FinalAccessError("v0.3 prospective seal policy hash changed")
    if manifest.get("selectivity_policy_sha256") != selectivity_sha:
        raise FinalAccessError("v0.3 prospective seal selectivity hash changed")
    if manifest.get("context") != asdict(artifacts.context):
        raise FinalAccessError("v0.3 qualification context is not bound to the verified artifact")

    config = _mapping(mapping["configuration.json"], "qualification configuration")
    if (
        config.get("schema_version") != "candidate-v0.3-qualification-config-v1"
        or config.get("dataset_id") != artifacts.context.dataset_id
        or config.get("development_start") != "2018-01-01T00:00:00Z"
        or config.get("development_end_exclusive") != "2026-08-01T00:00:00Z"
        or config.get("strategy_id") != _STRATEGY_ID
        or config.get("policy_version") != _POLICY_VERSION
        or config.get("selectivity_policy_sha256") != selectivity_sha
    ):
        raise FinalAccessError("v0.3 qualification configuration is not sealable")
    return policy_sha, selectivity_sha


def _seal_core(seal: V03ProspectiveFinalSeal) -> dict[str, object]:
    return {key: value for key, value in asdict(seal).items() if key != "seal_id"}


def _seal_id(core: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def create_v0_3_prospective_seal(
    artifacts: V03QualificationArtifacts,
) -> V03ProspectiveFinalSeal:
    """Create a future-only seal from already independently verified QUALIFIED evidence."""

    policy_sha, selectivity_sha = _locked_artifact_identities(artifacts)
    verified_at = _verification_milestone_utc()
    try:
        window = ProspectiveFinalWindow.from_verified_at(
            development_cutoff=_DEVELOPMENT_CUTOFF,
            verified_at=verified_at,
        )
    except ValueError as error:
        raise FinalAccessError(str(error)) from None
    core: dict[str, object] = {
        "schema_version": _SCHEMA,
        "strategy_id": _STRATEGY_ID,
        "policy_version": _POLICY_VERSION,
        "code_commit": artifacts.context.code_commit,
        "dataset_id": artifacts.context.dataset_id,
        "dataset_handoff_inventory_root": artifacts.context.dataset_handoff_inventory_root,
        "policy_sha256": policy_sha,
        "selectivity_policy_sha256": selectivity_sha,
        "qualification_id": artifacts.qualification_id,
        "qualification_inventory_root": artifacts.inventory_root_sha256,
        "workflow_run_id": artifacts.context.workflow_run_id,
        "workflow_run_attempt": artifacts.context.workflow_run_attempt,
        "verified_at": verified_at,
        "development_cutoff": _DEVELOPMENT_CUTOFF,
        "bridge_start": window.bridge_start,
        "bridge_end": window.bridge_end,
        "final_start": window.final_start,
        "final_end": window.final_end,
    }
    seal_id = _seal_id(core)
    return V03ProspectiveFinalSeal(
        schema_version=_SCHEMA,
        seal_id=seal_id,
        strategy_id=_STRATEGY_ID,
        policy_version=_POLICY_VERSION,
        code_commit=artifacts.context.code_commit,
        dataset_id=artifacts.context.dataset_id,
        dataset_handoff_inventory_root=artifacts.context.dataset_handoff_inventory_root,
        policy_sha256=policy_sha,
        selectivity_policy_sha256=selectivity_sha,
        qualification_id=artifacts.qualification_id,
        qualification_inventory_root=artifacts.inventory_root_sha256,
        workflow_run_id=artifacts.context.workflow_run_id,
        workflow_run_attempt=artifacts.context.workflow_run_attempt,
        verified_at=verified_at,
        development_cutoff=_DEVELOPMENT_CUTOFF,
        bridge_start=window.bridge_start,
        bridge_end=window.bridge_end,
        final_start=window.final_start,
        final_end=window.final_end,
    )


def serialize_v0_3_prospective_final_seal(seal: V03ProspectiveFinalSeal) -> bytes:
    """Serialize one canonical v0.3 future-window seal."""

    return canonical_json_bytes({**_seal_core(seal), "seal_id": seal.seal_id})


@dataclass(frozen=True, slots=True)
class V03LocalProspectiveFinalSealStore:
    """Fail-closed store permitting one immutable seal for Candidate v0.3."""

    root: Path

    def _candidate_directory(self) -> Path:
        return self.root / "data" / "historical-validation" / "v0-3-prospective-final"

    def _seal_path(self, seal_id: str) -> Path:
        if _SHA256.fullmatch(seal_id) is None:
            raise FinalAccessError("invalid v0.3 prospective seal ID")
        return self._candidate_directory() / "seals" / seal_id / "prospective-final-seal.json"

    def create(self, artifacts: V03QualificationArtifacts) -> V03ProspectiveFinalSeal:
        """Create exactly one immutable Candidate v0.3 future-window seal."""

        seal = create_v0_3_prospective_seal(artifacts)
        candidate = self._candidate_directory()
        marker = candidate / "active-seal"
        candidate.mkdir(parents=True, exist_ok=True)
        try:
            marker.mkdir(exist_ok=False)
        except FileExistsError:
            raise FinalAccessError("v0.3 prospective final seal already exists") from None
        write_immutable(self._seal_path(seal.seal_id), serialize_v0_3_prospective_final_seal(seal))
        write_immutable(marker / "seal-id.txt", f"{seal.seal_id}\n".encode())
        return seal

    def load(self, seal_id: str) -> V03ProspectiveFinalSeal:
        """Load and fully validate one canonical v0.3 prospective seal."""

        try:
            raw = self._seal_path(seal_id).read_bytes()
        except OSError:
            raise FinalAccessError("v0.3 prospective final seal is missing") from None
        mapping = _mapping(raw, "prospective seal")
        try:
            seal = V03ProspectiveFinalSeal(
                schema_version=cast(str, mapping["schema_version"]),
                seal_id=cast(str, mapping["seal_id"]),
                strategy_id=cast(str, mapping["strategy_id"]),
                policy_version=cast(str, mapping["policy_version"]),
                code_commit=cast(str, mapping["code_commit"]),
                dataset_id=cast(str, mapping["dataset_id"]),
                dataset_handoff_inventory_root=cast(
                    str, mapping["dataset_handoff_inventory_root"]
                ),
                policy_sha256=cast(str, mapping["policy_sha256"]),
                selectivity_policy_sha256=cast(str, mapping["selectivity_policy_sha256"]),
                qualification_id=cast(str, mapping["qualification_id"]),
                qualification_inventory_root=cast(str, mapping["qualification_inventory_root"]),
                workflow_run_id=cast(int, mapping["workflow_run_id"]),
                workflow_run_attempt=cast(int, mapping["workflow_run_attempt"]),
                verified_at=datetime.fromisoformat(
                    cast(str, mapping["verified_at"]).replace("Z", "+00:00")
                ),
                development_cutoff=datetime.fromisoformat(
                    cast(str, mapping["development_cutoff"]).replace("Z", "+00:00")
                ),
                bridge_start=datetime.fromisoformat(
                    cast(str, mapping["bridge_start"]).replace("Z", "+00:00")
                ),
                bridge_end=datetime.fromisoformat(
                    cast(str, mapping["bridge_end"]).replace("Z", "+00:00")
                ),
                final_start=datetime.fromisoformat(
                    cast(str, mapping["final_start"]).replace("Z", "+00:00")
                ),
                final_end=datetime.fromisoformat(
                    cast(str, mapping["final_end"]).replace("Z", "+00:00")
                ),
            )
        except (KeyError, TypeError, ValueError):
            raise FinalAccessError("invalid v0.3 prospective seal fields") from None
        if seal.seal_id != seal_id or serialize_v0_3_prospective_final_seal(seal) != raw:
            raise FinalAccessError("v0.3 prospective final seal encoding changed")
        return seal


__all__ = [
    "V03LocalProspectiveFinalSealStore",
    "V03ProspectiveFinalSeal",
    "create_v0_3_prospective_seal",
    "serialize_v0_3_prospective_final_seal",
]
