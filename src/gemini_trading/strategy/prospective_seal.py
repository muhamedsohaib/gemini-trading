"""Exclusive prospective-final seal for a verified Candidate v0.2 qualification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import write_immutable
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.prospective_final import ProspectiveFinalWindow
from gemini_trading.strategy.qualification import QualificationClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SCHEMA = "candidate-v0.2-prospective-final-seal-v1"


@dataclass(frozen=True, slots=True)
class ProspectiveFinalSealRequest:
    """Verified pre-final identities required to create one future final seal."""

    code_commit: str
    dataset_id: str
    dataset_handoff_inventory_root: str
    qualification_id: str
    qualification_inventory_root: str
    qualification_classification: QualificationClassification
    workflow_run_id: int
    workflow_run_attempt: int
    verified_at: datetime
    development_cutoff: datetime

    def __post_init__(self) -> None:
        if _GIT_SHA.fullmatch(self.code_commit) is None:
            raise FinalAccessError("invalid prospective seal code commit")
        for field_name in (
            "dataset_id",
            "dataset_handoff_inventory_root",
            "qualification_id",
            "qualification_inventory_root",
        ):
            if _SHA256.fullmatch(getattr(self, field_name)) is None:
                raise FinalAccessError(f"invalid prospective seal {field_name}")
        for field_name in ("workflow_run_id", "workflow_run_attempt"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 1:
                raise FinalAccessError(f"invalid prospective seal {field_name}")
        if self.qualification_classification is not QualificationClassification.QUALIFIED:
            raise FinalAccessError("prospective final seal requires QUALIFIED evidence")
        ProspectiveFinalWindow.from_verified_at(
            development_cutoff=self.development_cutoff,
            verified_at=self.verified_at,
        )


@dataclass(frozen=True, slots=True)
class ProspectiveFinalSeal:
    """Canonical immutable future-window identity; it contains no market rows."""

    schema_version: str
    seal_id: str
    code_commit: str
    dataset_id: str
    dataset_handoff_inventory_root: str
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
            raise FinalAccessError("unsupported prospective final seal schema")
        if _SHA256.fullmatch(self.seal_id) is None:
            raise FinalAccessError("invalid prospective final seal ID")
        if _seal_id(_seal_core(self)) != self.seal_id:
            raise FinalAccessError("prospective final seal identity mismatch")


def _request_core(request: ProspectiveFinalSealRequest) -> dict[str, object]:
    window = ProspectiveFinalWindow.from_verified_at(
        development_cutoff=request.development_cutoff,
        verified_at=request.verified_at,
    )
    return {
        "schema_version": _SCHEMA,
        "code_commit": request.code_commit,
        "dataset_id": request.dataset_id,
        "dataset_handoff_inventory_root": request.dataset_handoff_inventory_root,
        "qualification_id": request.qualification_id,
        "qualification_inventory_root": request.qualification_inventory_root,
        "workflow_run_id": request.workflow_run_id,
        "workflow_run_attempt": request.workflow_run_attempt,
        "verified_at": request.verified_at,
        "development_cutoff": request.development_cutoff,
        "bridge_start": window.bridge_start,
        "bridge_end": window.bridge_end,
        "final_start": window.final_start,
        "final_end": window.final_end,
    }


def _seal_core(seal: ProspectiveFinalSeal) -> dict[str, object]:
    return {key: value for key, value in asdict(seal).items() if key != "seal_id"}


def _seal_id(core: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(core)).hexdigest()


def build_prospective_final_seal(request: ProspectiveFinalSealRequest) -> ProspectiveFinalSeal:
    """Build a future-window seal without reading or constructing market evidence."""

    core = _request_core(request)
    return ProspectiveFinalSeal(
        seal_id=_seal_id(core),
        **core,
    )


def serialize_prospective_final_seal(seal: ProspectiveFinalSeal) -> bytes:
    """Serialize one canonical seal."""

    return canonical_json_bytes({**_seal_core(seal), "seal_id": seal.seal_id})


@dataclass(frozen=True, slots=True)
class LocalProspectiveFinalSealStore:
    """Fail-closed store that permits one immutable prospective seal per candidate."""

    root: Path

    def _candidate_directory(self) -> Path:
        return self.root / "data" / "historical-validation" / "v0-2-prospective-final"

    def _seal_path(self, seal_id: str) -> Path:
        if _SHA256.fullmatch(seal_id) is None:
            raise FinalAccessError("invalid prospective final seal ID")
        return self._candidate_directory() / "seals" / seal_id / "prospective-final-seal.json"

    def create(self, request: ProspectiveFinalSealRequest) -> ProspectiveFinalSeal:
        """Create exactly one v0.2 prospective seal with exclusive directory semantics."""

        seal = build_prospective_final_seal(request)
        candidate = self._candidate_directory()
        marker = candidate / "active-seal"
        candidate.mkdir(parents=True, exist_ok=True)
        try:
            marker.mkdir(exist_ok=False)
        except FileExistsError:
            raise FinalAccessError("prospective final seal already exists") from None
        write_immutable(self._seal_path(seal.seal_id), serialize_prospective_final_seal(seal))
        write_immutable(marker / "seal-id.txt", f"{seal.seal_id}\n".encode())
        return seal

    def load(self, seal_id: str) -> ProspectiveFinalSeal:
        """Load and validate one canonical prospective seal."""

        try:
            raw = self._seal_path(seal_id).read_bytes()
        except OSError:
            raise FinalAccessError("prospective final seal is missing") from None
        try:
            loaded: object = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FinalAccessError("invalid prospective final seal JSON") from None
        if not isinstance(loaded, dict):
            raise FinalAccessError("invalid prospective final seal JSON")
        mapping = cast(dict[str, object], loaded)
        try:
            seal = ProspectiveFinalSeal(
                schema_version=cast(str, mapping["schema_version"]),
                seal_id=cast(str, mapping["seal_id"]),
                code_commit=cast(str, mapping["code_commit"]),
                dataset_id=cast(str, mapping["dataset_id"]),
                dataset_handoff_inventory_root=cast(str, mapping["dataset_handoff_inventory_root"]),
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
        except (KeyError, ValueError):
            raise FinalAccessError("invalid prospective final seal fields") from None
        if seal.seal_id != seal_id or serialize_prospective_final_seal(seal) != raw:
            raise FinalAccessError("prospective final seal encoding changed")
        return seal


__all__ = [
    "LocalProspectiveFinalSealStore",
    "ProspectiveFinalSeal",
    "ProspectiveFinalSealRequest",
    "build_prospective_final_seal",
    "serialize_prospective_final_seal",
]
