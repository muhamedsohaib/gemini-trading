"""Deterministic end-to-end acceptance for Candidate v0.1 research evidence."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.cli import strategy
from gemini_trading.cli.main import main

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _PROJECT_ROOT / "tests" / "fixtures" / "strategy" / "candidate-v0.1-config.json"
_WORKER = _PROJECT_ROOT / "tests" / "candidate_strategy_e2e_worker.py"


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    loaded: object = json.loads(text)
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def test_candidate_strategy_end_to_end_is_deterministic_and_non_promotable(
    tmp_path: Path,
) -> None:
    blocked_prefixes = ("COV_", "COVERAGE", "PYTEST", "DD_")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith(blocked_prefixes)
    }
    environment["GEMINI_TRADING_MODE"] = "research"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(_PROJECT_ROOT / "src"), str(_PROJECT_ROOT / "tests"))
    )
    environment["DD_TRACE_ENABLED"] = "false"

    result = subprocess.run(
        [sys.executable, str(_WORKER), str(tmp_path), str(_PROJECT_ROOT), str(_CONFIG)],
        cwd=_PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = _decoded_output(result.stdout)
    assert payload["classification"] == "INCONCLUSIVE"
    assert payload["promotable"] is False
    assert payload["tamper_rejected"] is True
    assert len(cast(str, payload["study_id"])) == 64
    assert len(cast(str, payload["study_result_id"])) == 64
    hashes = cast(list[object], payload["artifact_hashes"])
    assert len(hashes) == 22
    checks = cast(list[str], payload["checks"])
    assert checks == sorted(checks)


def test_candidate_strategy_live_mode_fails_before_dataset_or_model_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []

    def dataset_forbidden(*_args: object, **_kwargs: object) -> None:
        events.append("dataset")
        raise AssertionError("dataset work must not start in live mode")

    monkeypatch.setenv("GEMINI_TRADING_MODE", "live")
    monkeypatch.setattr(strategy, "load_verified_dataset", dataset_forbidden)

    code = main(
        [
            "research",
            "strategy-evaluate",
            "--dataset-id",
            "a" * 64,
            "--config",
            str(_CONFIG),
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert events == []
    assert captured.out == ""
    payload = _decoded_output(captured.err)
    assert payload["status"] == "failed"
    assert cast(dict[str, object], payload["error"])["type"] == "UnsafeExecutionModeError"
