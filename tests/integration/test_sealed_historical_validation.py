"""Integration coverage for the two-phase sealed Candidate evaluator."""

from __future__ import annotations

import json
from dataclasses import replace
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
from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
    serialize_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import (
    CandleExclusion,
    CandleExclusionManifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.segments import (
    CandleSegment,
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.dataset_reader import VerifiedDataset
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
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLOSURE_ID = "binance-spot-system-upgrade-2018-02-08"


def _verified_dataset(root: Path) -> VerifiedDataset:
    source_candles = synthetic_candidate_candles()
    closure_duration = timedelta(hours=28)
    candles = (
        source_candles[0],
        *(
            replace(
                candle,
                open_time=candle.open_time + closure_duration,
                close_time=candle.close_time + closure_duration,
            )
            for candle in source_candles[1:]
        ),
    )
    canonical_bytes = serialize_candles(candles)
    boundary = 1
    synthetic_gap_start = candles[0].open_time + candles[0].timeframe.duration
    synthetic_expected_close = (
        synthetic_gap_start + candles[0].timeframe.duration - timedelta(milliseconds=1)
    )
    closure_manifest = ExchangeClosureManifest(
        schema_version="exchange-closure-manifest-v2",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time + timedelta(milliseconds=1),
        closures=(
            ExchangeClosure(
                closure_id=_CLOSURE_ID,
                canonical_gap_start=synthetic_gap_start,
                resumed_open=candles[boundary].open_time,
                unavailable_candle_count=7,
                fully_missing_start=synthetic_gap_start + candles[0].timeframe.duration,
                fully_missing_candle_count=6,
                reason_code="exchange_system_upgrade",
                governance_reference="synthetic-sealed-test",
                partial_candle=PartialCandleDeclaration(
                    open_time=synthetic_gap_start,
                    actual_close_time=synthetic_gap_start + timedelta(minutes=28),
                    expected_close_time=synthetic_expected_close,
                    provider_row_sha256="0" * 64,
                    exclusion_reason="synthetic_exchange_closed_mid_candle",
                ),
            ),
        ),
    )
    closure_bytes = serialize_exchange_closure_manifest(closure_manifest)
    exclusion_manifest = CandleExclusionManifest(
        schema_version="candle-exclusion-manifest-v1",
        exclusions=(
            CandleExclusion(
                closure_id=_CLOSURE_ID,
                raw_page_sequence=1,
                raw_page_sha256="1" * 64,
                row_index=boundary,
                provider_row_sha256="6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775",
                open_time=synthetic_gap_start,
                actual_close_time=synthetic_gap_start + timedelta(minutes=28),
                expected_close_time=synthetic_expected_close,
                exclusion_reason="synthetic_exchange_closed_mid_candle",
                canonical_index_before_removal=boundary,
            ),
        ),
    )
    exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
    segment_manifest = CandleSegmentManifest(
        schema_version="candle-segment-manifest-v1",
        segments=(
            CandleSegment(
                segment_number=1,
                start_index=0,
                end_exclusive=boundary,
                first_open_time=candles[0].open_time,
                last_open_time=candles[boundary - 1].open_time,
                candle_count=boundary,
                preceding_closure_id=None,
            ),
            CandleSegment(
                segment_number=2,
                start_index=boundary,
                end_exclusive=len(candles),
                first_open_time=candles[boundary].open_time,
                last_open_time=candles[-1].open_time,
                candle_count=len(candles) - boundary,
                preceding_closure_id=_CLOSURE_ID,
            ),
        ),
    )
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v3",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time + timedelta(milliseconds=1),
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest_bytes=closure_bytes,
        exclusion_manifest_bytes=exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
        closure_count=1,
        exclusion_count=1,
        segment_count=2,
    )
    store = LocalImmutableStore(root)
    store.write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    store.write_dataset_supporting_manifests(
        manifest.dataset_id,
        closure_bytes,
        segment_bytes,
    )
    store.write_dataset_exclusion_manifest(manifest.dataset_id, exclusion_bytes)
    return VerifiedDataset(
        manifest=manifest,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest=closure_manifest,
        exclusion_manifest=exclusion_manifest,
        segment_manifest=segment_manifest,
        closure_manifest_bytes=closure_bytes,
        exclusion_manifest_bytes=exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
    )


def _handoff(root: Path, dataset: VerifiedDataset) -> DatasetHandoffManifest:
    dataset_id = dataset.manifest.dataset_id
    canonical_root = root / "data" / "canonical" / dataset_id
    paths = tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in canonical_root.rglob("*")
            if path.is_file()
        )
    )
    files = build_artifact_inventory(root, paths)
    closure_path = (canonical_root / "exchange-closures.json").relative_to(root).as_posix()
    segment_path = (canonical_root / "candle-segments.json").relative_to(root).as_posix()
    handoff = DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v3",
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
        dataset_schema_version="candle-dataset-v3",
        closure_manifest_path=closure_path,
        closure_manifest_sha256=dataset.manifest.closure_manifest_sha256 or "",
        exclusion_manifest_path=(canonical_root / "candle-exclusions.json")
        .relative_to(root)
        .as_posix(),
        exclusion_manifest_sha256=dataset.manifest.exclusion_manifest_sha256 or "",
        segment_manifest_path=segment_path,
        segment_manifest_sha256=dataset.manifest.segment_manifest_sha256 or "",
        closure_count=dataset.manifest.closure_count,
        exclusion_count=dataset.manifest.exclusion_count,
        segment_count=dataset.manifest.segment_count,
        closure_ids=tuple(item.closure_id for item in dataset.closure_manifest.closures)
        if dataset.closure_manifest is not None
        else (),
        excluded_provider_row_sha256=(
            dataset.exclusion_manifest.exclusions[0].provider_row_sha256
            if dataset.exclusion_manifest is not None
            else ""
        ),
        segment_boundary_indices=(
            dataset.segment_manifest.boundary_indices
            if dataset.segment_manifest is not None
            else ()
        ),
        candle_count=len(dataset.candles),
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
    handoff = _handoff(tmp_path, dataset)
    simulation = base_simulation()
    full_count = len(dataset.candles)

    preparation = build_candidate_preparation(
        dataset=dataset,
        simulation=simulation,
        initial_cash=Decimal("10000"),
        include_final=False,
    )
    boundary = preparation.split_plan.final_test_boundary_index
    assert max(row.candle_index for row in preparation.matrix.rows) < boundary
    assert max(item.decision_candle_index for item in preparation.labels.observations) < boundary

    pre_final = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=simulation,
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

    research_store = LocalResearchStore(tmp_path)
    for row in rows:
        experiment_id = cast(str, row["experiment_id"])
        account_series = research_store.read_artifact(experiment_id, "account-series.jsonl")
        assert len(account_series.splitlines()) < full_count


def test_complete_requires_matching_durable_receipt(tmp_path: Path) -> None:
    dataset = _verified_dataset(tmp_path)
    simulation = base_simulation()
    handoff = _handoff(tmp_path, dataset)
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
