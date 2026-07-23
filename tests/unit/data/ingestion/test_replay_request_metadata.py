import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 1, 4, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 10, tzinfo=UTC)
_FIXTURE = (
    Path(__file__).parents[3] / "fixtures" / "binance_spot" / "klines_valid_two_pages_page_1.json"
)


def _milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def test_replay_rejects_manifest_instrument_tampering_against_request_metadata(
    tmp_path: Path,
) -> None:
    store = LocalImmutableStore(tmp_path)
    payload = _FIXTURE.read_bytes()
    page_hash = hashlib.sha256(payload).hexdigest()
    store.write_page(
        RawPage(
            run_id="run-metadata",
            sequence=1,
            request_parameters=tuple(
                sorted(
                    (
                        ("symbol", "ETHUSDT"),
                        ("interval", "4h"),
                        ("startTime", str(_milliseconds(_START))),
                        ("endTime", str(_milliseconds(_END) - 1)),
                        ("limit", "1000"),
                    )
                )
            ),
            retrieved_at=_SERVER_TIME,
            server_time_snapshot=_SERVER_TIME,
            http_status=200,
            response_bytes=payload,
            response_sha256=page_hash,
        )
    )
    store.write_retrieval_manifest(
        RetrievalManifest(
            schema_version="retrieval-manifest-v1",
            run_id="run-metadata",
            provider="binance_spot",
            instrument=Instrument("BTCUSDT", "BTC", "USDT"),
            timeframe=Timeframe.H4,
            start_time=_START,
            end_time=_END,
            server_time_snapshot=_SERVER_TIME,
            page_hashes=(page_hash,),
            retry_count=0,
            status=RetrievalStatus.COMPLETED,
            failure_type=None,
            failure_message=None,
        )
    )

    with pytest.raises(MarketDataError, match="request parameters"):
        ReplayService(
            raw_store=store,
            canonical_store=store,
            clock=lambda: _SERVER_TIME,
        ).replay("run-metadata")
