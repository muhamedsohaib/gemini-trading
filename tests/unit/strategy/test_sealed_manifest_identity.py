"""Strict parsing tests for sealed closure and segment study identity."""

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import StudyReplayMismatchError
from gemini_trading.strategy.replay import parse_study_manifest


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
        "dataset_schema_version": "candle-dataset-v2",
        "closure_manifest_sha256": "3" * 64,
        "segment_manifest_sha256": "4" * 64,
        "closure_count": 1,
        "segment_count": 2,
        "closure_ids": ["binance-spot-system-upgrade-2018-02-08"],
        "segment_boundary_indices": [229],
    }
    payload.update(overrides)
    return canonical_json_bytes(payload)


def test_sealed_manifest_binds_closure_and_segment_identity() -> None:
    manifest = parse_study_manifest(_manifest())

    assert manifest.dataset_schema_version == "candle-dataset-v2"
    assert manifest.closure_manifest_sha256 == "3" * 64
    assert manifest.segment_manifest_sha256 == "4" * 64
    assert manifest.closure_count == 1
    assert manifest.segment_count == 2
    assert manifest.closure_ids == ("binance-spot-system-upgrade-2018-02-08",)
    assert manifest.segment_boundary_indices == (229,)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_schema_version", "candle-dataset-v1", "requires candle-dataset-v2"),
        ("segment_count", 3, "segment count"),
        ("closure_ids", [], "closure IDs"),
        ("segment_boundary_indices", [], "segment boundaries"),
    ],
)
def test_sealed_manifest_rejects_inconsistent_segment_identity(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(StudyReplayMismatchError, match=message):
        parse_study_manifest(_manifest(**{field: value}))
