"""Acceptance gate for the sealed historical-validation operator guide."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "operations" / "sealed-btcusdt-historical-validation.md"
_README = _ROOT / "README.md"


def test_operator_guide_locks_scope_sequence_and_failure_policy() -> None:
    text = _GUIDE.read_text(encoding="utf-8")

    required = (
        "[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)",
        "Sealed BTCUSDT Dataset",
        "Sealed BTCUSDT Candidate Study",
        "source_commit",
        "dataset_run_id",
        "dataset_artifact_name",
        "dataset_id",
        "Issue #22",
        "explicit Issue #22 approval comment",
        "access receipt is written before final-test rows",
        "fresh final evaluation is prohibited",
        "Exact resume",
        "90 days",
        "Download the artifact immediately",
        "independently recompute",
        "PASS",
        "REJECTED",
        "INCONCLUSIVE",
        "RESEARCH_ONLY",
        "No classification authorizes execution or capital",
    )
    for phrase in required:
        assert phrase in text


def test_documentation_states_no_real_result_exists_before_operation() -> None:
    guide = _GUIDE.read_text(encoding="utf-8")
    readme = _README.read_text(encoding="utf-8")

    statement = "no real historical Candidate result"
    assert statement in guide
    assert statement in readme
    assert "does not prove future profitability" in guide
    assert "no credentials" in guide
    assert "no real-capital authorization" in guide
