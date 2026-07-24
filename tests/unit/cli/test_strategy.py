"""Unit tests for the safe Candidate strategy-study CLI surface."""

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

import gemini_trading.cli.main as cli_main
from gemini_trading.cli import strategy
from gemini_trading.safety.execution_mode import UnsafeExecutionModeError
from gemini_trading.strategy.artifacts import StrategyStudyArtifacts
from gemini_trading.strategy.evaluation import PromotionClassification

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG = _PROJECT_ROOT / "tests" / "fixtures" / "strategy" / "candidate-v0.1-config.json"


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    value: object = json.loads(text)
    assert isinstance(value, dict)
    assert text == (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return cast(dict[str, object], value)


def _artifacts() -> StrategyStudyArtifacts:
    files = tuple((name, b"{}\n") for name in strategy.REQUIRED_STUDY_ARTIFACT_NAMES)
    return StrategyStudyArtifacts(
        study_id="a" * 64,
        study_result_id="b" * 64,
        classification=PromotionClassification.INCONCLUSIVE,
        files=files,
    )


def test_strategy_evaluate_help_lists_exact_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli_main.main(["research", "strategy-evaluate", "--help"])

    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert captured.err == ""
    for flag in ("--dataset-id", "--config", "--project-root", "--output-root"):
        assert flag in captured.out


def test_locked_candidate_config_loads_exact_policy() -> None:
    loaded = strategy.load_candidate_strategy_config(_CONFIG)

    assert loaded.schema_version == "candidate-strategy-cli-v1"
    assert loaded.initial_cash == Decimal("10000")
    assert loaded.strategy_id == "candidate.multi_model.v0_1"
    assert loaded.policy_version == "candidate-multi-model-v0.1"
    assert loaded.simulation.promotable is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: {**payload, "extra": True}, "fields"),
        (
            lambda payload: {
                **payload,
                "strategy": {**cast(dict[str, object], payload["strategy"]), "id": "other"},
            },
            "strategy identity",
        ),
        (
            lambda payload: {
                **payload,
                "strategy": {
                    **cast(dict[str, object], payload["strategy"]),
                    "policy_version": "other",
                },
            },
            "policy version",
        ),
        (
            lambda payload: {
                **payload,
                "simulation": {
                    **cast(dict[str, object], payload["simulation"]),
                    "taker_fee_rate": "0",
                },
            },
            "costs",
        ),
        (
            lambda payload: {
                **payload,
                "simulation": {
                    **cast(dict[str, object], payload["simulation"]),
                    "timing_policy": "same_close",
                },
            },
            "next-candle",
        ),
        (
            lambda payload: {
                **payload,
                "simulation": {
                    **cast(dict[str, object], payload["simulation"]),
                    "limit_fill_policy": "optimistic",
                },
            },
            "conservative",
        ),
    ],
)
def test_locked_candidate_config_rejects_unsafe_changes(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], dict[str, object]],
    message: str,
) -> None:
    payload = cast(dict[str, object], json.loads(_CONFIG.read_text()))
    path = tmp_path / "config.json"
    path.write_text(json.dumps(mutation(payload)))

    with pytest.raises(Exception, match=message):
        strategy.load_candidate_strategy_config(path)


def test_strategy_runtime_policy_precedes_config_and_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[str] = []

    def reject_mode() -> object:
        events.append("policy")
        raise UnsafeExecutionModeError("unsafe strategy mode")

    def fail_config(_path: Path) -> object:
        events.append("config")
        raise AssertionError("configuration must not be read before runtime policy")

    monkeypatch.setattr(strategy, "load_runtime_policy", reject_mode)
    monkeypatch.setattr(strategy, "load_candidate_strategy_config", fail_config)

    code = cli_main.main(
        [
            "research",
            "strategy-evaluate",
            "--dataset-id",
            "a" * 64,
            "--config",
            str(_CONFIG),
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
        "error": {"message": "unsafe strategy mode", "type": "UnsafeExecutionModeError"},
        "status": "failed",
    }


def test_strategy_evaluate_emits_exact_safe_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(strategy, "load_runtime_policy", lambda: object())
    monkeypatch.setattr(strategy, "resolve_clean_git_commit", lambda _root: "d" * 40)
    monkeypatch.setattr(strategy, "evaluate_candidate_strategy", lambda **_kwargs: _artifacts())
    monkeypatch.setattr(strategy.LocalStrategyStudyStore, "write", lambda _self, _value: ())

    code = cli_main.main(
        [
            "research",
            "strategy-evaluate",
            "--dataset-id",
            "c" * 64,
            "--config",
            str(_CONFIG),
            "--project-root",
            str(tmp_path),
            "--output-root",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert _decoded_output(captured.out) == {
        "classification": "INCONCLUSIVE",
        "promotable": False,
        "status": "completed",
        "study_id": "a" * 64,
        "study_result_id": "b" * 64,
    }
