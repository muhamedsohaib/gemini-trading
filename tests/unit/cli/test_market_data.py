import json
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.cli import market_data
from gemini_trading.cli.main import main
from gemini_trading.data.errors import ProviderSchemaError
from gemini_trading.data.ingestion.service import IngestionResult
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.safety.execution_mode import ExecutionMode, RuntimePolicy

_DATASET_ID = "d" * 64
_VALID_INGEST_ARGS = [
    "market-data",
    "ingest",
    "--symbol",
    "ETHUSDT",
    "--base-asset",
    "ETH",
    "--quote-asset",
    "USDT",
    "--interval",
    "4h",
    "--start",
    "2025-01-01T00:00:00Z",
    "--end",
    "2025-01-02T00:00:00Z",
]


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    value: object = json.loads(text)
    assert isinstance(value, dict)
    assert text == (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return cast(dict[str, object], value)


def _install_successful_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    output_root: Path,
    events: list[str] | None = None,
) -> None:
    observed = events if events is not None else []

    def fake_policy() -> RuntimePolicy:
        observed.append("policy")
        return RuntimePolicy(ExecutionMode.PAPER)

    class FakeProvider:
        def __init__(self) -> None:
            observed.append("provider")

    class FakeIngestionService:
        def __init__(
            self,
            *,
            provider: object,
            raw_store: object,
            canonical_store: object,
        ) -> None:
            del provider, raw_store, canonical_store
            observed.append("service")

        def ingest(self, request: RetrievalRequest) -> IngestionResult:
            del request
            observed.append("ingest")
            return IngestionResult(
                run_id="run-001",
                dataset_id=_DATASET_ID,
                raw_page_count=2,
                candle_count=3,
                paths=(
                    (
                        "canonical_jsonl",
                        output_root / "data" / "canonical" / _DATASET_ID / "candles.jsonl",
                    ),
                    (
                        "retrieval_manifest",
                        output_root
                        / "data"
                        / "raw"
                        / "binance_spot"
                        / "run-001"
                        / "retrieval-manifest.json",
                    ),
                ),
            )

    monkeypatch.setattr(market_data, "load_runtime_policy", fake_policy)
    monkeypatch.setattr(market_data, "BinanceSpotProvider", FakeProvider)
    monkeypatch.setattr(market_data, "IngestionService", FakeIngestionService)


def test_ingest_requires_every_explicit_identity_and_window_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["market-data", "ingest"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload["status"] == "failed"
    error_value = payload["error"]
    assert isinstance(error_value, dict)
    error = cast(dict[str, object], error_value)
    assert error["type"] == "CliUsageError"
    message: object = error["message"]
    assert isinstance(message, str)
    for flag in (
        "--symbol",
        "--base-asset",
        "--quote-asset",
        "--interval",
        "--start",
        "--end",
        "--output-root",
    ):
        assert flag in message


def test_interval_is_rejected_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider_constructed = False

    class RecordingProvider:
        def __init__(self) -> None:
            nonlocal provider_constructed
            provider_constructed = True

    monkeypatch.setattr(market_data, "BinanceSpotProvider", RecordingProvider)
    args = [*_VALID_INGEST_ARGS, "--output-root", str(tmp_path)]
    args[args.index("4h")] = "2h"

    code = main(args)

    captured = capsys.readouterr()
    assert code == 2
    assert not provider_constructed
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload["status"] == "failed"
    assert "invalid choice" in str(payload["error"])


def test_ingest_requires_z_timestamp_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider_constructed = False

    class RecordingProvider:
        def __init__(self) -> None:
            nonlocal provider_constructed
            provider_constructed = True

    monkeypatch.setattr(market_data, "BinanceSpotProvider", RecordingProvider)
    args = [*_VALID_INGEST_ARGS, "--output-root", str(tmp_path)]
    args[args.index("2025-01-01T00:00:00Z")] = "2025-01-01T00:00:00+00:00"

    code = main(args)

    captured = capsys.readouterr()
    assert code == 2
    assert not provider_constructed
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload["status"] == "failed"
    assert "must end with Z" in str(payload["error"])


def test_runtime_policy_is_checked_before_network_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []
    _install_successful_ingestion(monkeypatch, tmp_path, events)

    code = main([*_VALID_INGEST_ARGS, "--output-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert events == ["policy", "provider", "service", "ingest"]


def test_ingest_success_emits_only_compact_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_successful_ingestion(monkeypatch, tmp_path)

    code = main([*_VALID_INGEST_ARGS, "--output-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    payload = _decoded_output(captured.out)
    assert payload == {
        "candle_count": 3,
        "dataset_id": _DATASET_ID,
        "paths": {
            "canonical_jsonl": f"data/canonical/{_DATASET_ID}/candles.jsonl",
            "retrieval_manifest": "data/raw/binance_spot/run-001/retrieval-manifest.json",
        },
        "raw_page_count": 2,
        "run_id": "run-001",
        "status": "completed",
    }
    assert str(tmp_path) not in captured.out


def test_market_data_error_returns_exit_two_without_traceback_or_raw_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_policy() -> RuntimePolicy:
        return RuntimePolicy(ExecutionMode.PAPER)

    class FakeProvider:
        raw_body = b"RAW_BODY_MUST_NOT_APPEAR"

    class FailingIngestionService:
        def __init__(
            self,
            *,
            provider: object,
            raw_store: object,
            canonical_store: object,
        ) -> None:
            del provider, raw_store, canonical_store

        def ingest(self, request: RetrievalRequest) -> IngestionResult:
            del request
            raise ProviderSchemaError("provider payload is invalid")

    monkeypatch.setattr(market_data, "load_runtime_policy", fake_policy)
    monkeypatch.setattr(market_data, "BinanceSpotProvider", FakeProvider)
    monkeypatch.setattr(market_data, "IngestionService", FailingIngestionService)

    code = main([*_VALID_INGEST_ARGS, "--output-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload == {
        "error": {
            "message": "provider payload is invalid",
            "type": "ProviderSchemaError",
        },
        "status": "failed",
    }
    assert "Traceback" not in captured.err
    assert "RAW_BODY_MUST_NOT_APPEAR" not in captured.err
