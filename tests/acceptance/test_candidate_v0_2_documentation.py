"""Acceptance contract for Candidate v0.2 operations documentation."""

from pathlib import Path

import pytest

_OPERATIONS = Path("docs/operations/candidate-multi-model-strategy-v0-2.md")
_STEPS = Path("docs/operations/candidate-multi-model-strategy-v0-2-step-verification.md")
_README = Path("README.md")


@pytest.mark.parametrize("path", [_OPERATIONS, _STEPS])
def test_candidate_v0_2_operations_docs_exist(path: Path) -> None:
    assert path.is_file()


@pytest.mark.parametrize(
    "required",
    [
        "RESEARCH_ONLY",
        "candidate.multi_model.v0_2",
        "candidate-multi-model-v0.2",
        "tol=1e-7",
        "max_iter=50000",
        "2026-07-01T00:00:00Z",
        "12 complete development folds",
        "QUALIFIED",
        "REJECTED",
        "INCONCLUSIVE",
        "bridge interval",
        "first UTC calendar-month boundary strictly after",
        "18 calendar months",
        "Future profitability",
        "execution authority",
        "candidate-v0.2-dataset-approved:",
        "strategy-v0-2-qualify",
        "strategy-v0-2-qualification-verify",
        "strategy-v0-2-seal-prospective-final",
        "--project-root",
        "policy.json",
        "configuration.json",
        "development-plan.json",
        "data/research",
        "Stage 1 artifact",
    ],
)
def test_v0_2_operations_document_contains_locked_protocol(required: str) -> None:
    text = _OPERATIONS.read_text(encoding="utf-8")
    assert required in text


@pytest.mark.parametrize(
    "required",
    [
        "Sealed BTCUSDT Dataset",
        "Candidate v0.2 Development Qualification",
        "candidate-v0.2-dataset-approved:",
        "QUALIFIED",
        "REJECTED",
        "INCONCLUSIVE",
        "18 calendar months",
        "future profitability",
        "no execution authority",
        "--project-root",
        "policy.json",
        "configuration.json",
        "development-plan.json",
        "data/research",
        "Stage 1 artifact",
    ],
)
def test_v0_2_step_document_contains_closure_evidence(required: str) -> None:
    text = _STEPS.read_text(encoding="utf-8")
    assert required in text


def test_readme_links_candidate_v0_2_operations() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "Candidate Multi-Model Strategy v0.2" in text
    assert "docs/operations/candidate-multi-model-strategy-v0-2.md" in text
    assert "docs/operations/candidate-multi-model-strategy-v0-2-step-verification.md" in text
