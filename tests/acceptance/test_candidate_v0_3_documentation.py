"""Acceptance contract for Candidate v0.3 operator documentation."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OPERATIONS = _ROOT / "docs" / "operations" / "candidate-multi-model-strategy-v0-3.md"
_VERIFICATION = (
    _ROOT / "docs" / "operations" / "candidate-multi-model-strategy-v0-3-step-verification.md"
)
_REQUIRED = (
    "candidate.multi_model.v0_3",
    "candidate-multi-model-v0.3",
    "2026-08-01T00:00:00Z",
    "q75",
    "0.50",
    "40 eligible calibration scores",
    "q70",
    "q80",
    "no-percentile-selectivity",
    "RESEARCH_ONLY",
    "QUALIFIED",
    "REJECTED",
    "INCONCLUSIVE",
    "no prospective-final performance peeks",
)


def test_v0_3_operations_contract_contains_every_frozen_token() -> None:
    combined = _OPERATIONS.read_text(encoding="utf-8") + _VERIFICATION.read_text(encoding="utf-8")
    for token in _REQUIRED:
        assert token in combined
    assert "candidate-v0.3-dataset-approved:" in combined
    assert "Issue #69" in combined
    assert "fresh Stage 1" in combined
    assert "execution authority" in combined
    assert "capital authority" in combined


def test_readme_links_candidate_v0_3_operations_contract() -> None:
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "candidate-multi-model-strategy-v0-3.md" in readme
