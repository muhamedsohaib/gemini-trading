"""Shared fixed-scope v4 closure, exclusion, and segment evidence for sealed tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fixtures.market_data.multi_closure_btcusdt_4h import (
    CANDLES,
    EXPECTED_BOUNDARIES,
    EXPECTED_CANDLE_COUNT,
    MANIFEST,
    MANIFEST_BYTES,
    REQUEST,
)
from gemini_trading.data.exclusions import (
    CandleExclusion,
    CandleExclusionManifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.segments import (
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)


@dataclass(frozen=True, slots=True)
class FixedSupportFields:
    dataset_schema_version: str
    closure_manifest_path: str
    closure_manifest_sha256: str
    exclusion_manifest_path: str
    exclusion_manifest_sha256: str
    segment_manifest_path: str
    segment_manifest_sha256: str
    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    excluded_provider_rows: tuple[tuple[str, str], ...]
    segment_boundary_indices: tuple[int, ...]
    candle_count: int


def _exclusion_manifest() -> CandleExclusionManifest:
    exclusions = tuple(
        CandleExclusion(
            closure_id=closure.closure_id,
            raw_page_sequence=index + 1,
            raw_page_sha256=f"{index + 1:064x}",
            row_index=index,
            provider_row_sha256=closure.partial_candle.provider_row_sha256,
            open_time=closure.partial_candle.open_time,
            actual_close_time=closure.partial_candle.actual_close_time,
            expected_close_time=closure.partial_candle.expected_close_time,
            exclusion_reason=closure.partial_candle.exclusion_reason,
            canonical_index_before_removal=EXPECTED_BOUNDARIES[index] + index,
        )
        for index, closure in enumerate(MANIFEST.closures)
    )
    return CandleExclusionManifest(
        schema_version="candle-exclusion-manifest-v1",
        exclusions=exclusions,
    )


def write_fixed_supporting_evidence(root: Path) -> FixedSupportFields:
    """Write canonical fixed-window supporting manifests and return handoff fields."""

    exclusion_manifest = _exclusion_manifest()
    exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
    segment_manifest = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    closure_path = root / "exchange-closures.json"
    exclusion_path = root / "candle-exclusions.json"
    segment_path = root / "candle-segments.json"
    closure_path.write_bytes(MANIFEST_BYTES)
    exclusion_path.write_bytes(exclusion_bytes)
    segment_path.write_bytes(segment_bytes)
    return FixedSupportFields(
        dataset_schema_version="candle-dataset-v4",
        closure_manifest_path=closure_path.relative_to(root).as_posix(),
        closure_manifest_sha256=hashlib.sha256(MANIFEST_BYTES).hexdigest(),
        exclusion_manifest_path=exclusion_path.relative_to(root).as_posix(),
        exclusion_manifest_sha256=hashlib.sha256(exclusion_bytes).hexdigest(),
        segment_manifest_path=segment_path.relative_to(root).as_posix(),
        segment_manifest_sha256=hashlib.sha256(segment_bytes).hexdigest(),
        closure_count=len(MANIFEST.closures),
        exclusion_count=len(exclusion_manifest.exclusions),
        segment_count=len(segment_manifest.segments),
        closure_ids=tuple(item.closure_id for item in MANIFEST.closures),
        excluded_provider_rows=tuple(
            (item.closure_id, item.provider_row_sha256) for item in exclusion_manifest.exclusions
        ),
        segment_boundary_indices=segment_manifest.boundary_indices,
        candle_count=EXPECTED_CANDLE_COUNT,
    )
