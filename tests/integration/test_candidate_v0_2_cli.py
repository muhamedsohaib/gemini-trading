"""RED integration tests for Candidate v0.2 qualification CLI surfaces."""

from pathlib import Path

import pytest

from gemini_trading.cli.main import main


@pytest.mark.parametrize(
    ("command", "required_flags"),
    [
        (
            "strategy-v0-2-qualify",
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
            "strategy-v0-2-qualification-verify",
            ("--qualification-id", "--output-root"),
        ),
        (
            "strategy-v0-2-seal-prospective-final",
            ("--qualification-id", "--verified-at", "--output-root"),
        ),
    ],
)
def test_v0_2_cli_help_is_narrow_and_identity_based(
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


def test_v0_2_locked_config_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "tests" / "fixtures" / "strategy" / "candidate-v0.2-config.json").is_file()
