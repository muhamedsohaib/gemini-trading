import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionResult, IngestionService
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.domain.dataset import RetrievalRequest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 14, tzinfo=UTC)
_CREATED_AT = datetime(2025, 1, 1, 14, 30, tzinfo=UTC)
_REQUEST = RetrievalRequest(_INSTRUMENT, Timeframe.H4, _START, _END)
_EXPECTED_DATASET_ID = "9c696d00d7116a7a9ef7d8b7fb7e42b75d7150e4d1254768ef87080869bd1333"
_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "binance_spot"
_FIXTURE_NAMES = (
    "ethusdt_4h_acceptance_page_1.json",
    "ethusdt_4h_acceptance_page_2.json",
)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) // timedelta(milliseconds=1)


def _fixture_bytes() -> tuple[bytes, bytes]:
    return (
        (_FIXTURE_ROOT / _FIXTURE_NAMES[0]).read_bytes(),
        (_FIXTURE_ROOT / _FIXTURE_NAMES[1]).read_bytes(),
    )


class DeterministicProvider:
    def __init__(self, payloads: tuple[bytes, ...]) -> None:
        self._payloads = payloads
        self._page_index = 0
        self.server_time_calls = 0
        self.cursors: list[datetime] = []

    def fetch_server_time(self) -> datetime:
        self.server_time_calls += 1
        return _SERVER_TIME

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        payload = self._payloads[self._page_index]
        self._page_index += 1
        self.cursors.append(cursor)
        parameters = tuple(
            sorted(
                (
                    ("symbol", request.instrument.symbol),
                    ("interval", request.timeframe.value),
                    ("startTime", str(_milliseconds(cursor))),
                    ("endTime", str(_milliseconds(request.end_time) - 1)),
                    ("limit", str(limit)),
                )
            )
        )
        return ProviderPage(
            request_parameters=parameters,
            response=HttpResponse(status_code=200, headers=(), body=payload),
            retrieved_at=_SERVER_TIME + timedelta(seconds=self._page_index),
        )


def _ingest(
    root: Path,
    run_id: str,
    payloads: tuple[bytes, ...],
) -> tuple[IngestionResult, LocalImmutableStore, DeterministicProvider]:
    store = LocalImmutableStore(root)
    provider = DeterministicProvider(payloads)
    result = IngestionService(
        provider=provider,
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
        run_id_factory=lambda: run_id,
    ).ingest(_REQUEST)
    return result, store, provider


def _json_lines(raw: bytes) -> tuple[dict[str, object], ...]:
    decoded: list[dict[str, object]] = []
    for line in raw.splitlines():
        value: object = json.loads(line)
        assert isinstance(value, dict)
        decoded.append(cast(dict[str, object], value))
    return tuple(decoded)


def test_ethusdt_4h_acceptance_matrix_is_byte_reproducible_and_verifiable(
    tmp_path: Path,
) -> None:
    payloads = _fixture_bytes()
    result, store, provider = _ingest(tmp_path, "acceptance-run-001", payloads)

    assert result.dataset_id == _EXPECTED_DATASET_ID
    assert result.raw_page_count == 2
    assert result.candle_count == 3
    assert provider.server_time_calls == 1
    assert provider.cursors == [_START, datetime(2025, 1, 1, 8, tzinfo=UTC)]

    manifest, raw_pages = store.read_run(result.run_id)
    assert manifest.status is RetrievalStatus.COMPLETED
    assert manifest.failure_type is None
    assert manifest.failure_message is None
    assert manifest.server_time_snapshot == _SERVER_TIME
    assert manifest.page_hashes == tuple(hashlib.sha256(payload).hexdigest() for payload in payloads)
    assert tuple(page.response_bytes for page in raw_pages) == payloads

    raw_directory = tmp_path / "data" / "raw" / "binance_spot" / result.run_id
    assert (raw_directory / "page-000001.json").read_bytes() == payloads[0]
    assert (raw_directory / "page-000002.json").read_bytes() == payloads[1]

    canonical_before, dataset_manifest_before = store.read_dataset(result.dataset_id)
    lines = _json_lines(canonical_before)
    assert len(lines) == 3
    assert all(line["completed"] is True for line in lines)
    assert [line["open_time"] for line in lines] == [
        "2025-01-01T00:00:00.000Z",
        "2025-01-01T04:00:00.000Z",
        "2025-01-01T08:00:00.000Z",
    ]
    assert [line["close_time"] for line in lines] == [
        "2025-01-01T03:59:59.999Z",
        "2025-01-01T07:59:59.999Z",
        "2025-01-01T11:59:59.999Z",
    ]
    assert [line["open"] for line in lines] == ["3200.1000", "3210.2500", "3218.7500"]
    assert [line["volume"] for line in lines] == [
        "123.450000",
        "98.765400",
        "110.000000",
    ]
    assert b'"open_time":"2025-01-01T12:00:00.000Z"' not in canonical_before
    assert hashlib.sha256(b"candle-dataset-v1\n" + canonical_before).hexdigest() == result.dataset_id

    replay = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
    ).replay(result.run_id)
    canonical_after, dataset_manifest_after = store.read_dataset(replay.dataset_id)
    assert replay.dataset_id == result.dataset_id
    assert canonical_after == canonical_before
    assert dataset_manifest_after == dataset_manifest_before

    verification = VerificationService(raw_store=store, canonical_store=store).verify(
        result.dataset_id,
        result.run_id,
    )
    assert verification.candle_count == 3
    assert set(verification.checks) == {
        "retrieval_manifest_bytes",
        "raw_page_hashes",
        "raw_reconstruction",
        "canonical_bytes",
        "canonical_manifest",
        "dataset_identity",
        "provenance_linkage",
        "parsed_continuity",
        "completed_state",
    }


def test_equivalent_acceptance_runs_share_identity_and_keep_separate_provenance(
    tmp_path: Path,
) -> None:
    payloads = _fixture_bytes()
    first, store, _provider = _ingest(tmp_path, "acceptance-run-001", payloads)
    second_provider = DeterministicProvider(payloads)
    second = IngestionService(
        provider=second_provider,
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
        run_id_factory=lambda: "acceptance-run-002",
    ).ingest(_REQUEST)

    assert first.dataset_id == second.dataset_id == _EXPECTED_DATASET_ID
    first_receipt = store.read_provenance(first.dataset_id, first.run_id)
    second_receipt = store.read_provenance(second.dataset_id, second.run_id)
    assert first_receipt != second_receipt
    assert b'"run_id":"acceptance-run-001"' in first_receipt
    assert b'"run_id":"acceptance-run-002"' in second_receipt


def test_production_market_data_modules_contain_no_acceptance_market_literals() -> None:
    source_root = Path(__file__).parents[2] / "src" / "gemini_trading"
    production_source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(source_root.rglob("*.py"))
    )

    for market_literal in ("ETHUSDT", "BTCUSDT", "SOLUSDT"):
        assert market_literal not in production_source
