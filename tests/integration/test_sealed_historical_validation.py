"""Integration coverage for the two-phase sealed Candidate evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from candidate_strategy_e2e_worker import _synthetic_candles
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.research.dataset_reader import VerifiedDataset, load_verified_dataset
from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES
from gemini_trading.strategy.final_access import FinalAccessStore
from gemini_trading.strategy.sealed_evaluator import (
    _build_preparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
from strategy_fixture_support import base_simulation

_CODE_COMMIT = "a" * 40


@dataclass(frozen=True, slots=True)
class _DiagnosticHandoff:
    dataset_id: str
    inventory_root_sha256: str = "1" * 64
    source_commit: str = _CODE_COMMIT
    workflow_run_id: int = 900
    workflow_run_attempt: int = 1
    run_id: str = "diagnostic-run"


def _verified_dataset(root: Path) -> VerifiedDataset:
    candles = _synthetic_candles()
    canonical_bytes = serialize_candles(candles)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time.replace(microsecond=0),
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return load_verified_dataset(LocalImmutableStore(root), manifest.dataset_id)


def test_prepare_does_not_materialize_final_phase(tmp_path: Path) -> None:
    dataset = _verified_dataset(tmp_path)
    handoff = _DiagnosticHandoff(dataset.manifest.dataset_id)

    pre_final = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=base_simulation(),
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit=_CODE_COMMIT,
        handoff=handoff,
    )

    rows = tuple(
        cast(dict[str, object], json.loads(line))
        for line in pre_final.artifact_bytes("development-experiments.jsonl").splitlines()
    )
    assert {row["phase"] for row in rows} == {"development"}
    assert not (tmp_path / "data" / "strategy-studies").exists()


def test_complete_requires_matching_durable_receipt(tmp_path: Path) -> None:
    dataset = _verified_dataset(tmp_path)
    simulation = base_simulation()
    handoff = _DiagnosticHandoff(dataset.manifest.dataset_id)
    pre_final = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit=_CODE_COMMIT,
        handoff=handoff,
    )
    preparation = _build_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        include_final=False,
    )
    identity = final_access_identity(
        pre_final=pre_final,
        handoff=handoff,
        preparation=preparation,
        code_commit=_CODE_COMMIT,
        workflow_run_id=handoff.workflow_run_id,
        workflow_run_attempt=handoff.workflow_run_attempt,
    )
    receipt = FinalAccessStore(tmp_path).authorize(identity)

    artifacts = complete_candidate_strategy_study(
        pre_final=pre_final,
        receipt=receipt,
        handoff=handoff,
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit=_CODE_COMMIT,
    )

    assert artifacts.names == REQUIRED_STUDY_ARTIFACT_NAMES
    assert artifacts.classification.value in {"PASS", "REJECTED", "INCONCLUSIVE"}
    manifest = cast(
        dict[str, object],
        json.loads(artifacts.artifact_bytes("study-manifest.json")),
    )
    assert manifest["pre_final_id"] == pre_final.pre_final_id
    assert manifest["dataset_handoff_inventory_root"] == handoff.inventory_root_sha256
    assert manifest["durable_final_access_receipt_id"] == receipt.receipt_id
