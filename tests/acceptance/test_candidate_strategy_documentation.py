"""Acceptance contract for Candidate v0.1 operations documentation."""

from pathlib import Path

import pytest

_OPERATIONS_DOCUMENT = Path("docs/operations/candidate-multi-model-strategy.md")


@pytest.mark.parametrize(
    "required",
    [
        "RESEARCH_ONLY",
        "BTC/USDT",
        "4h",
        "seven years",
        "18 calendar months",
        "strategy-evaluate",
        "strategy-replay",
        "strategy-verify",
        "rejection is a valid outcome",
        "does not establish durable profitability",
    ],
)
def test_operations_document_contains_safety_and_protocol(required: str) -> None:
    text = _OPERATIONS_DOCUMENT.read_text(encoding="utf-8")
    assert required in text
