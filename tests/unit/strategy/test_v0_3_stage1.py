"""Candidate v0.3 Stage 1 dataset isolation contracts."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.cli.main import build_parser
from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest
from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import ArtifactInventoryEntry, inventory_root_sha256
from gemini_trading.strategy.sealed_dataset_identity import (
    EXPECTED_BOUNDARIES,
    EXPECTED_CLOSURE_IDS,
    EXPECTED_COUNTS,
    EXPECTED_EXCLUDED_PROVIDER_ROWS,
)


def _stage1_module():
    spec = importlib.util.find_spec("gemini_trading.strategy.v0_3_stage1")
    assert spec is not None, "Candidate v0.3 requires a version-isolated Stage 1 module"
    return importlib.import_module("gemini_trading.strategy.v0_3_stage1")


def test_v0_3_stage1_window_extends_to_august_cutoff_without_changing_closures() -> None:
    stage1 = _stage1_module()
    project_root = Path(__file__).resolve().parents[3]
    base, base_raw = load_fixed_btcusdt_closure_manifest(project_root)
    manifest, raw = stage1.build_v0_3_closure_manifest(project_root)

    assert datetime(2018, 1, 1, tzinfo=UTC) == stage1.V03_STAGE1_START
    assert datetime(2026, 8, 1, tzinfo=UTC) == stage1.V03_STAGE1_END_EXCLUSIVE
    assert stage1.V03_EXPECTED_CANDLE_COUNT == 18_768
    assert stage1.V03_EXPECTED_LAST_OPEN_TIME == "2026-07-31T20:00:00Z"
    assert manifest.start_time == base.start_time
    assert manifest.end_time == stage1.V03_STAGE1_END_EXCLUSIVE
    assert manifest.closures == base.closures
    assert raw != base_raw


def test_v0_3_stage1_handoff_is_canonical_and_rejects_legacy_cutoff() -> None:
    stage1 = _stage1_module()
    files = (ArtifactInventoryEntry(path="data/example", size_bytes=1, sha256="a" * 64),)
    manifest = stage1.V03DatasetHandoffManifest(
        schema_version="candidate-v0.3-dataset-handoff-v1",
        repository="muhamedsohaib/gemini-trading",
        source_commit="b" * 40,
        workflow_name="candidate-v0.3-stage1",
        workflow_run_id=100,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="4h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-08-01T00:00:00Z",
        run_id="run-1",
        dataset_id="c" * 64,
        dataset_schema_version="candle-dataset-v4",
        closure_manifest_path="data/closure.json",
        closure_manifest_sha256="d" * 64,
        exclusion_manifest_path="data/exclusion.json",
        exclusion_manifest_sha256="e" * 64,
        segment_manifest_path="data/segments.json",
        segment_manifest_sha256="f" * 64,
        closure_count=EXPECTED_COUNTS[0],
        exclusion_count=EXPECTED_COUNTS[1],
        segment_count=EXPECTED_COUNTS[2],
        closure_ids=EXPECTED_CLOSURE_IDS,
        excluded_provider_rows=EXPECTED_EXCLUDED_PROVIDER_ROWS,
        segment_boundary_indices=EXPECTED_BOUNDARIES,
        candle_count=18_768,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-07-31T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=files,
        inventory_root_sha256=inventory_root_sha256(files),
    )
    raw = stage1.serialize_v0_3_dataset_handoff(manifest)
    assert stage1.load_v0_3_dataset_handoff(raw) == manifest

    with pytest.raises(DatasetHandoffError, match="historical window"):
        replace(manifest, end_exclusive="2026-07-01T00:00:00Z")


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
