"""Integration coverage for the two-phase sealed Candidate evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from candidate_strategy_e2e_worker import synthetic_candidate_candles
from fixtures.market_data.multi_closure_btcusdt_4h import (
    CANDLES as FIXED_CANDLES,
)
from fixtures.market_data.multi_closure_btcusdt_4h import (
    EXPECTED_BOUNDARIES,
    EXPECTED_CANDLE_COUNT,
    REQUEST,
)
from fixtures.market_data.multi_closure_btcusdt_4h import (
    MANIFEST as CLOSURE_MANIFEST,
)
from fixtures.market_data.multi_closure_btcusdt_4h import (
    MANIFEST_BYTES as CLOSURE_MANIFEST_BYTES,
)
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.exclusions import (
    CandleExclusion,
    CandleExclusionManifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.segments import (
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.domain.candle import Candle
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.strategy import sealed_evaluator
from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.final_access import FinalAccessStore
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    ExcludedProviderRow,
    build_artifact_inventory,
    inventory_root_sha256,
    serialize_dataset_handoff,
)
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.sealed_evaluator import (
    CandidatePreparation,
    complete_candidate_strategy_study,
    final_access_identity,
    prepare_candidate_strategy_study,
)
from gemini_trading.strategy.sealed_evaluator import (
    build_candidate_preparation as build_candidate_preparation_unbounded,
)
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_plans import (
    build_split_plan as build_split_plan_unbounded,
)
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
)
from gemini_trading.strategy.study_predictions import (
    fit_prediction_bundle as fit_prediction_bundle_unbounded,
)
from gemini_trading.strategy.verification import StrategyStudyVerificationService
from strategy_fixture_support import base_simulation

_CODE_COMMIT = "a" * 40
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAX_TRAINING_ROWS = 1_000
_MAX_CALIBRATION_ROWS = 500
_MAX_DECISION_ROWS = 64


@dataclass(frozen=True, slots=True)
class _StoredResearchVerification:
    result_id: str


def _stored_research_verifier(
    root: Path,
    experiment_id: str,
) -> _StoredResearchVerification:
    manifest = cast(
        dict[str, object],
        json.loads(
            LocalResearchStore(root).read_artifact(
                experiment_id,
                "result-manifest.json",
            )
        ),
    )
    result_id = manifest.get("result_id")
    if not isinstance(result_id, str):
        raise AssertionError("stored research result identity is missing")
    return _StoredResearchVerification(result_id=result_id)


def _bounded_prediction_bundle(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    matrix: FeatureMatrix,
    labels: LabelVector,
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> PredictionBundle:
    """Fit real deterministic specialists on bounded integration-only windows."""

    return fit_prediction_bundle_unbounded(
        phase=phase,
        fold_number=fold_number,
        matrix=matrix,
        labels=labels,
        policy=policy,
        training_indices=training_indices[:_MAX_TRAINING_ROWS],
        calibration_indices=calibration_indices[:_MAX_CALIBRATION_ROWS],
        prediction_indices=prediction_indices,
    )


def _bounded_split_plan(
    candles: tuple[Candle, ...],
    eligible_indices: tuple[int, ...],
    policy: CandidatePolicy,
    segment_manifest: CandleSegmentManifest | None = None,
) -> tuple[ChronologicalSplitPlan, bool]:
    """Retain exact boundaries while bounding integration decision work."""

    plan, history_requirement_met = build_split_plan_unbounded(
        candles,
        eligible_indices,
        policy,
        segment_manifest,
    )
    folds = tuple(
        replace(
            fold,
            development_test_indices=fold.development_test_indices[:_MAX_DECISION_ROWS],
        )
        for fold in plan.folds[: policy.minimum_development_folds]
    )
    return (
        replace(
            plan,
            folds=folds,
            final_test_indices=plan.final_test_indices[:_MAX_DECISION_ROWS],
        ),
        history_requirement_met,
    )


@pytest.fixture(autouse=True)
def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    preparation_cache: dict[bool, CandidatePreparation] = {}

    def cached_candidate_preparation(
        *,
        dataset: VerifiedDataset,
        simulation: SimulationConfig,
        initial_cash: Decimal,
        include_final: bool,
    ) -> CandidatePreparation:
        cached = preparation_cache.get(include_final)
        if cached is None:
            cached = build_candidate_preparation_unbounded(
                dataset=dataset,
                simulation=simulation,
                initial_cash=initial_cash,
                include_final=include_final,
            )
            preparation_cache[include_final] = cached
        return cached

    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_split_plan",
        _bounded_split_plan,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_candidate_preparation",
        cached_candidate_preparation,
    )


def _verified_dataset(root: Path) -> VerifiedDataset:
    source_candles = synthetic_candidate_candles()
    first_open = source_candles[0].open
    cycle_factor = source_candles[-1].close / first_open
    price_quantum = Decimal("0.01")
    candles = tuple(
        replace(
            source_candles[index % len(source_candles)],
            instrument=fixed.instrument,
            timeframe=fixed.timeframe,
            open_time=fixed.open_time,
            close_time=fixed.close_time,
            open=(
                source_candles[index % len(source_candles)].open
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            high=(
                source_candles[index % len(source_candles)].high
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            low=(
                source_candles[index % len(source_candles)].low
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            close=(
                source_candles[index % len(source_candles)].close
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            source_provider=fixed.source_provider,
        )
        for index, fixed in enumerate(FIXED_CANDLES)
    )
    if len(candles) != EXPECTED_CANDLE_COUNT:
        raise AssertionError("fixed dataset candle count mismatch")
    canonical_bytes = serialize_candles(candles)
    exclusion_manifest = CandleExclusionManifest(
        schema_version="candle-exclusion-manifest-v1",
        exclusions=tuple(
            CandleExclusion(
                closure_id=closure.closure_id,
                raw_page_sequence=index + 1,
                raw_page_sha256=f"{index + 1:064x}",
                row_index=index,
                provider_row_sha256=closure.partial_candle.provider_row_sha256,
                open_time=closure.partial_candle.open_time,
                actual_close_time=closure.partial_candle.actual_close_time,
                expected_close_time=closure.partial_candle.expected_close_time,
                exclusion_reason=closure.partial_candle.exclusion_reason,
                canonical_index_before_removal=EXPECTED_BOUNDARIES[index] + index,
            )
            for index, closure in enumerate(CLOSURE_MANIFEST.closures)
        ),
    )
    exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
    segment_manifest = validate_and_segment_candle_sequence(
        candles,
        REQUEST,
        CLOSURE_MANIFEST,
    )
    segment_bytes = serialize_candle_segment_manifest(segment_manifest)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v4",
        provider=CLOSURE_MANIFEST.provider,
        instrument=CLOSURE_MANIFEST.instrument,
        timeframe=CLOSURE_MANIFEST.timeframe,
        start_time=REQUEST.start_time,
        end_time=REQUEST.end_time,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest_bytes=CLOSURE_MANIFEST_BYTES,
        exclusion_manifest_bytes=exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
        closure_count=len(CLOSURE_MANIFEST.closures),
        exclusion_count=len(exclusion_manifest.exclusions),
        segment_count=len(segment_manifest.segments),
    )
    store = LocalImmutableStore(root)
    store.write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    store.write_dataset_supporting_manifests(
        manifest.dataset_id,
        CLOSURE_MANIFEST_BYTES,
        segment_bytes,
    )
    store.write_dataset_exclusion_manifest(manifest.dataset_id, exclusion_bytes)
    return VerifiedDataset(
        manifest=manifest,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest=CLOSURE_MANIFEST,
        exclusion_manifest=exclusion_manifest,
        segment_manifest=segment_manifest,
        closure_manifest_bytes=CLOSURE_MANIFEST_BYTES,
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
    exclusion_path = (canonical_root / "candle-exclusions.json").relative_to(root).as_posix()
    segment_path = (canonical_root / "candle-segments.json").relative_to(root).as_posix()
    handoff = DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v4",
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
        dataset_schema_version=dataset.manifest.schema_version,
        closure_manifest_path=closure_path,
        closure_manifest_sha256=dataset.manifest.closure_manifest_sha256 or "",
        exclusion_manifest_path=exclusion_path,
        exclusion_manifest_sha256=dataset.manifest.exclusion_manifest_sha256 or "",
        segment_manifest_path=segment_path,
        segment_manifest_sha256=dataset.manifest.segment_manifest_sha256 or "",
        closure_count=dataset.manifest.closure_count,
        exclusion_count=dataset.manifest.exclusion_count,
        segment_count=dataset.manifest.segment_count,
        closure_ids=tuple(item.closure_id for item in dataset.closure_manifest.closures)
        if dataset.closure_manifest is not None
        else (),
        excluded_provider_rows=tuple(
            ExcludedProviderRow(
                closure_id=item.closure_id,
                provider_row_sha256=item.provider_row_sha256,
            )
            for item in dataset.exclusion_manifest.exclusions
        )
        if dataset.exclusion_manifest is not None
        else (),
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
    preparation = sealed_evaluator.build_candidate_preparation(
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
    assert manifest["dataset_schema_version"] == "candle-dataset-v4"
    assert manifest["excluded_provider_rows"] == [
        {
            "closure_id": item.closure_id,
            "provider_row_sha256": item.provider_row_sha256,
        }
        for item in handoff.excluded_provider_rows
    ]
    assert "excluded_provider_row_sha256" not in manifest

    verified = StrategyStudyVerificationService(
        root=tmp_path,
        current_commit_resolver=lambda: _CODE_COMMIT,
        research_verifier=lambda experiment_id: _stored_research_verifier(
            tmp_path,
            experiment_id,
        ),
        research_strategy_reconstructor=reconstruct_study_strategy,
    ).verify(artifacts.study_id)
    assert {
        "dataset_handoff_verified",
        "durable_final_access_verified",
        "exact_resume_policy_verified",
        "pre_final_identity_verified",
        "single_final_access_verified",
    }.issubset(verified.checks)
