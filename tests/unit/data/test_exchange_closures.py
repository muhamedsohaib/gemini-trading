# ruff: noqa: E501
"""Contracts for the fixed sealed BTCUSDT exchange-closure manifest."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import (
    load_exchange_closure_manifest,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_FIXED_RELATIVE_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_APPROVED_CLOSURE_ROWS = (
    (
        "binance-spot-infrastructure-maintenance-2018-01-04",
        "ce5df946e724e509699e24166fcd96bd566c48de7090b3a092aaa324bd73c426",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2018-02-08",
        "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2018-06-26",
        "31d7e347e1830772a39ab0bdf78e09af6ff3f3735cad745916fe32e6fe0fd557",  # pragma: allowlist secret
    ),
    (
        "binance-spot-risk-control-suspension-2018-07-04",
        "1202a2e967f8907eab3917a36f9b5bb440e4ca6647779fdebefd50bcce61b5b8",  # pragma: allowlist secret
    ),
    (
        "binance-spot-emergency-maintenance-2018-10-19",
        "3a06f4a8c191d42bebd2597f7c19932362f4d95f7fe7452f51c268209b629474",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2018-11-14",
        "dd328080cdc59124c3a0467faf719f055dc208a03a229d89dbe0ec403ebf3ee8",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2019-03-12",
        "455bc52eeca4bc7097498742c200d5ecc46019683ed37ea36ed2acb4f3d8478f",  # pragma: allowlist secret
    ),
    (
        "binance-spot-security-upgrade-2019-05-15",
        "1021733a2305723bc1dad0dd8ebd8523fdc36839ef52353018d987429508efad",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2019-08-15",
        "1f68a701351a2ae6917bf4a5d524885416dc7715a704af8e0db52d3938cff876",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2019-11-13",
        "aee4ed92909f4b8e8c957370da2499c928d304374c7db303ffd591a370c2e609",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2019-11-25",
        "2b11ed5d8fe5724c559ce91e5c922b0a98d3ae16a859eec895e128b5e1e9ac54",  # pragma: allowlist secret
    ),
    (
        "binance-spot-market-data-maintenance-2020-02-19",
        "a756811ac8139d621c6fde28980d8019fef535d7f1e17b2d4310b10370d2ac53",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2020-04-25",
        "7c11bd7bff7cd4815615ea6003cb3dbed08b214b78a2bbe722cfe22912592354",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2020-06-28",
        "bbca0d86447c44964449be1ae5bf5968e391cffad1fb16aee136f07369553a01",  # pragma: allowlist secret
    ),
    (
        "binance-spot-matching-engine-maintenance-2020-12-21",
        "b9208db0c003f68d77ffeeb7e9054c348f61ede5840db275f0d5baf84cfdd2c9",  # pragma: allowlist secret
    ),
    (
        "binance-spot-matching-engine-maintenance-2021-02-11",
        "6336454bf83a67e99118f3405c3926c444668028f1c65518d509bdf19eab6cb4",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2021-04-20",
        "bdf24e2e33ecdca4f2d6960f80dd62521e9588e72badd2497857fa4efc521393",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2021-04-25",
        "d033c7c18ec2bc9b3b545a93b7d886e5e3f8c70331ffb07f2cf04fb631108d49",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2021-08-13",
        "82ec6dfd6d5d034bd9dfa6c81a5fdcee87db14a998beb3d9dad6f3dbd860509d",  # pragma: allowlist secret
    ),
    (
        "binance-spot-system-upgrade-2021-09-29",
        "ae05924001aab056ea72c61061f0b75db9aab01ca04ca6db69c7a01f09a99924",  # pragma: allowlist secret
    ),
)


def _fixed_mapping() -> dict[str, object]:
    loaded: object = json.loads((PROJECT_ROOT / _FIXED_RELATIVE_PATH).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def _closures(mapping: dict[str, object]) -> list[dict[str, object]]:
    value = mapping["closures"]
    assert isinstance(value, list)
    raw_items = cast(list[object], value)
    assert all(isinstance(item, dict) for item in raw_items)
    return cast(list[dict[str, object]], raw_items)


def _partial(closure: dict[str, object]) -> dict[str, object]:
    value = closure["partial_candle"]
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _canonical(mapping: dict[str, object]) -> bytes:
    return (json.dumps(mapping, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _write_fixed_candidate(root: Path, mapping: dict[str, object]) -> None:
    path = root / _FIXED_RELATIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(_canonical(mapping))


def _parse_utc(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _format_utc(value: datetime) -> str:
    timespec = "milliseconds" if value.microsecond else "seconds"
    return value.isoformat(timespec=timespec).replace("+00:00", "Z")


def _shifted_zero_missing_closure(
    source: dict[str, object],
    *,
    closure_id: str,
    digest: str,
    touch: bool = False,
) -> dict[str, object]:
    resumed = _parse_utc(source["resumed_open"])
    start = resumed if touch else resumed + timedelta(hours=4)
    expected_close = start + timedelta(hours=4) - timedelta(milliseconds=1)
    clone = json.loads(json.dumps(source))
    assert isinstance(clone, dict)
    closure = cast(dict[str, object], clone)
    closure.update(
        closure_id=closure_id,
        canonical_gap_start=_format_utc(start),
        resumed_open=_format_utc(start + timedelta(hours=4)),
        unavailable_candle_count=1,
        fully_missing_start=_format_utc(start + timedelta(hours=4)),
        fully_missing_candle_count=0,
    )
    partial = _partial(closure)
    partial.update(
        open_time=_format_utc(start),
        actual_close_time=_format_utc(start + timedelta(hours=1)),
        expected_close_time=_format_utc(expected_close),
        provider_row_sha256=digest,
    )
    return closure


def test_fixed_manifest_is_canonical_and_exact_v3() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.schema_version == "exchange-closure-manifest-v3"
    assert manifest.provider == "binance_spot"
    assert manifest.instrument.symbol == "BTCUSDT"
    assert manifest.timeframe.value == "4h"
    assert len(manifest.closures) == 20
    assert sum(item.unavailable_candle_count for item in manifest.closures) == 36
    assert sum(item.fully_missing_candle_count for item in manifest.closures) == 16
    actual_rows = tuple(
        (item.closure_id, item.partial_candle.provider_row_sha256) for item in manifest.closures
    )
    assert actual_rows == _APPROVED_CLOSURE_ROWS


def test_zero_fully_missing_closure_resumes_at_next_open() -> None:
    manifest, _ = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    zero_missing = tuple(item for item in manifest.closures if item.fully_missing_candle_count == 0)
    assert len(zero_missing) == 12
    for closure in zero_missing:
        assert closure.unavailable_candle_count == 1
        assert closure.fully_missing_start == closure.resumed_open


@pytest.mark.parametrize(
    "schema_version",
    ["exchange-closure-manifest-v1", "exchange-closure-manifest-v2"],
)
def test_manifest_rejects_legacy_schema(schema_version: str) -> None:
    mapping = _fixed_mapping()
    mapping["schema_version"] = schema_version
    with pytest.raises(CandleValidationError, match="schema"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_extra_fields() -> None:
    mapping = _fixed_mapping()
    mapping["unexpected"] = True
    with pytest.raises(CandleValidationError, match="fields"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_noncanonical_whitespace() -> None:
    mapping = _fixed_mapping()
    with pytest.raises(CandleValidationError, match="canonical"):
        load_exchange_closure_manifest(json.dumps(mapping, indent=2).encode())


def test_manifest_rejects_duplicate_closure_ids() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    duplicate = _shifted_zero_missing_closure(
        closures[0],
        closure_id=cast(str, closures[0]["closure_id"]),
        digest="0" * 64,
    )
    closures.append(duplicate)
    with pytest.raises(CandleValidationError, match="duplicate"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_duplicate_partial_opens() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    clone = json.loads(json.dumps(closures[0]))
    assert isinstance(clone, dict)
    duplicate = cast(dict[str, object], clone)
    duplicate["closure_id"] = "duplicate-partial-open"
    _partial(duplicate)["provider_row_sha256"] = "0" * 64
    closures.append(duplicate)
    with pytest.raises(CandleValidationError, match=r"duplicate.*partial.*open"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_duplicate_provider_row_digests() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    digest = _partial(closures[0])["provider_row_sha256"]
    assert isinstance(digest, str)
    closures.append(
        _shifted_zero_missing_closure(
            closures[0],
            closure_id="duplicate-provider-row",
            digest=digest,
        )
    )
    with pytest.raises(CandleValidationError, match=r"duplicate.*provider-row"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_non_utc_partial_timestamp() -> None:
    mapping = _fixed_mapping()
    _partial(_closures(mapping)[0])["actual_close_time"] = "2018-02-08T04:28:14.788+04:00"
    with pytest.raises(CandleValidationError, match="UTC"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_expected_close_mismatch() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    open_time = _parse_utc(partial["open_time"])
    partial["expected_close_time"] = _format_utc(
        open_time + timedelta(hours=4) - timedelta(milliseconds=2)
    )
    with pytest.raises(CandleValidationError, match="expected close"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_close_not_strictly_inside_slot() -> None:
    mapping = _fixed_mapping()
    partial = _partial(_closures(mapping)[0])
    partial["actual_close_time"] = partial["expected_close_time"]
    with pytest.raises(CandleValidationError, match="partial candle"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_invalid_provider_row_sha256() -> None:
    mapping = _fixed_mapping()
    _partial(_closures(mapping)[0])["provider_row_sha256"] = "abc"
    with pytest.raises(CandleValidationError, match="SHA-256"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_unavailable_count() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure["unavailable_candle_count"] = cast(int, closure["unavailable_candle_count"]) + 1
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_wrong_fully_missing_count() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    closure["fully_missing_candle_count"] = cast(int, closure["fully_missing_candle_count"]) + 1
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_negative_fully_missing_count() -> None:
    mapping = _fixed_mapping()
    _closures(mapping)[0]["fully_missing_candle_count"] = -1
    with pytest.raises(CandleValidationError, match="fully-missing"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_partial_open_not_equal_to_gap_start() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    partial = _partial(closure)
    gap_start = _parse_utc(closure["canonical_gap_start"])
    shifted = gap_start + timedelta(hours=4)
    partial.update(
        open_time=_format_utc(shifted),
        actual_close_time=_format_utc(shifted + timedelta(hours=1)),
        expected_close_time=_format_utc(shifted + timedelta(hours=4) - timedelta(milliseconds=1)),
    )
    with pytest.raises(CandleValidationError, match="gap start"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_fully_missing_start_not_next_slot() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    gap_start = _parse_utc(closure["canonical_gap_start"])
    closure["fully_missing_start"] = _format_utc(gap_start + timedelta(hours=8))
    with pytest.raises(CandleValidationError, match="fully missing"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_shifted_resumption() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    resumed = _parse_utc(closure["resumed_open"])
    closure["resumed_open"] = _format_utc(resumed + timedelta(hours=4))
    with pytest.raises(CandleValidationError, match="count"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_unordered_entries() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    closures.append(
        _shifted_zero_missing_closure(
            closures[0],
            closure_id="later-closure",
            digest="0" * 64,
        )
    )
    closures[0], closures[1] = closures[1], closures[0]
    with pytest.raises(CandleValidationError, match="ordered"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_manifest_rejects_touching_entries() -> None:
    mapping = _fixed_mapping()
    closures = _closures(mapping)
    closures.insert(
        1,
        _shifted_zero_missing_closure(
            closures[0],
            closure_id="touching-closure",
            digest="1" * 64,
            touch=True,
        ),
    )
    with pytest.raises(CandleValidationError, match="overlap or touch"):
        load_exchange_closure_manifest(_canonical(mapping))


def test_fixed_loader_rejects_wrong_market_identity(tmp_path: Path) -> None:
    mapping = _fixed_mapping()
    instrument = mapping["instrument"]
    assert isinstance(instrument, dict)
    instrument["symbol"] = "ETHUSDT"
    instrument["base_asset"] = "ETH"
    _write_fixed_candidate(tmp_path, mapping)

    with pytest.raises(CandleValidationError, match="identity"):
        load_fixed_btcusdt_closure_manifest(tmp_path)


def test_manifest_rejects_closure_outside_request_window() -> None:
    mapping = _fixed_mapping()
    closure = _closures(mapping)[0]
    partial = _partial(closure)
    closure.update(
        canonical_gap_start="2017-12-31T20:00:00Z",
        resumed_open="2018-01-01T00:00:00Z",
        unavailable_candle_count=1,
        fully_missing_start="2018-01-01T00:00:00Z",
        fully_missing_candle_count=0,
    )
    partial.update(
        open_time="2017-12-31T20:00:00Z",
        actual_close_time="2017-12-31T21:00:00Z",
        expected_close_time="2017-12-31T23:59:59.999Z",
    )
    with pytest.raises(CandleValidationError, match="window"):
        load_exchange_closure_manifest(_canonical(mapping))
