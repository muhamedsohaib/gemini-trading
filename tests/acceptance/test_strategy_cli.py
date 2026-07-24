"""Acceptance tests for provider-free Candidate strategy-study CLI commands."""

import json
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.cli import strategy
from gemini_trading.cli.main import main
from gemini_trading.strategy.artifacts import LocalStrategyStudyStore, build_study_artifacts
from gemini_trading.strategy.evaluation import MANDATORY_GATE_IDS, PromotionClassification
from gemini_trading.strategy.verification import StrategyStudyVerificationResult
from strategy_study_artifact_support import complete_payloads, complete_study_evidence

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _PROJECT_ROOT / "tests" / "fixtures" / "strategy" / "candidate-v0.1-config.json"
_CODE_COMMIT = "a" * 40


def _decoded_output(text: str) -> dict[str, object]:
    assert text.endswith("\n")
    assert text.count("\n") == 1
    value: object = json.loads(text)
    assert isinstance(value, dict)
    assert text == (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return cast(dict[str, object], value)


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    code = main(argv)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    return _decoded_output(captured.out)


def _stored_study(tmp_path: Path) -> tuple[str, str]:
    payloads = complete_payloads()
    payloads["promotion-gates.json"] = {
        "classification": PromotionClassification.INCONCLUSIVE.value,
        "gates": [{"gate_id": gate_id} for gate_id in MANDATORY_GATE_IDS],
    }
    artifacts = build_study_artifacts(
        complete_study_evidence(),
        classification=PromotionClassification.INCONCLUSIVE,
        payloads=payloads,
        code_commit=_CODE_COMMIT,
    )
    LocalStrategyStudyStore(tmp_path).write(artifacts)
    return artifacts.study_id, artifacts.study_result_id


def test_strategy_replay_cli_reads_only_immutable_local_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    study_id, study_result_id = _stored_study(tmp_path)
    monkeypatch.setattr(strategy, "load_runtime_policy", lambda: object())
    monkeypatch.setattr(strategy, "resolve_clean_git_commit", lambda _root: _CODE_COMMIT)

    payload = _run(
        [
            "research",
            "strategy-replay",
            "--study-id",
            study_id,
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )

    assert payload == {
        "classification": "INCONCLUSIVE",
        "promotable": False,
        "status": "completed",
        "study_id": study_id,
        "study_result_id": study_result_id,
    }
    assert str(tmp_path.resolve()) not in json.dumps(payload)


def test_strategy_verify_cli_returns_safe_sorted_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    study_id, study_result_id = _stored_study(tmp_path)
    expected = StrategyStudyVerificationResult(
        study_id=study_id,
        study_result_id=study_result_id,
        classification=PromotionClassification.INCONCLUSIVE,
        promotable=False,
        checks=("artifact_hashes_verified", "replay_equivalent"),
    )

    class _Verifier:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify(self, supplied_study_id: str) -> StrategyStudyVerificationResult:
            assert supplied_study_id == study_id
            return expected

    monkeypatch.setattr(strategy, "load_runtime_policy", lambda: object())
    monkeypatch.setattr(strategy, "StrategyStudyVerificationService", _Verifier)

    payload = _run(
        [
            "research",
            "strategy-verify",
            "--study-id",
            study_id,
            "--project-root",
            str(_PROJECT_ROOT),
            "--output-root",
            str(tmp_path),
        ],
        capsys,
    )

    assert payload == {
        "checks": ["artifact_hashes_verified", "replay_equivalent"],
        "classification": "INCONCLUSIVE",
        "promotable": False,
        "status": "verified",
        "study_id": study_id,
        "study_result_id": study_result_id,
    }
