"""Unit tests for the fixed-scope sealed historical-validation CLI."""

import argparse
from pathlib import Path

import pytest

from gemini_trading.cli import historical_validation
from gemini_trading.cli.historical_validation import (
    resolve_locked_candidate_config,
    run_historical_validation,
)
from gemini_trading.cli.main import build_parser, main
from gemini_trading.cli.market_data import CliUsageError


def test_parser_accepts_only_fixed_historical_validation_shapes() -> None:
    parser = build_parser()

    handoff = parser.parse_args(
        [
            "research",
            "strategy-handoff",
            "--run-id",
            "run-1",
            "--dataset-id",
            "a" * 64,
            "--source-commit",
            "b" * 40,
            "--workflow-run-id",
            "100",
            "--workflow-run-attempt",
            "1",
            "--output-root",
            ".",
        ]
    )
    assert handoff.research_command == "strategy-handoff"

    finalize = parser.parse_args(
        [
            "research",
            "strategy-finalize",
            "--pre-final-id",
            "c" * 64,
            "--receipt-id",
            "d" * 64,
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )
    assert finalize.research_command == "strategy-finalize"


@pytest.mark.parametrize(
    "extra",
    (
        ("--symbol", "ETHUSDT"),
        ("--start", "2019-01-01T00:00:00Z"),
        ("--interval", "1h"),
    ),
)
def test_parser_rejects_scope_override_inputs(extra: tuple[str, str]) -> None:
    with pytest.raises(CliUsageError):
        build_parser().parse_args(
            [
                "research",
                "strategy-handoff",
                "--run-id",
                "run-1",
                "--dataset-id",
                "a" * 64,
                "--source-commit",
                "b" * 40,
                "--workflow-run-id",
                "100",
                "--workflow-run-attempt",
                "1",
                "--output-root",
                ".",
                *extra,
            ]
        )


def test_runtime_policy_is_loaded_before_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def policy() -> None:
        events.append("policy")

    def handoff(_arguments: argparse.Namespace) -> dict[str, object]:
        events.append("handler")
        return {"status": "verified"}

    monkeypatch.setattr(historical_validation, "load_runtime_policy", policy)
    monkeypatch.setattr(historical_validation, "_strategy_handoff", handoff)

    result = run_historical_validation(argparse.Namespace(research_command="strategy-handoff"))

    assert result == {"status": "verified"}
    assert events == ["policy", "handler"]


def test_locked_config_rejects_arbitrary_override(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    arguments = argparse.Namespace(config=str(tmp_path / "other.json"))

    with pytest.raises(CliUsageError, match="locked Candidate configuration"):
        resolve_locked_candidate_config(arguments, project_root)


def test_resume_rejects_receipt_not_bound_to_study(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ReceiptStore:
        def __init__(self, root: Path) -> None:
            assert root == tmp_path

        def load(self, receipt_id: str) -> argparse.Namespace:
            return argparse.Namespace(receipt_id=receipt_id)

    class StudyStore:
        def __init__(self, root: Path) -> None:
            assert root == tmp_path

        def read_artifact(self, study_id: str, name: str) -> bytes:
            assert study_id == "b" * 64
            assert name == "study-manifest.json"
            return b"manifest"

    monkeypatch.setattr(historical_validation, "load_runtime_policy", lambda: None)
    monkeypatch.setattr(historical_validation, "FinalAccessStore", ReceiptStore)
    monkeypatch.setattr(historical_validation, "LocalStrategyStudyStore", StudyStore)
    monkeypatch.setattr(
        historical_validation,
        "parse_study_manifest",
        lambda raw: argparse.Namespace(durable_final_access_receipt_id="c" * 64),
    )

    with pytest.raises(CliUsageError, match="receipt does not match strategy study"):
        run_historical_validation(
            argparse.Namespace(
                research_command="strategy-resume",
                study_id="b" * 64,
                receipt_id="a" * 64,
                project_root=str(tmp_path),
                output_root=str(tmp_path),
            )
        )


def test_malformed_ids_and_attempts_fail_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", "research")
    code = main(
        [
            "research",
            "strategy-authorize-final",
            "--pre-final-id",
            "not-a-hash",
            "--workflow-run-id",
            "10",
            "--workflow-run-attempt",
            "0",
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert "lowercase SHA-256" in captured.err
