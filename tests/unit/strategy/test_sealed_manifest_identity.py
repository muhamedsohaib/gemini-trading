"""Strict parsing tests for sealed closure, exclusion, and segment identity."""

import pytest

from fixtures.market_data.multi_closure_btcusdt_4h import (
    EXPECTED_BOUNDARIES,
    MANIFEST,
)
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import StudyReplayMismatchError
from gemini_trading.strategy.replay import parse_study_manifest

_EXPECTED_ROWS = [
    {
        "closure_id": item.closure_id,
        "provider_row_sha256": item.partial_candle.provider_row_sha256,
    }
    for item in MANIFEST.closures
]


def _manifest(**overrides: object) -> bytes:
    payload: dict[str, object] = {
        "schema_version": "strategy-study-v1",
        "study_id": "a" * 64,
        "split_plan_sha256": "b" * 64,
        "policy_sha256": "c" * 64,
        "configuration_sha256": "d" * 64,
        "code_commit": "e" * 40,
        "final_test_receipt_id": "f" * 64,
        "final_evaluation_count": 1,
        "pre_final_id": "1" * 64,
        "dataset_handoff_inventory_root": "2" * 64,
        "durable_final_access_receipt_id": "f" * 64,
        "dataset_schema_version": "candle-dataset-v4",
        "closure_manifest_sha256": "3" * 64,
        "exclusion_manifest_sha256": "5" * 64,
        "segment_manifest_sha256": "4" * 64,
        "closure_count": 20,
        "exclusion_count": 20,
        "segment_count": 21,
        "closure_ids": [item.closure_id for item in MANIFEST.closures],
        "excluded_provider_rows": _EXPECTED_ROWS,
        "segment_boundary_indices": list(EXPECTED_BOUNDARIES),
    }
    payload.update(overrides)
    return canonical_json_bytes(payload)


def test_sealed_manifest_binds_closure_exclusion_and_segment_identity() -> None:
    manifest = parse_study_manifest(_manifest())

    assert manifest.dataset_schema_version == "candle-dataset-v4"
    assert manifest.closure_manifest_sha256 == "3" * 64
    assert manifest.exclusion_manifest_sha256 == "5" * 64
    assert manifest.segment_manifest_sha256 == "4" * 64
    assert (
        manifest.closure_count,
        manifest.exclusion_count,
        manifest.segment_count,
    ) == (20, 20, 21)
    assert manifest.closure_ids == tuple(item.closure_id for item in MANIFEST.closures)
    assert tuple(
        (item.closure_id, item.provider_row_sha256)
        for item in manifest.excluded_provider_rows
    ) == tuple(
        (item["closure_id"], item["provider_row_sha256"])
        for item in _EXPECTED_ROWS
    )
    assert manifest.segment_boundary_indices == EXPECTED_BOUNDARIES


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_schema_version", "candle-dataset-v3", "requires candle-dataset-v4"),
        ("exclusion_count", 19, "exclusion count"),
        ("segment_count", 20, "segment count"),
        ("closure_ids", [], "closure IDs"),
        ("excluded_provider_rows", [], "excluded row"),
        ("segment_boundary_indices", [], "segment boundaries"),
    ],
)
def test_sealed_manifest_rejects_inconsistent_segment_identity(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(StudyReplayMismatchError, match=message):
        parse_study_manifest(_manifest(**{field: value}))


def test_sealed_manifest_rejects_legacy_scalar_row_identity() -> None:
    payload = __import__("json").loads(_manifest())
    rows = payload.pop("excluded_provider_rows")
    payload["excluded_provider_row_sha256"] = rows[0]["provider_row_sha256"]

    with pytest.raises(StudyReplayMismatchError, match="fields"):
        parse_study_manifest(canonical_json_bytes(payload))


def test_sealed_manifest_rejects_reordered_row_identity() -> None:
    with pytest.raises(StudyReplayMismatchError, match=r"order|identity"):
        parse_study_manifest(_manifest(excluded_provider_rows=list(reversed(_EXPECTED_ROWS))))
