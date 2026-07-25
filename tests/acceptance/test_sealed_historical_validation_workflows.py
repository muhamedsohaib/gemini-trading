"""Contract tests for the two manually dispatched sealed workflows."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DATASET = _ROOT / ".github" / "workflows" / "sealed-btcusdt-dataset.yml"
_STUDY = _ROOT / ".github" / "workflows" / "sealed-btcusdt-study.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_dispatch_input_block(text: str) -> str:
    marker = "  workflow_dispatch:\n    inputs:\n"
    start = text.index(marker) + len(marker)
    end = text.index("\npermissions:", start)
    return text[start:end]


def test_dataset_workflow_is_manual_fixed_scope_and_least_privilege() -> None:
    text = _text(_DATASET)

    assert text.startswith("name: Sealed BTCUSDT Dataset\n\non:\n  workflow_dispatch:\n")
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "permissions:\n  contents: read\n" in text
    assert "jobs:\n  dataset:" in text
    assert "fetch-depth: 0" in text
    assert 'python-version: "3.12"' in text
    assert 'version: "0.11.25"' in text
    assert "OUTPUT_ROOT: ${{ runner.temp }}/sealed-output" in text
    assert 'test "${GITHUB_REF_NAME}" = "main"' in text
    assert "--symbol BTCUSDT" in text
    assert "--base-asset BTC" in text
    assert "--quote-asset USDT" in text
    assert "--interval 4h" in text
    assert "--start 2018-01-01T00:00:00Z" in text
    assert "--end 2026-07-01T00:00:00Z" in text
    assert text.index("market-data ingest") < text.index("market-data replay")
    assert text.index("market-data replay") < text.index("market-data verify")
    assert text.index("market-data verify") < text.index("strategy-handoff")
    assert "sealed-btcusdt-dataset-${{ github.sha }}-${{ github.run_id }}" in text
    assert "path: ${{ runner.temp }}/sealed-output/" in text
    assert "retention-days: 90" in text
    assert "secrets." not in text
    assert "workflow_dispatch:\n    inputs:" not in text


def test_study_workflow_has_exact_narrow_inputs_and_cross_run_barriers() -> None:
    text = _text(_STUDY)
    inputs = _workflow_dispatch_input_block(text)

    expected_inputs = {
        "source_commit",
        "dataset_run_id",
        "dataset_artifact_name",
        "dataset_id",
    }
    observed_inputs = {
        line.strip()[:-1]
        for line in inputs.splitlines()
        if line.startswith("      ") and not line.startswith("        ") and line.endswith(":")
    }
    assert observed_inputs == expected_inputs
    assert inputs.count("required: true") == 4
    assert inputs.count("type: string") == 4
    for forbidden in (
        "symbol:",
        "start:",
        "end:",
        "interval:",
        "config:",
        "command:",
        "output_root:",
        "strategy:",
    ):
        assert forbidden not in inputs
    assert "permissions:\n  actions: read\n  contents: read\n  issues: write\n" in text
    assert "concurrency:\n  group: sealed-btcusdt-study\n  cancel-in-progress: false\n" in text
    for job_name in ("validate-dataset", "prepare", "authorize-final", "finalize"):
        assert f"  {job_name}:\n" in text
    assert 'test "${GITHUB_RUN_ATTEMPT}" = "1"' in text
    assert "sealed-dataset-approved:" in text
    assert "exact Issue #22 dataset approval marker is missing" in text
    assert "sealed-final-access:${PRE_FINAL_ID}" in text
    assert "final-test repository seal already exists" in text
    assert "github-actions[bot]" in text
    assert "GITHUB_REPOSITORY_OWNER" in text
    assert "github-issue-final-seal-v1" in text
    assert "issues/22/comments" in text
    assert "receipt.identity.workflow_run_attempt" in text
    assert "receipt.identity.workflow_run_id" in text
    assert "strategy-prepare" in text
    assert "strategy-authorize-final" in text
    assert "strategy-finalize" in text
    assert "strategy-replay" in text
    assert "strategy-verify" in text
    assert "if: always()" in text
    assert "sealed-pre-final-${{ github.run_id }}" in text
    assert "sealed-final-access-${{ github.run_id }}" in text
    assert "sealed-candidate-study-${{ github.run_id }}" in text
    assert "overwrite: false" in text
    assert "retention-days: 90" in text
    assert "secrets.GITHUB_TOKEN" in text
    assert text.count("OUTPUT_ROOT: ${{ runner.temp }}/sealed-output") == 4
    assert "api.binance.com" not in text
    assert "GITHUB_ENV" not in text
    assert (
        "\n        env:\n          COMMENT_ID: ${{ steps.repository-seal.outputs.comment_id }}"
        not in text
    )
