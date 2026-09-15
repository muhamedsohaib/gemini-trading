"""Immutable raw-evidence storage for Economic Data Fabric v1."""

from hashlib import sha256
from pathlib import Path

import pytest

from gemini_trading.economics.data.storage import (
    ECONOMIC_RAW_RECEIPT_SCHEMA_V1,
    EconomicStorageError,
    LocalEconomicEvidenceStore,
    RawEvidenceInventory,
    RawEvidenceReceipt,
)


def test_raw_receipt_schema_is_frozen() -> None:
    assert ECONOMIC_RAW_RECEIPT_SCHEMA_V1 == "economic-raw-receipt-v1"


def test_same_receipt_same_bytes_is_idempotent(tmp_path: Path) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)

    first = store.put(source_id="fixture.macro.v1", receipt_id="release-1", payload=b"abc")
    second = store.put(source_id="fixture.macro.v1", receipt_id="release-1", payload=b"abc")

    assert first == second
    assert first.sha256 == sha256(b"abc").hexdigest()
    assert first.byte_length == 3
    assert first.relative_path == "raw/fixture.macro.v1/release-1.bin"
    assert (tmp_path / first.relative_path).read_bytes() == b"abc"


def test_same_receipt_different_bytes_fails_closed(tmp_path: Path) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)
    store.put(source_id="fixture", receipt_id="release-1", payload=b"abc")

    with pytest.raises(EconomicStorageError, match="immutable"):
        store.put(source_id="fixture", receipt_id="release-1", payload=b"xyz")


@pytest.mark.parametrize(
    ("source_id", "receipt_id"),
    [
        ("../escape", "release-1"),
        ("fixture", "../../escape"),
        ("fixture/subdir", "release-1"),
        ("fixture", "release\\1"),
        (".", "release-1"),
        ("fixture", ".."),
        ("", "release-1"),
        ("fixture", ""),
        ("space source", "release-1"),
    ],
)
def test_store_rejects_unsafe_path_segments(
    tmp_path: Path,
    source_id: str,
    receipt_id: str,
) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)

    with pytest.raises(EconomicStorageError, match="path segment"):
        store.put(source_id=source_id, receipt_id=receipt_id, payload=b"abc")


def test_store_rejects_empty_payload(tmp_path: Path) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)

    with pytest.raises(EconomicStorageError, match="must not be empty"):
        store.put(source_id="fixture", receipt_id="release-1", payload=b"")


def _receipt(
    *,
    source_id: str,
    receipt_id: str,
    payload: bytes,
) -> RawEvidenceReceipt:
    return RawEvidenceReceipt(
        schema_version="economic-raw-receipt-v1",
        source_id=source_id,
        receipt_id=receipt_id,
        relative_path=f"raw/{source_id}/{receipt_id}.bin",
        byte_length=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def test_inventory_is_sorted_and_root_is_input_order_independent() -> None:
    first = _receipt(source_id="z-source", receipt_id="receipt-2", payload=b"z")
    second = _receipt(source_id="a-source", receipt_id="receipt-1", payload=b"a")

    forward = RawEvidenceInventory((first, second))
    reverse = RawEvidenceInventory((second, first))

    assert forward == reverse
    assert tuple(item.source_id for item in forward.receipts) == ("a-source", "z-source")
    assert forward.canonical_bytes == reverse.canonical_bytes
    assert forward.inventory_root_sha256 == reverse.inventory_root_sha256
    assert forward.inventory_root_sha256 == sha256(forward.canonical_bytes).hexdigest()


def test_inventory_rejects_duplicate_receipt_identity() -> None:
    first = _receipt(source_id="fixture", receipt_id="release-1", payload=b"a")
    second = _receipt(source_id="fixture", receipt_id="release-1", payload=b"b")

    with pytest.raises(EconomicStorageError, match="duplicate raw receipt identity"):
        RawEvidenceInventory((first, second))


def test_inventory_rejects_empty_inventory() -> None:
    with pytest.raises(EconomicStorageError, match="at least one"):
        RawEvidenceInventory(())


@pytest.mark.parametrize(
    "digest",
    ["", "a" * 63, "A" * 64, "g" * 64],
)
def test_receipt_rejects_invalid_sha256(digest: str) -> None:
    with pytest.raises(EconomicStorageError, match="sha256"):
        RawEvidenceReceipt(
            schema_version="economic-raw-receipt-v1",
            source_id="fixture",
            receipt_id="release-1",
            relative_path="raw/fixture/release-1.bin",
            byte_length=1,
            sha256=digest,
        )


def test_receipt_rejects_path_not_matching_identity() -> None:
    with pytest.raises(EconomicStorageError, match="relative_path"):
        RawEvidenceReceipt(
            schema_version="economic-raw-receipt-v1",
            source_id="fixture",
            receipt_id="release-1",
            relative_path="raw/other/release-1.bin",
            byte_length=1,
            sha256="a" * 64,
        )
