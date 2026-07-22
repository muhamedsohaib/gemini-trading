from gemini_trading.safety.execution_mode import load_runtime_policy


def test_no_supported_runtime_mode_allows_exchange_submission() -> None:
    for value in ("research", "paper"):
        policy = load_runtime_policy({"GEMINI_TRADING_MODE": value})
        assert policy.exchange_submission_allowed is False
