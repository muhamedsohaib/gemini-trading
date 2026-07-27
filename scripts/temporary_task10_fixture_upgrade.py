"""Upgrade the sealed two-phase integration fixture to fixed dataset v4 evidence."""

from pathlib import Path


pre_final_path = Path("tests/unit/strategy/test_pre_final.py")
pre_final = pre_final_path.read_text(encoding="utf-8")
pre_final = pre_final.replace(
    "from pathlib import Path\n\nimport pytest",
    "from pathlib import Path\nfrom typing import cast\n\nimport pytest",
    1,
)
old_typed_block = '''    manifest = json.loads(files["pre-final-manifest.json"])
    rows = manifest["excluded_provider_rows"]
    assert isinstance(rows, list)
    manifest["excluded_provider_rows"] = list(reversed(rows))
    files["pre-final-manifest.json"] = canonical_json_bytes(manifest)

    result = json.loads(files["pre-final-result-manifest.json"])
'''
new_typed_block = '''    manifest = cast(
        dict[str, object],
        json.loads(files["pre-final-manifest.json"]),
    )
    rows_value = manifest.get("excluded_provider_rows")
    assert isinstance(rows_value, list)
    rows = cast(list[object], rows_value)
    manifest["excluded_provider_rows"] = list(reversed(rows))
    files["pre-final-manifest.json"] = canonical_json_bytes(manifest)

    result = cast(
        dict[str, object],
        json.loads(files["pre-final-result-manifest.json"]),
    )
'''
if pre_final.count(old_typed_block) != 1:
    raise SystemExit("unexpected pre-final typed tamper block")
pre_final_path.write_text(
    pre_final.replace(old_typed_block, new_typed_block, 1),
    encoding="utf-8",
)

integration_path = Path("tests/integration/test_sealed_historical_validation.py")
integration = integration_path.read_text(encoding="utf-8")
integration = integration.replace("from datetime import timedelta\n", "", 1)
integration = integration.replace(
    "from candidate_strategy_e2e_worker import synthetic_candidate_candles\n",
    '''from candidate_strategy_e2e_worker import synthetic_candidate_candles
from fixtures.market_data.multi_closure_btcusdt_4h import (
    CANDLES as FIXED_CANDLES,
    EXPECTED_BOUNDARIES,
    EXPECTED_CANDLE_COUNT,
    MANIFEST as CLOSURE_MANIFEST,
    MANIFEST_BYTES as CLOSURE_MANIFEST_BYTES,
    REQUEST,
)
''',
    1,
)
old_closure_import = '''from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
    serialize_exchange_closure_manifest,
)
'''
if integration.count(old_closure_import) != 1:
    raise SystemExit("unexpected integration closure imports")
integration = integration.replace(old_closure_import, "", 1)
old_segment_import = '''from gemini_trading.data.segments import (
    CandleSegment,
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
)
'''
new_segment_import = '''from gemini_trading.data.segments import (
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
'''
if integration.count(old_segment_import) != 1:
    raise SystemExit("unexpected integration segment imports")
integration = integration.replace(old_segment_import, new_segment_import, 1)
integration = integration.replace(
    "    DatasetHandoffManifest,\n",
    "    DatasetHandoffManifest,\n    ExcludedProviderRow,\n",
    1,
)
old_constants = '''_CLOSURE_ID = "binance-spot-system-upgrade-2018-02-08"
_APPROVED_ROW_SHA256 = (
    "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"  # pragma: allowlist secret
)


'''
if integration.count(old_constants) != 1:
    raise SystemExit("unexpected integration closure constants")
integration = integration.replace(old_constants, "", 1)
start = integration.index("def _verified_dataset(root: Path) -> VerifiedDataset:\n")
end = integration.index("\n\ndef _handoff", start)
new_verified_dataset = '''def _verified_dataset(root: Path) -> VerifiedDataset:
    source_candles = synthetic_candidate_candles()
    if len(source_candles) < EXPECTED_CANDLE_COUNT:
        raise AssertionError("candidate fixture lacks fixed-window history")
    candles = tuple(
        replace(
            source_candles[index],
            instrument=fixed.instrument,
            timeframe=fixed.timeframe,
            open_time=fixed.open_time,
            close_time=fixed.close_time,
            source_provider=fixed.source_provider,
        )
        for index, fixed in enumerate(FIXED_CANDLES)
    )
    if len(candles) != EXPECTED_CANDLE_COUNT:
        raise AssertionError("fixed dataset candle count mismatch")
    canonical_bytes = serialize_candles(candles)
    exclusion_manifest = CandleExclusionManifest(
        schema_version="candle-exclusion-manifest-v1",
        exclusions=tuple(
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
            for index, closure in enumerate(CLOSURE_MANIFEST.closures)
        ),
    )
    exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
    segment_manifest = validate_and_segment_candle_sequence(
        candles,
        REQUEST,
        CLOSURE_MANIFEST,
    )
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v4",
        provider=CLOSURE_MANIFEST.provider,
        instrument=CLOSURE_MANIFEST.instrument,
        timeframe=CLOSURE_MANIFEST.timeframe,
        start_time=REQUEST.start_time,
        end_time=REQUEST.end_time,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest_bytes=CLOSURE_MANIFEST_BYTES,
        exclusion_manifest_bytes=exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
        closure_count=len(CLOSURE_MANIFEST.closures),
        exclusion_count=len(exclusion_manifest.exclusions),
        segment_count=len(segment_manifest.segments),
    )
    store = LocalImmutableStore(root)
    store.write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    store.write_dataset_supporting_manifests(
        manifest.dataset_id,
        CLOSURE_MANIFEST_BYTES,
        segment_bytes,
    )
    store.write_dataset_exclusion_manifest(manifest.dataset_id, exclusion_bytes)
    return VerifiedDataset(
        manifest=manifest,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest=CLOSURE_MANIFEST,
        exclusion_manifest=exclusion_manifest,
        segment_manifest=segment_manifest,
        closure_manifest_bytes=CLOSURE_MANIFEST_BYTES,
        exclusion_manifest_bytes=exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
    )
'''
integration = integration[:start] + new_verified_dataset + integration[end:]
integration = integration.replace(
    '        schema_version="sealed-dataset-handoff-v3",',
    '        schema_version="sealed-dataset-handoff-v4",',
    1,
)
integration = integration.replace(
    '        dataset_schema_version="candle-dataset-v3",',
    '        dataset_schema_version=dataset.manifest.schema_version,',
    1,
)
integration = integration.replace(
    '''        excluded_provider_row_sha256=_APPROVED_ROW_SHA256,
        segment_boundary_indices=(1,),
        candle_count=18_618,''',
    '''        excluded_provider_rows=tuple(
            ExcludedProviderRow(
                closure_id=item.closure_id,
                provider_row_sha256=item.provider_row_sha256,
            )
            for item in dataset.exclusion_manifest.exclusions
        )
        if dataset.exclusion_manifest is not None
        else (),
        segment_boundary_indices=(
            dataset.segment_manifest.boundary_indices
            if dataset.segment_manifest is not None
            else ()
        ),
        candle_count=len(dataset.candles),''',
    1,
)
assertion_anchor = '''    assert manifest["pre_final_id"] == pre_final.pre_final_id
    assert manifest["dataset_handoff_inventory_root"] == handoff.inventory_root_sha256
    assert manifest["durable_final_access_receipt_id"] == receipt.receipt_id
'''
assertion_replacement = '''    assert manifest["pre_final_id"] == pre_final.pre_final_id
    assert manifest["dataset_handoff_inventory_root"] == handoff.inventory_root_sha256
    assert manifest["durable_final_access_receipt_id"] == receipt.receipt_id
    assert manifest["dataset_schema_version"] == "candle-dataset-v4"
    assert manifest["excluded_provider_rows"] == [
        {
            "closure_id": item.closure_id,
            "provider_row_sha256": item.provider_row_sha256,
        }
        for item in handoff.excluded_provider_rows
    ]
    assert "excluded_provider_row_sha256" not in manifest
'''
if integration.count(assertion_anchor) != 1:
    raise SystemExit("unexpected integration study manifest assertions")
integration_path.write_text(
    integration.replace(assertion_anchor, assertion_replacement, 1),
    encoding="utf-8",
)
