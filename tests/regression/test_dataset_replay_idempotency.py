import hashlib
from datetime import UTC, datetime
from pathlib import Path

from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 1, 4, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 10, tzinfo=UTC)
_FIRST_REPLAY_TIME = datetime(2025, 1, 1, 11, tzinfo=UTC)
_SECOND_REPLAY_TIME = datetime(2025, 1, 1, 12, tzinfo=UTC)
_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "binance_spot"
    / "klines_valid_two_pages_page_1.json"
)


def _seed_completed_run(store: LocalImmutableStore) -> None:
    payload = _FIXTURE.read_bytes()
    page_hash = hashlib.sha256(payload).hexdigest()
    store.write_page(
        RawPage(
            run_id="run-idempotent",
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
            run_id="run-idempotent",
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


def test_replaying_same_run_preserves_existing_immutable_provenance(
    tmp_path: Path,
) -> None:
    store = LocalImmutableStore(tmp_path)
    _seed_completed_run(store)

    first = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _FIRST_REPLAY_TIME,
    ).replay("run-idempotent")
    original_receipt = store.read_provenance(first.dataset_id, first.run_id)

    second = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _SECOND_REPLAY_TIME,
    ).replay("run-idempotent")

    assert second.dataset_id == first.dataset_id
    assert second.run_id == first.run_id
    assert store.read_provenance(second.dataset_id, second.run_id) == original_receipt
