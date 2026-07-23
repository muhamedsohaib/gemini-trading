import hashlib
import socket
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from _pytest.monkeypatch import MonkeyPatch

from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 1, 4, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 10, tzinfo=UTC)
_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "binance_spot" / "klines_valid_two_pages_page_1.json"
)


def _forbid_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("offline replay attempted network access")


def test_replay_completes_with_network_entry_points_disabled(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    store = LocalImmutableStore(tmp_path)
    payload = _FIXTURE.read_bytes()
    page_hash = hashlib.sha256(payload).hexdigest()
    store.write_page(
        RawPage(
            run_id="run-offline",
            sequence=1,
            request_parameters=tuple(
                sorted(
                    (
                        ("symbol", "ETHUSDT"),
                        ("interval", "4h"),
                        ("startTime", "1735689600000"),
                        ("endTime", "1735703999999"),
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
            run_id="run-offline",
            provider="binance_spot",
            instrument=_INSTRUMENT,
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
    monkeypatch.setattr(urllib.request, "urlopen", _forbid_network)
    monkeypatch.setattr(socket, "create_connection", _forbid_network)

    result = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _SERVER_TIME,
    ).replay("run-offline")

    assert result.raw_page_count == 1
    assert result.candle_count == 1
