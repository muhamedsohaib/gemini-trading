"""Durable single-use authorization for sealed final-test access."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import FinalAccessError, HistoricalValidationError
from gemini_trading.strategy.handoff import ArtifactInventoryEntry, build_artifact_inventory

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_RECEIPT_SCHEMA = "durable-final-access-v1"
_SEAL_SCHEMA = "durable-final-seal-v1"
_IDENTITY_FIELDS = {
    "code_commit",
    "dataset_id",
    "configuration_sha256",
    "policy_sha256",
    "split_plan_sha256",
    "pre_final_id",
    "workflow_run_id",
    "workflow_run_attempt",
}
_STABLE_IDENTITY_FIELDS = {
    "code_commit",
    "dataset_id",
    "configuration_sha256",
    "policy_sha256",
    "split_plan_sha256",
    "pre_final_id",
}
_RECEIPT_FIELDS = {"schema_version", "identity", "evaluation_count", "receipt_id"}
_SEAL_FIELDS = {"schema_version", "identity", "seal_id", "receipt_id"}


def _sha256(value: str, field_name: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise FinalAccessError(f"invalid {field_name}")
    return value


def _positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or value < 1:
        raise FinalAccessError(f"invalid {field_name}")
    return value


@dataclass(frozen=True, slots=True)
class FinalAccessIdentity:
    """Every immutable identity required to open one sealed final partition."""

    code_commit: str
    dataset_id: str
    configuration_sha256: str
    policy_sha256: str
    split_plan_sha256: str
    pre_final_id: str
    workflow_run_id: int
    workflow_run_attempt: int

    def __post_init__(self) -> None:
        if _GIT_COMMIT_PATTERN.fullmatch(self.code_commit) is None:
            raise FinalAccessError("invalid code commit")
        _sha256(self.dataset_id, "dataset ID")
        _sha256(self.configuration_sha256, "configuration SHA-256")
        _sha256(self.policy_sha256, "policy SHA-256")
        _sha256(self.split_plan_sha256, "split-plan SHA-256")
        _sha256(self.pre_final_id, "pre-final ID")
        _positive_int(self.workflow_run_id, "workflow run ID")
        _positive_int(self.workflow_run_attempt, "workflow run attempt")


@dataclass(frozen=True, slots=True)
class DurableFinalAccessReceipt:
    """Canonical evidence that one exact final-test identity was authorized once."""

    schema_version: str
    identity: FinalAccessIdentity
    evaluation_count: int
    receipt_id: str

    def __post_init__(self) -> None:
        if self.schema_version != _RECEIPT_SCHEMA:
            raise FinalAccessError("unsupported final-access receipt schema")
        if self.evaluation_count != 1:
            raise FinalAccessError("final-access receipt must record exactly one evaluation")
        _sha256(self.receipt_id, "receipt ID")
        if (
            _receipt_id(self.schema_version, self.identity, self.evaluation_count)
            != self.receipt_id
        ):
            raise FinalAccessError("final-access receipt identity mismatch")


class ResumeDecision(StrEnum):
    """Closed exact-resume outcomes."""

    ALLOWED = "allowed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ExactResumeAssessment:
    """Provider-free decision for continuing from complete immutable final outputs."""

    decision: ResumeDecision
    checks: tuple[str, ...]


def _identity_payload(identity: FinalAccessIdentity) -> dict[str, object]:
    return {
        "code_commit": identity.code_commit,
        "dataset_id": identity.dataset_id,
        "configuration_sha256": identity.configuration_sha256,
        "policy_sha256": identity.policy_sha256,
        "split_plan_sha256": identity.split_plan_sha256,
        "pre_final_id": identity.pre_final_id,
        "workflow_run_id": identity.workflow_run_id,
        "workflow_run_attempt": identity.workflow_run_attempt,
    }


def _stable_identity_payload(identity: FinalAccessIdentity) -> dict[str, object]:
    return {
        "code_commit": identity.code_commit,
        "dataset_id": identity.dataset_id,
        "configuration_sha256": identity.configuration_sha256,
        "policy_sha256": identity.policy_sha256,
        "split_plan_sha256": identity.split_plan_sha256,
        "pre_final_id": identity.pre_final_id,
    }


def _receipt_core_payload(
    schema_version: str,
    identity: FinalAccessIdentity,
    evaluation_count: int,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "identity": _identity_payload(identity),
        "evaluation_count": evaluation_count,
    }


def _receipt_id(
    schema_version: str,
    identity: FinalAccessIdentity,
    evaluation_count: int,
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(_receipt_core_payload(schema_version, identity, evaluation_count))
    ).hexdigest()


def final_access_seal_id(identity: FinalAccessIdentity) -> str:
    """Return the stable run-independent identity of one sealed final evaluation."""

    return hashlib.sha256(canonical_json_bytes(_stable_identity_payload(identity))).hexdigest()


def serialize_receipt(receipt: DurableFinalAccessReceipt) -> bytes:
    """Serialize one receipt using exact canonical JSON bytes."""

    return canonical_json_bytes(
        {
            **_receipt_core_payload(
                receipt.schema_version,
                receipt.identity,
                receipt.evaluation_count,
            ),
            "receipt_id": receipt.receipt_id,
        }
    )


def _seal_bytes(receipt: DurableFinalAccessReceipt) -> bytes:
    return canonical_json_bytes(
        {
            "schema_version": _SEAL_SCHEMA,
            "identity": _stable_identity_payload(receipt.identity),
            "seal_id": final_access_seal_id(receipt.identity),
            "receipt_id": receipt.receipt_id,
        }
    )


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FinalAccessError(f"invalid {description}")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise FinalAccessError(f"invalid {description}")
    return cast(dict[str, object], raw)


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise FinalAccessError(f"invalid final-access field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise FinalAccessError(f"invalid final-access field: {key}")
    return value


def load_receipt(raw: bytes) -> DurableFinalAccessReceipt:
    """Parse exact receipt bytes and reject extra fields or alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FinalAccessError("invalid final-access receipt JSON") from None
    mapping = _mapping(loaded, "final-access receipt")
    if set(mapping) != _RECEIPT_FIELDS:
        raise FinalAccessError("invalid final-access receipt fields")
    identity_mapping = _mapping(mapping.get("identity"), "final-access identity")
    if set(identity_mapping) != _IDENTITY_FIELDS:
        raise FinalAccessError("invalid final-access identity fields")
    identity = FinalAccessIdentity(
        code_commit=_string(identity_mapping, "code_commit"),
        dataset_id=_string(identity_mapping, "dataset_id"),
        configuration_sha256=_string(identity_mapping, "configuration_sha256"),
        policy_sha256=_string(identity_mapping, "policy_sha256"),
        split_plan_sha256=_string(identity_mapping, "split_plan_sha256"),
        pre_final_id=_string(identity_mapping, "pre_final_id"),
        workflow_run_id=_integer(identity_mapping, "workflow_run_id"),
        workflow_run_attempt=_integer(identity_mapping, "workflow_run_attempt"),
    )
    receipt = DurableFinalAccessReceipt(
        schema_version=_string(mapping, "schema_version"),
        identity=identity,
        evaluation_count=_integer(mapping, "evaluation_count"),
        receipt_id=_string(mapping, "receipt_id"),
    )
    if serialize_receipt(receipt) != raw:
        raise FinalAccessError("final-access receipt encoding is not canonical")
    return receipt


def _verify_seal(raw: bytes, receipt: DurableFinalAccessReceipt) -> None:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FinalAccessError("invalid final-access seal JSON") from None
    mapping = _mapping(loaded, "final-access seal")
    if set(mapping) != _SEAL_FIELDS:
        raise FinalAccessError("invalid final-access seal fields")
    identity = _mapping(mapping.get("identity"), "final-access seal identity")
    if set(identity) != _STABLE_IDENTITY_FIELDS:
        raise FinalAccessError("invalid final-access seal identity fields")
    if identity != _stable_identity_payload(receipt.identity):
        raise FinalAccessError("final-access seal identity mismatch")
    if _string(mapping, "seal_id") != final_access_seal_id(receipt.identity):
        raise FinalAccessError("final-access seal ID mismatch")
    if _string(mapping, "receipt_id") != receipt.receipt_id:
        raise FinalAccessError("final-access seal receipt mismatch")
    if canonical_json_bytes(mapping) != raw:
        raise FinalAccessError("final-access seal encoding is not canonical")


@dataclass(frozen=True, slots=True)
class FinalAccessStore:
    """Filesystem store that prohibits repeated final authorization."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _base(self) -> Path:
        return self.root / "data" / "historical-validation" / "final-access"

    def _receipt_directory(self, receipt_id: str) -> Path:
        _sha256(receipt_id, "receipt ID")
        return self._base() / "receipts" / receipt_id

    def _receipt_path(self, receipt_id: str) -> Path:
        return self._receipt_directory(receipt_id) / "final-access-receipt.json"

    def _seal_directory(self, identity: FinalAccessIdentity) -> Path:
        return self._base() / "seals" / final_access_seal_id(identity)

    def _seal_path(self, identity: FinalAccessIdentity) -> Path:
        return self._seal_directory(identity) / "final-access-seal.json"

    def authorize(self, identity: FinalAccessIdentity) -> DurableFinalAccessReceipt:
        """Persist a stable seal and receipt before final rows may be materialized."""

        receipt_id = _receipt_id(_RECEIPT_SCHEMA, identity, 1)
        receipt = DurableFinalAccessReceipt(
            schema_version=_RECEIPT_SCHEMA,
            identity=identity,
            evaluation_count=1,
            receipt_id=receipt_id,
        )
        seal_directory = self._seal_directory(identity)
        seal_directory.parent.mkdir(parents=True, exist_ok=True)
        try:
            seal_directory.mkdir(exist_ok=False)
        except FileExistsError:
            raise FinalAccessError("final-test access seal already exists") from None
        write_immutable(self._seal_path(identity), _seal_bytes(receipt))

        receipt_directory = self._receipt_directory(receipt_id)
        receipt_directory.parent.mkdir(parents=True, exist_ok=True)
        try:
            receipt_directory.mkdir(exist_ok=False)
        except FileExistsError:
            raise FinalAccessError("final-test access receipt already exists") from None
        try:
            write_immutable(self._receipt_path(receipt_id), serialize_receipt(receipt))
        except Exception:
            # The stable seal remains as fail-closed evidence of consumed authorization.
            raise
        return receipt

    def load(self, receipt_id: str) -> DurableFinalAccessReceipt:
        """Load and independently validate one canonical receipt and stable seal."""

        try:
            raw = self._receipt_path(receipt_id).read_bytes()
        except OSError:
            raise FinalAccessError("final-test access receipt is missing") from None
        receipt = load_receipt(raw)
        if receipt.receipt_id != receipt_id:
            raise FinalAccessError("final-test access receipt path mismatch")
        try:
            seal_raw = self._seal_path(receipt.identity).read_bytes()
        except OSError:
            raise FinalAccessError("final-test access seal is missing") from None
        _verify_seal(seal_raw, receipt)
        return receipt

    def require(
        self,
        receipt_id: str,
        expected_identity: FinalAccessIdentity,
    ) -> DurableFinalAccessReceipt:
        """Require a stored receipt to match every expected identity field."""

        receipt = self.load(receipt_id)
        if receipt.identity != expected_identity:
            raise FinalAccessError("final-test access identity mismatch")
        return receipt


def authorize_then_load_final(
    store: FinalAccessStore,
    identity: FinalAccessIdentity,
    final_loader: Callable[[], tuple[int, ...]],
) -> tuple[DurableFinalAccessReceipt, tuple[int, ...]]:
    """Persist authorization first, then and only then materialize final rows."""

    receipt = store.authorize(identity)
    return receipt, final_loader()


def assess_exact_resume(
    *,
    receipt: DurableFinalAccessReceipt,
    identity: FinalAccessIdentity,
    completed_final_files: tuple[ArtifactInventoryEntry, ...],
    artifact_root: Path,
) -> ExactResumeAssessment:
    """Allow only provider-free continuation from complete immutable final outputs."""

    if receipt.identity != identity:
        return ExactResumeAssessment(ResumeDecision.INCONCLUSIVE, ("identity_mismatch",))
    if not completed_final_files:
        return ExactResumeAssessment(ResumeDecision.INCONCLUSIVE, ("final_outputs_missing",))
    try:
        rebuilt = build_artifact_inventory(
            artifact_root,
            tuple(item.path for item in completed_final_files),
        )
    except HistoricalValidationError:
        return ExactResumeAssessment(
            ResumeDecision.INCONCLUSIVE,
            ("final_outputs_tampered",),
        )
    if rebuilt != completed_final_files:
        return ExactResumeAssessment(
            ResumeDecision.INCONCLUSIVE,
            ("final_outputs_tampered",),
        )
    return ExactResumeAssessment(
        ResumeDecision.ALLOWED,
        ("identity_match", "final_outputs_complete", "provider_free_resume_only"),
    )


__all__ = [
    "DurableFinalAccessReceipt",
    "ExactResumeAssessment",
    "FinalAccessIdentity",
    "FinalAccessStore",
    "ResumeDecision",
    "assess_exact_resume",
    "authorize_then_load_final",
    "final_access_seal_id",
    "load_receipt",
    "serialize_receipt",
]
