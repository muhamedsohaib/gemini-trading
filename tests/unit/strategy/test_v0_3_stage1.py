"""Candidate v0.3 Stage 1 dataset isolation contracts."""

from __future__ import annotations

import importlib
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from gemini_trading.cli.main import build_parser
from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest


def _stage1_module():
    spec = importlib.util.find_spec("gemini_trading.strategy.v0_3_stage1")
    assert spec is not None, "Candidate v0.3 requires a version-isolated Stage 1 module"
    return importlib.import_module("gemini_trading.strategy.v0_3_stage1")


def test_v0_3_stage1_window_extends_to_august_cutoff_without_changing_closures() -> None:
    stage1 = _stage1_module()
    project_root = Path(__file__).resolve().parents[3]
    base, base_raw = load_fixed_btcusdt_closure_manifest(project_root)
    manifest, raw = stage1.build_v0_3_closure_manifest(project_root)

    assert stage1.V03_STAGE1_START == datetime(2018, 1, 1, tzinfo=UTC)
    assert stage1.V03_STAGE1_END_EXCLUSIVE == datetime(2026, 8, 1, tzinfo=UTC)
    assert stage1.V03_EXPECTED_CANDLE_COUNT == 18_768
    assert stage1.V03_EXPECTED_LAST_OPEN_TIME == "2026-07-31T20:00:00Z"
    assert manifest.start_time == base.start_time
    assert manifest.end_time == stage1.V03_STAGE1_END_EXCLUSIVE
    assert manifest.closures == base.closures
    assert raw != base_raw


def test_v0_3_stage1_commands_are_registered_without_changing_legacy_commands() -> None:
    parser = build_parser()
    ingest = parser.parse_args(
        [
            "research",
            "dataset-v0-3-ingest",
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )
    assert ingest.research_command == "dataset-v0-3-ingest"

    handoff = parser.parse_args(
        [
            "research",
            "strategy-v0-3-handoff",
            "--run-id",
            "run-1",
            "--dataset-id",
            "a" * 64,
            "--source-commit",
            "b" * 40,
            "--workflow-run-id",
            "100",
            "--workflow-run-attempt",
            "1",
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )
    assert handoff.research_command == "strategy-v0-3-handoff"

    legacy = parser.parse_args(
        [
            "research",
            "dataset-ingest",
            "--project-root",
            ".",
            "--output-root",
            ".",
        ]
    )
    assert legacy.research_command == "dataset-ingest"


def test_v0_3_stage1_workflow_is_version_isolated_and_uses_exact_cutoff() -> None:
    project_root = Path(__file__).resolve().parents[3]
    workflow = project_root / ".github" / "workflows" / "candidate-v0.3-stage1.yml"
    assert workflow.exists(), "Candidate v0.3 requires a dedicated Stage 1 workflow"
    text = workflow.read_text()

    assert "dataset-v0-3-ingest" in text
    assert "strategy-v0-3-handoff" in text
    assert "2026-08-01T00:00:00Z" in text
    assert "assert_fixed_sealed_dataset_identity" not in text
    assert "candidate-v0.3-stage1-${{ github.sha }}-${{ github.run_id }}" in text
