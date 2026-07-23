"""End-to-end acceptance tests for deterministic research CLI workflows."""

import json
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.cli import research
from gemini_trading.cli.main import main
from research_fixture_support import write_fixture_dataset

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_OFFICIAL_CONFIG = _PROJECT_ROOT / "tests" / "fixtures" / "research" / "official-fixture-config.json"
_DIAGNOSTIC_CONFIG = (
    _PROJECT_ROOT / "tests" / "fixtures" / "research" / "diagnostic-fixture-config.json"
)
_TEST_COMMIT = "1" * 40


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    value: object = json.loads(text)
    assert isinstance(value, dict)
    assert text == (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return cast(dict[str, object], value)


def _run(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> dict[str, object]:
    code = main(argv)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    return _decoded_output(captured.out)


def test_research_backtest_replay_and_verify_are_provider_free_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = write_fixture_dataset(tmp_path)
    monkeypatch.setattr(research, "resolve_clean_git_commit", lambda _root: _TEST_COMMIT)

    backtest = _run(
        [
            "research",
            "backtest",
            "--dataset-id",
            dataset.manifest.dataset_id,
            "--config",
            str(_OFFICIAL_CONFIG),
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )
    assert backtest["status"] == "completed"
    assert backtest["promotable"] is True
    experiment_id = cast(str, backtest["experiment_id"])
    result_id = cast(str, backtest["result_id"])
    assert len(experiment_id) == 64
    assert len(result_id) == 64
    assert str(tmp_path.resolve()) not in json.dumps(backtest)
    assert str(_PROJECT_ROOT.resolve()) not in json.dumps(backtest)

    replay = _run(
        [
            "research",
            "replay",
            "--experiment-id",
            experiment_id,
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )
    assert replay == {
        "experiment_id": experiment_id,
        "promotable": True,
        "result_id": result_id,
        "status": "completed",
    }

    verified = _run(
        [
            "research",
            "verify",
            "--experiment-id",
            experiment_id,
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )
    assert verified["status"] == "verified"
    assert verified["experiment_id"] == experiment_id
    assert verified["result_id"] == result_id
    assert verified["promotable"] is True
    checks = verified["checks"]
    assert isinstance(checks, list)
    assert checks == sorted(checks)
    assert "replay_equivalent" in checks


def test_diagnostic_fixture_is_completed_but_never_promotable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dataset = write_fixture_dataset(tmp_path)
    monkeypatch.setattr(research, "resolve_clean_git_commit", lambda _root: _TEST_COMMIT)

    payload = _run(
        [
            "research",
            "backtest",
            "--dataset-id",
            dataset.manifest.dataset_id,
            "--config",
            str(_DIAGNOSTIC_CONFIG),
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )

    assert payload["status"] == "completed"
    assert payload["promotable"] is False


def test_research_cli_rejects_live_mode_before_reading_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", "live")

    code = main(
        [
            "research",
            "verify",
            "--experiment-id",
            "a" * 64,
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["type"] == "UnsafeExecutionModeError"
    assert "Traceback" not in captured.err
    assert str(tmp_path.resolve()) not in captured.err
