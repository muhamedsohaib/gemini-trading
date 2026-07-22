import pytest

from gemini_trading.safety.repository_policy import (
    RepositoryPolicyViolation,
    validate_tracked_paths,
)


def test_safe_paths_are_allowed() -> None:
    validate_tracked_paths([".env.example", "src/gemini_trading/__init__.py"])


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "service.key",
        "certificate.pem",
        "__pycache__/module.pyc",
        "q_table.json",
    ],
)
def test_prohibited_tracked_paths_are_rejected(path: str) -> None:
    with pytest.raises(RepositoryPolicyViolation):
        validate_tracked_paths([path])


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/binance_spot/run/page-000001.json",
        "data/canonical/dataset/candles.jsonl",
    ],
)
def test_generated_market_data_must_not_be_tracked(path: str) -> None:
    with pytest.raises(
        RepositoryPolicyViolation,
        match="generated market data must not be tracked",
    ):
        validate_tracked_paths([path])
