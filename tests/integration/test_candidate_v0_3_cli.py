"""Integration contracts for Candidate v0.3 qualification CLI surfaces."""

from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

import gemini_trading.cli.candidate_v0_3 as candidate_v0_3
from gemini_trading.cli.main import main


@pytest.mark.parametrize(
    ("command", "required_flags"),
    [
        (
            "strategy-v0-3-qualify",
            (
                "--handoff",
                "--config",
                "--project-root",
                "--output-root",
                "--workflow-run-id",
                "--workflow-run-attempt",
            ),
        ),
        (
            "strategy-v0-3-verify-qualification",
            ("--qualification-id", "--project-root", "--output-root"),
        ),
        (
            "strategy-v0-3-create-prospective-seal",
            ("--qualification-id", "--project-root", "--output-root"),
        ),
    ],
)
def test_v0_3_cli_help_is_narrow_research_only_and_identity_based(
    command: str,
    required_flags: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["research", command, "--help"])

    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert captured.err == ""
    for flag in required_flags:
        assert flag in captured.out
    assert "--symbol" not in captured.out
    assert "--start" not in captured.out
    assert "--end" not in captured.out
    assert "--command" not in captured.out
    assert "--verified-at" not in captured.out
    assert "--api-key" not in captured.out
    assert "--api-secret" not in captured.out


def test_v0_3_locked_config_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "tests" / "fixtures" / "strategy" / "candidate-v0.3-config.json").is_file()


def test_v0_3_qualify_rejects_v0_2_config_before_handoff_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = Path(__file__).resolve().parents[2]
    result = main(
        [
            "research",
            "strategy-v0-3-qualify",
            "--handoff",
            str(tmp_path / "missing-handoff.json"),
            "--config",
            str(root / "tests" / "fixtures" / "strategy" / "candidate-v0.2-config.json"),
            "--workflow-run-id",
            "1",
            "--workflow-run-attempt",
            "1",
            "--project-root",
            str(root),
            "--output-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Candidate v0.3 qualification requires the exact v0.3 config" in captured.err


@dataclass(frozen=True)
class _FakeSeal:
    bridge_start: datetime
    bridge_end: datetime
    final_start: datetime
    final_end: datetime
    qualification_id: str
    seal_id: str


def test_v0_3_seal_payload_is_json_serializable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verified = object()
    seal = _FakeSeal(
        bridge_start=datetime(2026, 8, 1, tzinfo=UTC),
        bridge_end=datetime(2026, 9, 1, tzinfo=UTC),
        final_start=datetime(2026, 9, 1, tzinfo=UTC),
        final_end=datetime(2028, 3, 1, tzinfo=UTC),
        qualification_id="4" * 64,
        seal_id="5" * 64,
    )

    def fake_runtime_policy() -> None:
        return None

    def fake_verified_bundle(_arguments: Namespace) -> object:
        return verified

    class FakeStore:
        def __init__(self, root: Path) -> None:
            assert root == tmp_path.resolve(strict=False)

        def create(self, artifacts: object) -> _FakeSeal:
            assert artifacts is verified
            return seal

    monkeypatch.setattr(candidate_v0_3, "load_runtime_policy", fake_runtime_policy)
    monkeypatch.setattr(candidate_v0_3, "_verified_bundle", fake_verified_bundle)
    monkeypatch.setattr(candidate_v0_3, "V03LocalProspectiveFinalSealStore", FakeStore)

    payload = candidate_v0_3.run_candidate_v0_3(
        Namespace(
            research_command="strategy-v0-3-create-prospective-seal",
            qualification_id="4" * 64,
            project_root=str(tmp_path),
            output_root=str(tmp_path),
        )
    )
    encoded = json.dumps(payload, sort_keys=True)

    assert '"bridge_start": "2026-08-01T00:00:00Z"' in encoded
    assert '"final_start": "2026-09-01T00:00:00Z"' in encoded
    assert '"final_end": "2028-03-01T00:00:00Z"' in encoded
