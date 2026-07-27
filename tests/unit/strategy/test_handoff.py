"""Unit tests for sealed historical-validation artifact handoffs."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.data.exclusions import (
    load_candle_exclusion_manifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.strategy.errors import DatasetHandoffError, HistoricalValidationError
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    ExcludedProviderRow,
    build_artifact_inventory,
    inventory_root_sha256,
    load_dataset_handoff,
    serialize_dataset_handoff,
    verify_dataset_handoff,
)
from sealed_dataset_support import write_fixed_supporting_evidence


def _manifest(root: Path, relative_paths: tuple[str, ...]) -> DatasetHandoffManifest:
    support = write_fixed_supporting_evidence(root)
    entries = build_artifact_inventory(
        root,
        (
            *relative_paths,
            support.closure_manifest_path,
            support.exclusion_manifest_path,
            support.segment_manifest_path,
        ),
    )
    return DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v4",
        repository="muhamedsohaib/gemini-trading",
        source_commit="a" * 40,
        workflow_name="sealed-btcusdt-dataset",
        workflow_run_id=123,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="4h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-07-01T00:00:00Z",
        run_id="run-123",
        dataset_id="b" * 64,
        dataset_schema_version=support.dataset_schema_version,
        closure_manifest_path=support.closure_manifest_path,
        closure_manifest_sha256=support.closure_manifest_sha256,
        exclusion_manifest_path=support.exclusion_manifest_path,
        exclusion_manifest_sha256=support.exclusion_manifest_sha256,
        segment_manifest_path=support.segment_manifest_path,
        segment_manifest_sha256=support.segment_manifest_sha256,
        closure_count=support.closure_count,
        exclusion_count=support.exclusion_count,
        segment_count=support.segment_count,
        closure_ids=support.closure_ids,
        excluded_provider_rows=tuple(
            ExcludedProviderRow(closure_id=closure_id, provider_row_sha256=row_sha256)
            for closure_id, row_sha256 in support.excluded_provider_rows
        ),
        segment_boundary_indices=support.segment_boundary_indices,
        candle_count=support.candle_count,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-06-30T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=entries,
        inventory_root_sha256=inventory_root_sha256(entries),
    )


def test_inventory_is_sorted_and_content_addressed(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_bytes(b"beta\n")
    (tmp_path / "a.txt").write_bytes(b"alpha\n")

    entries = build_artifact_inventory(tmp_path, ("b.txt", "a.txt"))

    assert tuple(item.path for item in entries) == ("a.txt", "b.txt")
    assert tuple(item.size_bytes for item in entries) == (6, 5)
    assert len(inventory_root_sha256(entries)) == 64


@pytest.mark.parametrize("path", ("../escape", "/absolute", "a/../../b", "a\\b", "./a"))
def test_inventory_rejects_unsafe_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(HistoricalValidationError, match="artifact-relative path"):
        build_artifact_inventory(tmp_path, (path,))


def test_inventory_rejects_duplicate_paths(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"alpha\n")

    with pytest.raises(HistoricalValidationError, match="duplicate"):
        build_artifact_inventory(tmp_path, ("a.txt", "a.txt"))


def test_inventory_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(HistoricalValidationError, match="unable to read"):
        build_artifact_inventory(tmp_path, ("missing.txt",))


def test_handoff_round_trip_is_byte_stable(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))

    raw = serialize_dataset_handoff(manifest)

    assert serialize_dataset_handoff(load_dataset_handoff(raw)) == raw
    verify_dataset_handoff(manifest, tmp_path)
    assert manifest.dataset_schema_version == "candle-dataset-v4"
    assert (
        manifest.closure_count,
        manifest.exclusion_count,
        manifest.segment_count,
    ) == (20, 20, 21)
    assert len(manifest.excluded_provider_rows) == 20
    assert manifest.candle_count == 18_582


def test_handoff_rejects_wrong_dataset_id(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))

    with pytest.raises(DatasetHandoffError, match="dataset identity"):
        verify_dataset_handoff(manifest, tmp_path, expected_dataset_id="c" * 64)


def test_handoff_rejects_wrong_commit_and_workflow_run(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))

    with pytest.raises(DatasetHandoffError, match="source commit"):
        verify_dataset_handoff(manifest, tmp_path, expected_commit="c" * 40)
    with pytest.raises(DatasetHandoffError, match="workflow run"):
        verify_dataset_handoff(manifest, tmp_path, expected_run_id=456)


def test_handoff_rejects_tampered_file(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))
    path.write_bytes(b"tampered\n")

    with pytest.raises(DatasetHandoffError, match="inventory mismatch"):
        verify_dataset_handoff(manifest, tmp_path)


def test_handoff_rejects_extra_field(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    raw = serialize_dataset_handoff(_manifest(tmp_path, ("data.txt",)))
    altered = raw[:-2] + b',"extra":true}\n'

    with pytest.raises(DatasetHandoffError, match="fields"):
        load_dataset_handoff(altered)


def test_handoff_rejects_legacy_scalar_excluded_row_field(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    payload = cast(dict[str, object], json.loads(serialize_dataset_handoff(_manifest(tmp_path, ("data.txt",)))))
    rows = cast(list[dict[str, object]], payload.pop("excluded_provider_rows"))
    payload["excluded_provider_row_sha256"] = rows[0]["provider_row_sha256"]
    altered = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()

    with pytest.raises(DatasetHandoffError, match="fields"):
        load_dataset_handoff(altered)


def test_handoff_rejects_noncanonical_encoding(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    raw = serialize_dataset_handoff(_manifest(tmp_path, ("data.txt",)))

    with pytest.raises(DatasetHandoffError, match="canonical"):
        load_dataset_handoff(raw.replace(b'"repository":', b'"repository": '))


def test_handoff_rejects_changed_scope(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    with pytest.raises(DatasetHandoffError, match="market scope"):
        replace(_manifest(tmp_path, ("data.txt",)), symbol="ETHUSDT")


def test_handoff_rejects_legacy_dataset_schema(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    with pytest.raises(DatasetHandoffError, match="candle-dataset-v4"):
        replace(
            _manifest(tmp_path, ("data.txt",)),
            dataset_schema_version="candle-dataset-v3",
        )


def test_handoff_rejects_tampered_exclusion_manifest(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))
    exclusion_path = tmp_path / manifest.exclusion_manifest_path
    exclusion_path.write_bytes(
        exclusion_path.read_bytes().replace(b'"row_index":0', b'"row_index":99', 1)
    )

    with pytest.raises(DatasetHandoffError, match="exclusion manifest hash"):
        verify_dataset_handoff(manifest, tmp_path)


def test_handoff_rejects_exclusion_linked_to_different_closure(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))
    exclusion_path = tmp_path / manifest.exclusion_manifest_path
    exclusion_manifest = load_candle_exclusion_manifest(exclusion_path.read_bytes())
    altered_exclusion = replace(
        exclusion_manifest.exclusions[0],
        closure_id="different-exchange-closure",
    )
    altered_bytes = serialize_candle_exclusion_manifest(
        replace(
            exclusion_manifest,
            exclusions=(altered_exclusion, *exclusion_manifest.exclusions[1:]),
        )
    )
    exclusion_path.write_bytes(altered_bytes)
    rebuilt_files = build_artifact_inventory(tmp_path, tuple(item.path for item in manifest.files))
    altered_manifest = replace(
        manifest,
        exclusion_manifest_sha256=hashlib.sha256(altered_bytes).hexdigest(),
        files=rebuilt_files,
        inventory_root_sha256=inventory_root_sha256(rebuilt_files),
    )

    with pytest.raises(DatasetHandoffError, match="excluded provider row|closure ID"):
        verify_dataset_handoff(altered_manifest, tmp_path)


def test_handoff_rejects_reordered_excluded_rows(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))

    with pytest.raises(DatasetHandoffError, match="order"):
        replace(
            manifest,
            excluded_provider_rows=tuple(reversed(manifest.excluded_provider_rows)),
        )


def test_handoff_rejects_missing_or_extra_excluded_rows(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))

    with pytest.raises(DatasetHandoffError, match="count"):
        replace(manifest, excluded_provider_rows=manifest.excluded_provider_rows[:-1])
    with pytest.raises(DatasetHandoffError, match="count"):
        replace(
            manifest,
            excluded_provider_rows=(
                *manifest.excluded_provider_rows,
                ExcludedProviderRow("extra-closure", "f" * 64),
            ),
        )


def test_handoff_rejects_duplicate_excluded_ids_and_digests(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(tmp_path, ("data.txt",))
    rows = list(manifest.excluded_provider_rows)

    rows[1] = replace(rows[1], closure_id=rows[0].closure_id)
    with pytest.raises(DatasetHandoffError, match="order|duplicate"):
        replace(manifest, excluded_provider_rows=tuple(rows))

    rows = list(manifest.excluded_provider_rows)
    rows[1] = replace(rows[1], provider_row_sha256=rows[0].provider_row_sha256)
    with pytest.raises(DatasetHandoffError, match="duplicate"):
        replace(manifest, excluded_provider_rows=tuple(rows))


def test_handoff_rejects_wrong_segment_boundary_count(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")

    with pytest.raises(DatasetHandoffError, match="segment boundary count"):
        replace(
            _manifest(tmp_path, ("data.txt",)),
            segment_boundary_indices=(),
        )
