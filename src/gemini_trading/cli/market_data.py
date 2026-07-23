"""Safe command handlers for bounded market-data operations."""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionResult, IngestionService
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationResult, VerificationService
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.safety.execution_mode import load_runtime_policy


class CliUsageError(ValueError):
    """Raised when command-line arguments are incomplete or invalid."""


def _argument(arguments: argparse.Namespace, name: str) -> str:
    value: object = getattr(arguments, name, None)
    if not isinstance(value, str) or not value:
        raise CliUsageError(f"missing command-line argument: --{name.replace('_', '-')}")
    return value


def _parse_utc_z(value: str, flag_name: str) -> datetime:
    if not value.endswith("Z"):
        raise CliUsageError(f"{flag_name} must end with Z")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        raise CliUsageError(f"{flag_name} must be a valid ISO-8601 UTC timestamp") from None
    if parsed.utcoffset() != timedelta(0):
        raise CliUsageError(f"{flag_name} must be UTC")
    return parsed.astimezone(UTC)


def _safe_paths(
    paths: tuple[tuple[str, Path], ...],
    output_root: Path,
) -> dict[str, str]:
    root = output_root.resolve(strict=False)
    safe: dict[str, str] = {}
    for name, path in paths:
        try:
            relative = path.resolve(strict=False).relative_to(root)
        except ValueError:
            raise MarketDataError("result path escaped the configured output root") from None
        safe[name] = relative.as_posix()
    return safe


def _ingestion_payload(result: IngestionResult, output_root: Path) -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": result.run_id,
        "dataset_id": result.dataset_id,
        "raw_page_count": result.raw_page_count,
        "candle_count": result.candle_count,
        "paths": _safe_paths(result.paths, output_root),
    }


def _verification_payload(result: VerificationResult) -> dict[str, object]:
    return {
        "status": "verified",
        "dataset_id": result.dataset_id,
        "run_id": result.run_id,
        "candle_count": result.candle_count,
        "checks": list(result.checks),
    }


def _ingest(arguments: argparse.Namespace) -> dict[str, object]:
    try:
        instrument = Instrument(
            _argument(arguments, "symbol"),
            _argument(arguments, "base_asset"),
            _argument(arguments, "quote_asset"),
        )
        timeframe = Timeframe(_argument(arguments, "interval"))
        request = RetrievalRequest(
            instrument=instrument,
            timeframe=timeframe,
            start_time=_parse_utc_z(_argument(arguments, "start"), "--start"),
            end_time=_parse_utc_z(_argument(arguments, "end"), "--end"),
        )
    except ValueError as error:
        if isinstance(error, CliUsageError):
            raise
        raise CliUsageError(str(error)) from None

    output_root = Path(_argument(arguments, "output_root"))
    load_runtime_policy()
    store = LocalImmutableStore(output_root)
    provider = BinanceSpotProvider()
    result = IngestionService(
        provider=provider,
        raw_store=store,
        canonical_store=store,
    ).ingest(request)
    return _ingestion_payload(result, output_root)


def _replay(arguments: argparse.Namespace) -> dict[str, object]:
    run_id = _argument(arguments, "run_id")
    output_root = Path(_argument(arguments, "output_root"))
    store = LocalImmutableStore(output_root)
    result = ReplayService(raw_store=store, canonical_store=store).replay(run_id)
    return _ingestion_payload(result, output_root)


def _verify(arguments: argparse.Namespace) -> dict[str, object]:
    dataset_id = _argument(arguments, "dataset_id")
    run_id = _argument(arguments, "run_id")
    output_root = Path(_argument(arguments, "output_root"))
    store = LocalImmutableStore(output_root)
    result = VerificationService(raw_store=store, canonical_store=store).verify(
        dataset_id,
        run_id,
    )
    return _verification_payload(result)


def run_market_data(arguments: argparse.Namespace) -> dict[str, object]:
    """Execute one parsed market-data command and return a safe JSON payload."""

    command = _argument(arguments, "market_data_command")
    if command == "ingest":
        return _ingest(arguments)
    if command == "replay":
        return _replay(arguments)
    if command == "verify":
        return _verify(arguments)
    raise CliUsageError(f"unsupported market-data command: {command}")
