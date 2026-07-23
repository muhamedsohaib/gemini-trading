from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import assume, given
from hypothesis import strategies as st

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    dataset_id,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_OPEN_TIME = datetime(2025, 1, 1, tzinfo=UTC)
_CLOSE_TIME = datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC)
_SCHEMA_VERSION = "candle-dataset-v1"
_DECIMAL_VALUES = st.integers(min_value=-10_000_000, max_value=10_000_000)
_HASH_VALUES = st.integers(min_value=0, max_value=(1 << 256) - 1)


def _decimal(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.00"))


def _candle(*, open_value: int, close_value: int, volume_value: int) -> Candle:
    return Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        open_time=_OPEN_TIME,
        close_time=_CLOSE_TIME,
        open=_decimal(open_value),
        high=Decimal("999999.9900"),
        low=Decimal("-999999.9900"),
        close=_decimal(close_value),
        volume=_decimal(volume_value),
        completed=True,
        source_provider="binance_spot",
    )


@given(
    open_value=_DECIMAL_VALUES,
    close_value=_DECIMAL_VALUES,
    volume_value=_DECIMAL_VALUES,
)
def test_identical_candles_always_produce_identical_bytes_manifest_and_identity(
    open_value: int,
    close_value: int,
    volume_value: int,
) -> None:
    candle = _candle(
        open_value=open_value,
        close_value=close_value,
        volume_value=volume_value,
    )

    first_bytes = serialize_candles((candle,))
    second_bytes = serialize_candles((candle,))
    first_identity = dataset_id(_SCHEMA_VERSION, first_bytes)
    second_identity = dataset_id(_SCHEMA_VERSION, second_bytes)
    first_manifest = build_dataset_manifest(
        schema_version=_SCHEMA_VERSION,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_OPEN_TIME,
        end_time=_OPEN_TIME + timedelta(days=1),
        candles=(candle,),
        canonical_bytes=first_bytes,
    )
    second_manifest = build_dataset_manifest(
        schema_version=_SCHEMA_VERSION,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_OPEN_TIME,
        end_time=_OPEN_TIME + timedelta(days=1),
        candles=(candle,),
        canonical_bytes=second_bytes,
    )

    assert first_bytes == second_bytes
    assert first_identity == second_identity
    assert serialize_dataset_manifest(first_manifest) == serialize_dataset_manifest(second_manifest)


@given(
    original_close=_DECIMAL_VALUES,
    changed_close=_DECIMAL_VALUES,
    open_value=_DECIMAL_VALUES,
    volume_value=_DECIMAL_VALUES,
)
def test_changing_a_canonical_value_changes_bytes_and_content_identity(
    original_close: int,
    changed_close: int,
    open_value: int,
    volume_value: int,
) -> None:
    assume(original_close != changed_close)
    original = _candle(
        open_value=open_value,
        close_value=original_close,
        volume_value=volume_value,
    )
    changed = _candle(
        open_value=open_value,
        close_value=changed_close,
        volume_value=volume_value,
    )

    original_bytes = serialize_candles((original,))
    changed_bytes = serialize_candles((changed,))

    assert original_bytes != changed_bytes
    assert dataset_id(_SCHEMA_VERSION, original_bytes) != dataset_id(
        _SCHEMA_VERSION,
        changed_bytes,
    )


@given(
    first_run=st.integers(min_value=0, max_value=1_000_000),
    second_run=st.integers(min_value=0, max_value=1_000_000),
    first_page_hash=_HASH_VALUES,
    second_page_hash=_HASH_VALUES,
)
def test_changing_only_run_metadata_never_changes_canonical_bytes_or_identity(
    first_run: int,
    second_run: int,
    first_page_hash: int,
    second_page_hash: int,
) -> None:
    assume(first_run != second_run or first_page_hash != second_page_hash)
    candle = _candle(open_value=10_000, close_value=10_500, volume_value=1_234)
    canonical = serialize_candles((candle,))
    identity = dataset_id(_SCHEMA_VERSION, canonical)
    first_receipt = build_provenance(
        schema_version="dataset-provenance-v1",
        dataset_id=identity,
        run_id=f"run-{first_run}",
        page_hashes=(f"{first_page_hash:064x}",),
        retrieval_manifest_sha256="a" * 64,
        linked=True,
        created_at=datetime(2025, 1, 2, tzinfo=UTC),
    )
    second_receipt = build_provenance(
        schema_version="dataset-provenance-v1",
        dataset_id=identity,
        run_id=f"run-{second_run}",
        page_hashes=(f"{second_page_hash:064x}",),
        retrieval_manifest_sha256="b" * 64,
        linked=True,
        created_at=datetime(2025, 1, 3, tzinfo=UTC),
    )

    assert serialize_provenance(first_receipt) != serialize_provenance(second_receipt)
    assert serialize_candles((candle,)) == canonical
    assert dataset_id(_SCHEMA_VERSION, canonical) == identity
