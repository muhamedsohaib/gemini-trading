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
