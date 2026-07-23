"""Deterministic JSONL datasets, manifests, and provenance receipts."""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest, DatasetProvenance
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _format_decimal(value: Decimal) -> str:
    return format(value, "f")


def _json_bytes(payload: dict[str, object]) -> bytes:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def _instrument_payload(instrument: Instrument) -> dict[str, object]:
    return {
        "symbol": instrument.symbol,
        "base_asset": instrument.base_asset,
        "quote_asset": instrument.quote_asset,
    }


def _candle_payload(candle: Candle) -> dict[str, object]:
    if not candle.completed:
        raise ValueError("canonical datasets require completed candles")
    return {
        "symbol": candle.instrument.symbol,
        "base_asset": candle.instrument.base_asset,
        "quote_asset": candle.instrument.quote_asset,
        "timeframe": candle.timeframe.value,
        "open_time": _format_datetime(candle.open_time),
        "close_time": _format_datetime(candle.close_time),
        "open": _format_decimal(candle.open),
        "high": _format_decimal(candle.high),
        "low": _format_decimal(candle.low),
        "close": _format_decimal(candle.close),
        "volume": _format_decimal(candle.volume),
        "completed": candle.completed,
        "source_provider": candle.source_provider,
    }


def serialize_candles(candles: Sequence[Candle]) -> bytes:
    """Serialize canonical candles as compact deterministic JSON Lines."""

    return b"".join(_json_bytes(_candle_payload(candle)) for candle in candles)


def dataset_id(schema_version: str, canonical_bytes: bytes) -> str:
    """Return the content-addressed identity for canonical dataset bytes."""

    if not schema_version.strip():
        raise ValueError("schema_version must not be empty")
    identity_input = schema_version.encode("utf-8") + b"\n" + canonical_bytes
    return hashlib.sha256(identity_input).hexdigest()


def build_dataset_manifest(
    *,
    schema_version: str,
    provider: str,
    instrument: Instrument,
    timeframe: Timeframe,
    start_time: datetime,
    end_time: datetime,
    candles: Sequence[Candle],
    canonical_bytes: bytes,
) -> DatasetManifest:
    """Build deterministic metadata derived only from canonical and stable inputs."""

    candle_values = tuple(candles)
    if not candle_values:
        raise ValueError("canonical dataset must contain at least one candle")
    return DatasetManifest(
        schema_version=schema_version,
        dataset_id=dataset_id(schema_version, canonical_bytes),
        provider=provider,
        instrument=instrument,
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        first_open_time=candle_values[0].open_time,
        last_open_time=candle_values[-1].open_time,
        candle_count=len(candle_values),
        canonical_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
    )


def serialize_dataset_manifest(manifest: DatasetManifest) -> bytes:
    """Serialize a deterministic canonical dataset manifest."""

    return _json_bytes(
        {
            "schema_version": manifest.schema_version,
            "dataset_id": manifest.dataset_id,
            "provider": manifest.provider,
            "instrument": _instrument_payload(manifest.instrument),
            "timeframe": manifest.timeframe.value,
            "start_time": _format_datetime(manifest.start_time),
            "end_time": _format_datetime(manifest.end_time),
            "first_open_time": _format_datetime(manifest.first_open_time),
            "last_open_time": _format_datetime(manifest.last_open_time),
            "candle_count": manifest.candle_count,
            "canonical_sha256": manifest.canonical_sha256,
        }
    )


def build_provenance(
    *,
    schema_version: str,
    dataset_id: str,
    run_id: str,
    page_hashes: tuple[str, ...],
    retrieval_manifest_sha256: str,
    linked: bool,
    created_at: datetime,
) -> DatasetProvenance:
    """Build one run-specific receipt linking raw evidence to canonical identity."""

    return DatasetProvenance(
        schema_version=schema_version,
        dataset_id=dataset_id,
        run_id=run_id,
        page_hashes=page_hashes,
        retrieval_manifest_sha256=retrieval_manifest_sha256,
        linked=linked,
        created_at=created_at,
    )


def serialize_provenance(receipt: DatasetProvenance) -> bytes:
    """Serialize a run-specific provenance receipt deterministically."""

    return _json_bytes(
        {
            "schema_version": receipt.schema_version,
            "dataset_id": receipt.dataset_id,
            "run_id": receipt.run_id,
            "page_hashes": list(receipt.page_hashes),
            "retrieval_manifest_sha256": receipt.retrieval_manifest_sha256,
            "linked": receipt.linked,
            "created_at": _format_datetime(receipt.created_at),
        }
    )
