"""Tests for deterministic research errors."""

from gemini_trading.research.errors import (
    AccountingInvariantError,
    DatasetVerificationError,
    ResearchError,
)


def test_research_errors_share_one_safe_base() -> None:
    assert issubclass(AccountingInvariantError, ResearchError)
    assert issubclass(DatasetVerificationError, ResearchError)
