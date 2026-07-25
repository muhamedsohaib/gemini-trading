"""Integration coverage for the two-phase sealed Candidate evaluator."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

from candidate_strategy_e2e_worker import synthetic_candidate_candles
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.research.dataset_reader import VerifiedDataset, load_verified_dataset
from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.final_access import FinalAccessStore
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    build_artifact_inventory,
    inventory_root_sha256,
    serialize_dataset_handoff,
)
from gemini_trading.strategy.sealed_evaluator import (
    build_candidate_preparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
from gemini_trading.strategy.verification import StrategyStudyVerificationService
from strategy_fixture_support import base_simulation

_CODE_COMMIT = "a" * 40


def _verified_dataset(root: Path) -> VerifiedDataset:
    candles = synthetic_candidate_candles()
    canonical_bytes = serialize_candles(candles)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time + timedelta(milliseconds=1),
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return load_verified_dataset(LocalImmutableStore(root), manifest.dataset_id)


def _handoff(root: Path, dataset_id: str) -> DatasetHandoffManifest:
    canonical_root = root / "data" / "canonical" / dataset_id
    paths = tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in canonical_root.rglob("*")
            if path.is_file()
        )
    )
    files = build_artifact_inventory(root, paths)
    handoff = DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v1",
        repository="muhamedsohaib/gemini-trading",
        source_commit=_CODE_COMMIT,
        workflow_name="sealed-btcusdt-dataset",
        workflow_run_id=900,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="4h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-07-01T00:00:00Z",
        run_id="diagnostic-run",
        dataset_id=dataset_id,
        candle_count=18_618,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-06-30T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=files,
        inventory_root_sha256=inventory_root_sha256(files),
    )
    path = root / "data" / "historical-validation" / "handoff" / dataset_id / "dataset-handoff.json"
    write_immutable(path, serialize_dataset_handoff(handoff))
    return handoff


def test_prepare_does_not_materialize_final_phase(tmp_path: Path) -> None:
    dataset = _verified_dataset(tmp_path)
    handoff = _handoff(tmp_path, dataset.manifest.dataset_id)

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
    handoff = _handoff(tmp_path, dataset.manifest.dataset_id)
    pre_final = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit=_CODE_COMMIT,
        handoff=handoff,
    )
    preparation = build_candidate_preparation(
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

    verified = StrategyStudyVerificationService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
        research_strategy_reconstructor=reconstruct_study_strategy,
    ).verify(artifacts.study_id)
    assert {
        "dataset_handoff_verified",
        "durable_final_access_verified",
        "exact_resume_policy_verified",
        "pre_final_identity_verified",
        "single_final_access_verified",
    }.issubset(verified.checks)
