"""Tests for the fixed sealed BTCUSDT dataset v4 identity."""

from pathlib import Path

import pytest

from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    ExcludedProviderRow,
    build_artifact_inventory,
    inventory_root_sha256,
)
from gemini_trading.strategy.sealed_dataset_identity import (
    EXPECTED_BOUNDARIES,
    EXPECTED_CANDLE_COUNT,
    EXPECTED_CLOSURE_IDS,
    EXPECTED_CLOSURE_MANIFEST_SHA256,
    EXPECTED_COUNTS,
    EXPECTED_EXCLUDED_PROVIDER_ROWS,
    assert_fixed_sealed_dataset_identity,
)
from sealed_dataset_support import write_fixed_supporting_evidence


def _manifest(root: Path) -> DatasetHandoffManifest:
    support = write_fixed_supporting_evidence(root)
    files = build_artifact_inventory(
        root,
        (
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
            ExcludedProviderRow(closure_id, row_sha256)
            for closure_id, row_sha256 in support.excluded_provider_rows
        ),
        segment_boundary_indices=support.segment_boundary_indices,
        candle_count=support.candle_count,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-06-30T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=files,
        inventory_root_sha256=inventory_root_sha256(files),
    )


def test_fixed_identity_accepts_exact_handoff(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    assert manifest.closure_manifest_sha256 == EXPECTED_CLOSURE_MANIFEST_SHA256
    assert manifest.closure_ids == EXPECTED_CLOSURE_IDS
    assert manifest.excluded_provider_rows == EXPECTED_EXCLUDED_PROVIDER_ROWS
    assert manifest.segment_boundary_indices == EXPECTED_BOUNDARIES
    assert (
        manifest.closure_count,
        manifest.exclusion_count,
        manifest.segment_count,
    ) == EXPECTED_COUNTS
    assert manifest.candle_count == EXPECTED_CANDLE_COUNT
    assert_fixed_sealed_dataset_identity(manifest)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("closure_manifest_sha256", "f" * 64),
        ("closure_count", 19),
        ("exclusion_count", 19),
        ("segment_count", 20),
        ("closure_ids", tuple(reversed(EXPECTED_CLOSURE_IDS))),
        ("excluded_provider_rows", tuple(reversed(EXPECTED_EXCLUDED_PROVIDER_ROWS))),
        ("segment_boundary_indices", tuple(reversed(EXPECTED_BOUNDARIES))),
        ("candle_count", EXPECTED_CANDLE_COUNT - 1),
        ("first_open_time", "2018-01-01T04:00:00Z"),
        ("last_open_time", "2026-06-30T16:00:00Z"),
        ("replay_status", "pending"),
        ("verification_status", "unverified"),
    ),
)
def test_fixed_identity_rejects_single_field_mismatch(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    manifest = _manifest(tmp_path)
    object.__setattr__(manifest, field_name, value)

    with pytest.raises(DatasetHandoffError, match="fixed sealed dataset identity mismatch"):
        assert_fixed_sealed_dataset_identity(manifest)
