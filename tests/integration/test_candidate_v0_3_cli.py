"""Integration contracts for Candidate v0.3 qualification CLI surfaces."""

from pathlib import Path

import pytest

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
