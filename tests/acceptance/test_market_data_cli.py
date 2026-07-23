import json
import tomllib
from pathlib import Path

import pytest

from gemini_trading.cli import market_data
from gemini_trading.cli.main import main
from gemini_trading.data.ingestion.service import IngestionResult
from gemini_trading.data.verification.service import VerificationResult

_DATASET_ID = "a" * 64


def _payload(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert ": " not in text
    assert ", " not in text
    decoded = json.loads(text)
    assert isinstance(decoded, dict)
    return decoded


def test_project_script_and_help_expose_all_market_data_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = Path(__file__).parents[2]
    configuration = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = configuration["project"]
    assert isinstance(project, dict)
    scripts = project["scripts"]
    assert isinstance(scripts, dict)
    assert scripts["gemini-trading"] == "gemini_trading.cli.main:main"

    with pytest.raises(SystemExit) as error:
        main(["market-data", "--help"])

    captured = capsys.readouterr()
    assert error.value.code == 0
    assert captured.err == ""
    assert "ingest" in captured.out
    assert "replay" in captured.out
    assert "verify" in captured.out


def test_replay_and_verify_commands_emit_compact_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeReplayService:
        def __init__(self, *, raw_store: object, canonical_store: object) -> None:
            del raw_store, canonical_store

        def replay(self, run_id: str) -> IngestionResult:
            assert run_id == "run-001"
            return IngestionResult(
                run_id=run_id,
                dataset_id=_DATASET_ID,
                raw_page_count=2,
                candle_count=3,
                paths=(
                    (
                        "canonical_jsonl",
                        tmp_path / "data" / "canonical" / _DATASET_ID / "candles.jsonl",
                    ),
                ),
            )

    class FakeVerificationService:
        def __init__(self, *, raw_store: object, canonical_store: object) -> None:
            del raw_store, canonical_store

        def verify(self, dataset_id: str, run_id: str) -> VerificationResult:
            assert dataset_id == _DATASET_ID
            assert run_id == "run-001"
            return VerificationResult(
                dataset_id=dataset_id,
                run_id=run_id,
                candle_count=3,
                checks=("raw_page_hashes", "dataset_identity"),
            )

    monkeypatch.setattr(market_data, "ReplayService", FakeReplayService)
    monkeypatch.setattr(market_data, "VerificationService", FakeVerificationService)

    replay_code = main(
        [
            "market-data",
            "replay",
            "--run-id",
            "run-001",
            "--output-root",
            str(tmp_path),
        ]
    )
    replay_captured = capsys.readouterr()
    assert replay_code == 0
    assert replay_captured.err == ""
    assert _payload(replay_captured.out) == {
        "candle_count": 3,
        "dataset_id": _DATASET_ID,
        "paths": {"canonical_jsonl": f"data/canonical/{_DATASET_ID}/candles.jsonl"},
        "raw_page_count": 2,
        "run_id": "run-001",
        "status": "completed",
    }

    verify_code = main(
        [
            "market-data",
            "verify",
            "--dataset-id",
            _DATASET_ID,
            "--run-id",
            "run-001",
            "--output-root",
            str(tmp_path),
        ]
    )
    verify_captured = capsys.readouterr()
    assert verify_code == 0
    assert verify_captured.err == ""
    assert _payload(verify_captured.out) == {
        "candle_count": 3,
        "checks": ["raw_page_hashes", "dataset_identity"],
        "dataset_id": _DATASET_ID,
        "run_id": "run-001",
        "status": "verified",
    }


def test_live_mode_is_rejected_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider_constructed = False

    class RecordingProvider:
        def __init__(self) -> None:
            nonlocal provider_constructed
            provider_constructed = True

    monkeypatch.setenv("GEMINI_TRADING_MODE", "live")
    monkeypatch.setattr(market_data, "BinanceSpotProvider", RecordingProvider)

    code = main(
        [
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
            "--output-root",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert not provider_constructed
    assert captured.out == ""
    payload = _payload(captured.err)
    assert payload["status"] == "failed"
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["type"] == "UnsafeExecutionModeError"
    assert "only research and paper are allowed" in str(error["message"])
    assert "Traceback" not in captured.err
