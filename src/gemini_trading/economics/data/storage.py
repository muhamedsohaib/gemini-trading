"""Immutable provider-neutral raw evidence storage for economic datasets."""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

ECONOMIC_RAW_RECEIPT_SCHEMA_V1: Final[str] = "economic-raw-receipt-v1"
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")


class EconomicStorageError(ValueError):
    """Raised when immutable economic evidence storage is invalid."""


def _validate_path_segment(value: str, field_name: str) -> None:
    if value in {"", ".", ".."} or _SAFE_SEGMENT.fullmatch(value) is None:
        raise EconomicStorageError(f"{field_name} is not a safe path segment")


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EconomicStorageError("sha256 must be lowercase SHA-256 hex")


@dataclass(frozen=True, slots=True)
class RawEvidenceReceipt:
    """Immutable identity for one captured raw evidence payload."""

    schema_version: str
    source_id: str
    receipt_id: str
    relative_path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_RAW_RECEIPT_SCHEMA_V1:
            raise EconomicStorageError("unsupported economic raw receipt schema")
        _validate_path_segment(self.source_id, "source_id")
        _validate_path_segment(self.receipt_id, "receipt_id")
        if isinstance(self.byte_length, bool) or self.byte_length < 1:
            raise EconomicStorageError("byte_length must be a positive integer")
        _validate_sha256(self.sha256)
        expected_path = f"raw/{self.source_id}/{self.receipt_id}.bin"
        if self.relative_path != expected_path:
            raise EconomicStorageError("relative_path does not match receipt identity")


def _receipt_payload(receipt: RawEvidenceReceipt) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "source_id": receipt.source_id,
        "receipt_id": receipt.receipt_id,
        "relative_path": receipt.relative_path,
        "byte_length": receipt.byte_length,
        "sha256": receipt.sha256,
    }


def _inventory_bytes(receipts: tuple[RawEvidenceReceipt, ...]) -> bytes:
    rows: list[bytes] = []
    for receipt in receipts:
        encoded = json.dumps(
            _receipt_payload(receipt),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        rows.append(f"{encoded}\n".encode())
    return b"".join(rows)


@dataclass(frozen=True, slots=True, init=False)
class RawEvidenceInventory:
    """Canonical inventory of immutable raw evidence receipts."""

    receipts: tuple[RawEvidenceReceipt, ...]

    def __init__(self, receipts: tuple[RawEvidenceReceipt, ...]) -> None:
        if not receipts:
            raise EconomicStorageError("raw evidence inventory requires at least one receipt")
        ordered = tuple(
            sorted(
                receipts,
                key=lambda item: (item.source_id, item.receipt_id, item.sha256),
            )
        )
        identities = tuple((item.source_id, item.receipt_id) for item in ordered)
        if len(identities) != len(set(identities)):
            raise EconomicStorageError("duplicate raw receipt identity")
        object.__setattr__(self, "receipts", ordered)

    @property
    def canonical_bytes(self) -> bytes:
        """Return deterministic JSONL bytes for this inventory."""

        return _inventory_bytes(self.receipts)

    @property
    def inventory_root_sha256(self) -> str:
        """Return the content root for the canonical inventory bytes."""

        return sha256(self.canonical_bytes).hexdigest()

    @property
    def raw_digests(self) -> frozenset[str]:
        """Return the exact raw payload digests present in this inventory."""

        return frozenset(item.sha256 for item in self.receipts)


class LocalEconomicEvidenceStore:
    """Fail-closed immutable byte store rooted at one economic bundle directory."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def put(self, *, source_id: str, receipt_id: str, payload: bytes) -> RawEvidenceReceipt:
        """Persist one raw payload idempotently and return its immutable receipt."""

        _validate_path_segment(source_id, "source_id")
        _validate_path_segment(receipt_id, "receipt_id")
        if not payload:
            raise EconomicStorageError("raw evidence payload must not be empty")

        digest = sha256(payload).hexdigest()
        relative_path = f"raw/{source_id}/{receipt_id}.bin"
        target = self._root / "raw" / source_id / f"{receipt_id}.bin"
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            if target.read_bytes() != payload:
                raise EconomicStorageError(
                    "immutable raw evidence path already contains different bytes"
                )
        else:
            try:
                with target.open("xb") as handle:
                    handle.write(payload)
            except FileExistsError:
                if target.read_bytes() != payload:
                    raise EconomicStorageError(
                        "immutable raw evidence path already contains different bytes"
                    ) from None

        return RawEvidenceReceipt(
            schema_version=ECONOMIC_RAW_RECEIPT_SCHEMA_V1,
            source_id=source_id,
            receipt_id=receipt_id,
            relative_path=relative_path,
            byte_length=len(payload),
            sha256=digest,
        )


__all__ = [
    "ECONOMIC_RAW_RECEIPT_SCHEMA_V1",
    "EconomicStorageError",
    "LocalEconomicEvidenceStore",
    "RawEvidenceInventory",
    "RawEvidenceReceipt",
]
