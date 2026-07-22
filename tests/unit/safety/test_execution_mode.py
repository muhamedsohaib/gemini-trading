import pytest

from gemini_trading.safety.execution_mode import (
    ExecutionMode,
    UnsafeExecutionModeError,
    load_runtime_policy,
)


def test_default_mode_is_paper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_TRADING_MODE", raising=False)

    policy = load_runtime_policy()

    assert policy.mode is ExecutionMode.PAPER
    assert policy.exchange_submission_allowed is False


@pytest.mark.parametrize("value", ["research", "paper", "RESEARCH", " PAPER "])
def test_safe_modes_are_accepted(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", value)

    policy = load_runtime_policy()

    assert policy.exchange_submission_allowed is False


@pytest.mark.parametrize("value", ["demo", "live", "production", "", "random"])
def test_unsafe_or_unknown_modes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", value)

    with pytest.raises(UnsafeExecutionModeError):
        load_runtime_policy()
