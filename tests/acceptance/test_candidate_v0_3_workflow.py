"""Workflow contracts for governed Candidate v0.3 development qualification."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github" / "workflows" / "candidate-v0.3-qualification.yml"


def test_v0_3_qualification_workflow_is_manual_narrow_and_prefinal_only() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "push:" not in text
    assert "pull_request:" not in text
    for name in (
        "source_commit:",
        "dataset_run_id:",
        "dataset_artifact_name:",
        "dataset_id:",
    ):
        assert text.count(name) >= 1
    assert "permissions:\n  contents: read\n  issues: read\n  actions: read" in text
    assert "SOURCE_COMMIT: ${{ inputs.source_commit }}" in text
    assert 'test "${GITHUB_REF_NAME}" = "main"' in text
    assert 'test "${SOURCE_COMMIT}" = "${GITHUB_SHA}"' in text
    assert "candidate-v0.3-dataset-approved:" in text
    assert "issues/69/comments" in text
    assert "GITHUB_REPOSITORY_OWNER" in text
    assert "2026-08-01T00:00:00Z" in text
    assert "strategy-v0-3-qualify" in text
    assert "strategy-v0-3-verify-qualification" in text
    assert '--project-root "${GITHUB_WORKSPACE}"' in text
    assert "strategy-v0-3-create-prospective-seal" not in text
    assert "strategy-finalize" not in text
    assert "strategy-authorize-final" not in text
    assert "candidate-v0.3-bundle" in text
    assert "data/research" in text
    assert "data/historical-validation/v0-3-qualification" in text
    assert "actions/upload-artifact" in text
    assert "retention-days: 90" in text
    assert "candidate-v0.3-qualification-" in text


def test_v0_3_workflow_has_no_exchange_secret_private_or_final_data_surface() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "api_key" not in lowered
    assert "api-secret" not in lowered
    assert "private endpoint" not in lowered
    assert "place-order" not in lowered
    assert "paper" not in lowered
    assert "demo" not in lowered
    assert "live" not in lowered
    assert "prospective-final" not in lowered
