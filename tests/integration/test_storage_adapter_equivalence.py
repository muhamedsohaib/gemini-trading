from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 14, tzinfo=UTC)
_REQUEST = RetrievalRequest(_INSTRUMENT, Timeframe.H4, _START, _END)
_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "binance_spot"
_FIXTURE_NAMES = (
    "ethusdt_4h_acceptance_page_1.json",
    "ethusdt_4h_acceptance_page_2.json",
)


def _milliseconds(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) // timedelta(milliseconds=1)


def _payloads() -> tuple[bytes, bytes]:
    return (
        (_FIXTURE_ROOT / _FIXTURE_NAMES[0]).read_bytes(),
        (_FIXTURE_ROOT / _FIXTURE_NAMES[1]).read_bytes(),
    )


class FixtureProvider:
    def __init__(self, payloads: tuple[bytes, bytes]) -> None:
        self._payloads = payloads
        self._index = 0

    def fetch_server_time(self) -> datetime:
        return _SERVER_TIME

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        payload = self._payloads[self._index]
        self._index += 1
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
            retrieved_at=_SERVER_TIME + timedelta(seconds=self._index),
        )


class CapturingCanonicalStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.dataset_id: str | None = None
        self.canonical_bytes: bytes | None = None
        self.manifest_bytes: bytes | None = None
        self.receipts: dict[tuple[str, str], bytes] = {}

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]:
        self.dataset_id = dataset_id
        self.canonical_bytes = jsonl_bytes
        self.manifest_bytes = manifest_bytes
        directory = self._root / "capturing-adapter" / dataset_id
        return directory / "candles.jsonl", directory / "dataset-manifest.json"

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path:
        self.receipts[(dataset_id, run_id)] = receipt_bytes
        return self._root / "capturing-adapter" / dataset_id / "provenance" / f"{run_id}.json"


def test_canonical_bytes_do_not_depend_on_canonical_storage_adapter(tmp_path: Path) -> None:
    payloads = _payloads()

    local_root = tmp_path / "local"
    local_store = LocalImmutableStore(local_root)
    local_result = IngestionService(
        provider=FixtureProvider(payloads),
        raw_store=local_store,
        canonical_store=local_store,
        clock=lambda: _SERVER_TIME,
        run_id_factory=lambda: "local-run",
    ).ingest(_REQUEST)
    local_canonical, local_manifest = local_store.read_dataset(local_result.dataset_id)

    capture_root = tmp_path / "capture"
    raw_store = LocalImmutableStore(capture_root)
    capture_store = CapturingCanonicalStore(capture_root)
    capture_result = IngestionService(
        provider=FixtureProvider(payloads),
        raw_store=raw_store,
        canonical_store=capture_store,
        clock=lambda: _SERVER_TIME,
        run_id_factory=lambda: "capture-run",
    ).ingest(_REQUEST)

    assert capture_result.dataset_id == local_result.dataset_id
    assert capture_store.dataset_id == local_result.dataset_id
    assert capture_store.canonical_bytes == local_canonical
    assert capture_store.manifest_bytes == local_manifest
    assert (capture_result.dataset_id, capture_result.run_id) in capture_store.receipts
