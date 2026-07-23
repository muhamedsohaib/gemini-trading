"""Unit tests for the safe deterministic research CLI surface."""

import json
from pathlib import Path
from typing import cast

import pytest

import gemini_trading.cli.main as cli_main
from gemini_trading.cli import research
from gemini_trading.safety.execution_mode import UnsafeExecutionModeError


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    value: object = json.loads(text)
    assert isinstance(value, dict)
    assert text == (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return cast(dict[str, object], value)


def test_research_backtest_requires_every_explicit_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli_main.main(["research", "backtest"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload["status"] == "failed"
    for flag in ("--dataset-id", "--config", "--project-root", "--output-root"):
        assert flag in str(payload["error"])


def test_research_runtime_policy_is_loaded_before_config_or_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []

    def reject_mode() -> object:
        events.append("policy")
        raise UnsafeExecutionModeError("unsafe research mode")

    def fail_config(_path: Path) -> object:
        events.append("config")
        raise AssertionError("configuration must not be read before runtime policy")

    monkeypatch.setattr(research, "load_runtime_policy", reject_mode)
    monkeypatch.setattr(research, "_load_config", fail_config)

    code = cli_main.main(
        [
            "research",
            "backtest",
            "--dataset-id",
            "a" * 64,
            "--config",
            "unused.json",
            "--project-root",
            str(tmp_path),
            "--output-root",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert events == ["policy"]
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload == {
        "error": {"message": "unsafe research mode", "type": "UnsafeExecutionModeError"},
        "status": "failed",
    }


def test_unclassified_research_failure_uses_safe_research_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_arguments: object) -> dict[str, object]:
        raise RuntimeError("sensitive traceback detail")

    monkeypatch.setattr(cli_main, "run_research", fail)

    code = cli_main.main(
        [
            "research",
            "verify",
            "--experiment-id",
            "a" * 64,
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload == {
        "error": {"message": "research command failed", "type": "InternalError"},
        "status": "failed",
    }
    assert "sensitive traceback detail" not in captured.err
    assert "Traceback" not in captured.err
