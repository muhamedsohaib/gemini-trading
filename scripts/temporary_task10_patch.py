"""Apply the temporary Task 10 handoff-v4 evidence propagation patch."""

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"unexpected {label} structure")
    return text.replace(old, new, 1)


pre_path = Path("src/gemini_trading/strategy/pre_final.py")
pre = pre_path.read_text(encoding="utf-8")
pre = replace_once(
    pre,
    "from gemini_trading.strategy.handoff import DatasetHandoffManifest",
    "from gemini_trading.strategy.handoff import DatasetHandoffManifest, ExcludedProviderRow",
    "pre-final handoff import",
)
pre = replace_once(
    pre,
    '"schema_version": "dataset-handoff-reference-v3",',
    '"schema_version": "dataset-handoff-reference-v4",',
    "handoff reference schema",
)
pre = replace_once(
    pre,
    '        "excluded_provider_row_sha256": handoff.excluded_provider_row_sha256,',
    '''        "excluded_provider_rows": [
            {
                "closure_id": item.closure_id,
                "provider_row_sha256": item.provider_row_sha256,
            }
            for item in handoff.excluded_provider_rows
        ],''',
    "handoff reference row identity",
)
pre = replace_once(
    pre,
    "    excluded_provider_row_sha256: str,",
    "    excluded_provider_rows: tuple[ExcludedProviderRow, ...],",
    "pre-final identity signature",
)
pre = replace_once(
    pre,
    '        "excluded_provider_row_sha256": excluded_provider_row_sha256,',
    '''        "excluded_provider_rows": [
            {
                "closure_id": item.closure_id,
                "provider_row_sha256": item.provider_row_sha256,
            }
            for item in excluded_provider_rows
        ],''',
    "pre-final identity payload",
)
pre = replace_once(
    pre,
    "        excluded_provider_row_sha256=handoff.excluded_provider_row_sha256,",
    "        excluded_provider_rows=handoff.excluded_provider_rows,",
    "pre-final identity call",
)
pre = pre.replace('"excluded_provider_row_sha256",', '"excluded_provider_rows",')
required_int_anchor = '''def _required_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PreFinalArtifactError(f"invalid pre-final field: {key}")
    return value
'''
required_rows = required_int_anchor + '''

def _required_excluded_rows(
    mapping: Mapping[str, object], key: str
) -> tuple[ExcludedProviderRow, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise PreFinalArtifactError(f"invalid pre-final field: {key}")
    rows: list[ExcludedProviderRow] = []
    for raw_row in cast(list[object], value):
        if not isinstance(raw_row, dict):
            raise PreFinalArtifactError(f"invalid pre-final field: {key}")
        row = cast(dict[object, object], raw_row)
        if set(row) != {"closure_id", "provider_row_sha256"}:
            raise PreFinalArtifactError(f"invalid pre-final field: {key}")
        closure_id = row.get("closure_id")
        provider_row_sha256 = row.get("provider_row_sha256")
        if not isinstance(closure_id, str) or not isinstance(provider_row_sha256, str):
            raise PreFinalArtifactError(f"invalid pre-final field: {key}")
        rows.append(ExcludedProviderRow(closure_id, provider_row_sha256))
    return tuple(rows)
'''
pre = replace_once(pre, required_int_anchor, required_rows, "pre-final row parser")
pre = replace_once(
    pre,
    '            "excluded_provider_row_sha256": expected_handoff.excluded_provider_row_sha256,',
    '''            "excluded_provider_rows": [
                {
                    "closure_id": item.closure_id,
                    "provider_row_sha256": item.provider_row_sha256,
                }
                for item in expected_handoff.excluded_provider_rows
            ],''',
    "pre-final expected row identity",
)
pre = replace_once(
    pre,
    '        excluded_provider_row_sha256=_required_str(manifest, "excluded_provider_row_sha256"),',
    '        excluded_provider_rows=_required_excluded_rows(manifest, "excluded_provider_rows"),',
    "pre-final rebuilt row identity",
)
pre_path.write_text(pre, encoding="utf-8")

replay_path = Path("src/gemini_trading/strategy/replay.py")
replay = replay_path.read_text(encoding="utf-8")
replay = replace_once(
    replay,
    "from gemini_trading.strategy.errors import StudyReplayMismatchError",
    "from gemini_trading.strategy.errors import StudyReplayMismatchError\n"
    "from gemini_trading.strategy.handoff import ExcludedProviderRow",
    "replay handoff import",
)
replay = replay.replace('"excluded_provider_row_sha256",', '"excluded_provider_rows",')
replay = replace_once(
    replay,
    "    excluded_provider_row_sha256: str | None = None",
    "    excluded_provider_rows: tuple[ExcludedProviderRow, ...] = ()",
    "stored manifest row field",
)
tuple_anchor = '''def _required_positive_int_tuple(
    mapping: Mapping[str, object], key: str, description: str
) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    values = cast(list[object], value)
    if not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in values
    ):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    return tuple(cast(list[int], values))
'''
row_parser = tuple_anchor + '''

def _required_excluded_rows(
    mapping: Mapping[str, object], key: str, description: str
) -> tuple[ExcludedProviderRow, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise StudyReplayMismatchError(f"invalid {description} field: {key}")
    rows: list[ExcludedProviderRow] = []
    for raw_row in cast(list[object], value):
        if not isinstance(raw_row, dict):
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        row = cast(dict[object, object], raw_row)
        if set(row) != {"closure_id", "provider_row_sha256"}:
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        closure_id = row.get("closure_id")
        provider_row_sha256 = row.get("provider_row_sha256")
        if not isinstance(closure_id, str) or not isinstance(provider_row_sha256, str):
            raise StudyReplayMismatchError(f"invalid {description} field: {key}")
        try:
            rows.append(ExcludedProviderRow(closure_id, provider_row_sha256))
        except Exception:
            raise StudyReplayMismatchError(f"invalid {description} field: {key}") from None
    return tuple(rows)
'''
replay = replace_once(replay, tuple_anchor, row_parser, "replay row parser")
scalar_parse = '''        excluded_provider_row_sha256=(
            _sha256(
                _required_str(
                    mapping,
                    "excluded_provider_row_sha256",
                    "strategy study manifest",
                ),
                "excluded provider-row identity",
            )
            if sealed
            else None
        ),'''
plural_parse = '''        excluded_provider_rows=(
            _required_excluded_rows(
                mapping,
                "excluded_provider_rows",
                "strategy study manifest",
            )
            if sealed
            else ()
        ),'''
replay = replace_once(replay, scalar_parse, plural_parse, "replay row parsing")
replay = replace_once(
    replay,
    '        if manifest.dataset_schema_version != "candle-dataset-v3":\n'
    '            raise StudyReplayMismatchError("sealed study requires candle-dataset-v3")',
    '        if manifest.dataset_schema_version != "candle-dataset-v4":\n'
    '            raise StudyReplayMismatchError("sealed study requires candle-dataset-v4")',
    "replay dataset schema",
)
replay = replace_once(
    replay,
    '''        if manifest.excluded_provider_row_sha256 is None:
            raise StudyReplayMismatchError("sealed study lacks excluded row identity")
        if len(manifest.closure_ids) != manifest.closure_count:
            raise StudyReplayMismatchError("invalid sealed study closure IDs")''',
    '''        if len(manifest.excluded_provider_rows) != manifest.exclusion_count:
            raise StudyReplayMismatchError("invalid sealed study excluded row count")
        if len(manifest.closure_ids) != manifest.closure_count:
            raise StudyReplayMismatchError("invalid sealed study closure IDs")
        if tuple(item.closure_id for item in manifest.excluded_provider_rows) != manifest.closure_ids:
            raise StudyReplayMismatchError("invalid sealed study excluded row order")
        if len({item.provider_row_sha256 for item in manifest.excluded_provider_rows}) != len(
            manifest.excluded_provider_rows
        ):
            raise StudyReplayMismatchError("duplicate sealed study excluded row identity")''',
    "replay plural row validation",
)
replay_path.write_text(replay, encoding="utf-8")

evaluator_path = Path("src/gemini_trading/strategy/sealed_evaluator.py")
evaluator = evaluator_path.read_text(encoding="utf-8")
evaluator = evaluator.replace('"candle-dataset-v3"', '"candle-dataset-v4"')
evaluator = evaluator.replace("dataset v3 evidence", "dataset v4 evidence")
evaluator = replace_once(
    evaluator,
    '''    if len(exclusion_manifest.exclusions) != 1:
        raise StudyArtifactError("sealed candidate evaluation requires one exclusion")''',
    '''    if (
        dataset.manifest.closure_count,
        dataset.manifest.exclusion_count,
        dataset.manifest.segment_count,
    ) != (20, 20, 21):
        raise StudyArtifactError("sealed candidate evaluation evidence counts mismatch")
    if tuple(item.closure_id for item in exclusion_manifest.exclusions) != tuple(
        item.closure_id for item in closure_manifest.closures
    ):
        raise StudyArtifactError("sealed candidate exclusion order mismatch")''',
    "evaluator exclusion count",
)
evaluator = replace_once(
    evaluator,
    '            "excluded_provider_row_sha256": exclusion_manifest.exclusions[0].provider_row_sha256,',
    '''            "excluded_provider_rows": [
                {
                    "closure_id": item.closure_id,
                    "provider_row_sha256": item.provider_row_sha256,
                }
                for item in exclusion_manifest.exclusions
            ],''',
    "evaluator configuration rows",
)
evaluator = replace_once(
    evaluator,
    '            "excluded_provider_row_sha256": handoff.excluded_provider_row_sha256,',
    '''            "excluded_provider_rows": [
                {
                    "closure_id": item.closure_id,
                    "provider_row_sha256": item.provider_row_sha256,
                }
                for item in handoff.excluded_provider_rows
            ],''',
    "evaluator study manifest rows",
)
evaluator_path.write_text(evaluator, encoding="utf-8")

verification_path = Path("src/gemini_trading/strategy/sealed_verification.py")
verification = verification_path.read_text(encoding="utf-8")
verification = replace_once(
    verification,
    "        or manifest.excluded_provider_row_sha256 != handoff.excluded_provider_row_sha256",
    "        or manifest.excluded_provider_rows != handoff.excluded_provider_rows",
    "sealed verification row identity",
)
verification_path.write_text(verification, encoding="utf-8")
