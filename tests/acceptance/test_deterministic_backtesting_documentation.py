"""Acceptance checks for deterministic backtesting milestone documentation."""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOCUMENTS = (
    _PROJECT_ROOT / "README.md",
    _PROJECT_ROOT / "docs" / "architecture" / "adr" / "0003-deterministic-research-engine.md",
    _PROJECT_ROOT / "docs" / "operations" / "deterministic-backtesting.md",
    _PROJECT_ROOT
    / "docs"
    / "operations"
    / "deterministic-backtesting-step-verification.md",
    _PROJECT_ROOT / "reports" / "verification" / "deterministic-backtesting-final.md",
)


def test_deterministic_backtesting_documents_preserve_commands_and_trust_boundaries() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _DOCUMENTS).lower()

    required_phrases = (
        "gemini-trading research backtest",
        "gemini-trading research replay",
        "gemini-trading research verify",
        "research_only",
        "next-candle",
        "conservative",
        "costs",
        "partial fills",
        "no credentials",
        "exchange order submission",
        "provider-free replay",
        "exact pull-request-head verification",
        "exact merged-main verification",
        "assistant",
        "human authorization",
        "ohlcv",
        "queue",
        "intrabar",
        "profitability",
        "not established",
    )
    for phrase in required_phrases:
        assert phrase in combined
