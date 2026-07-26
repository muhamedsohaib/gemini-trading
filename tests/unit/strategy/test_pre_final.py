"""Unit tests for immutable pre-final Candidate evidence."""

import hashlib
from pathlib import Path

import pytest

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import PreFinalArtifactError
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    build_artifact_inventory,
    inventory_root_sha256,
)
from gemini_trading.strategy.pre_final import (
    REQUIRED_PRE_FINAL_NAMES,
    LocalPreFinalStore,
    PreFinalArtifacts,
    build_pre_final_artifacts,
    verify_pre_final_artifacts,
)
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    StudyCaseEvidence,
    StudyPhase,
)
from sealed_dataset_support import write_fixed_supporting_evidence


def _handoff(tmp_path: Path) -> DatasetHandoffManifest:
    evidence = tmp_path / "dataset-evidence.txt"
    evidence.write_bytes(b"dataset\n")
    support = write_fixed_supporting_evidence(tmp_path)
    entries = build_artifact_inventory(
        tmp_path,
        (
            "dataset-evidence.txt",
            support.closure_manifest_path,
            support.segment_manifest_path,
        ),
    )
    return DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v2",
        repository="muhamedsohaib/gemini-trading",
        source_commit="a" * 40,
        workflow_name="sealed-btcusdt-dataset",
        workflow_run_id=123,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="4h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-07-01T00:00:00Z",
        run_id="run-123",
        dataset_id="b" * 64,
        dataset_schema_version=support.dataset_schema_version,
        closure_manifest_path=support.closure_manifest_path,
        closure_manifest_sha256=support.closure_manifest_sha256,
        segment_manifest_path=support.segment_manifest_path,
        segment_manifest_sha256=support.segment_manifest_sha256,
        closure_count=support.closure_count,
        segment_count=support.segment_count,
        closure_ids=support.closure_ids,
        candle_count=18_618,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-06-30T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=entries,
        inventory_root_sha256=inventory_root_sha256(entries),
    )


def _records() -> tuple[StudyCaseEvidence, ...]:
    records: list[StudyCaseEvidence] = []
    for fold_number in (1, 2):
        for index, case_id in enumerate(REQUIRED_DEVELOPMENT_CASE_IDS):
            records.append(
                StudyCaseEvidence(
                    case_id=case_id,
                    phase=StudyPhase.DEVELOPMENT,
                    fold_number=fold_number,
                    terminal_status="completed",
                    experiment_id=f"{fold_number:02x}{index:02x}".ljust(64, "a"),
                    evidence_sha256=f"{index:02x}{fold_number:02x}".ljust(64, "b"),
                )
            )
    return tuple(records)


def _artifacts(tmp_path: Path) -> PreFinalArtifacts:
    split_plan_bytes = canonical_json_bytes(
        {"schema_version": "strategy-split-plan-v1", "final_test_indices": [9, 10]}
    )
    return build_pre_final_artifacts(
        dataset_id="b" * 64,
        handoff=_handoff(tmp_path),
        code_commit="a" * 40,
        policy_bytes=canonical_json_bytes({"policy_version": "candidate-multi-model-v0.1"}),
        configuration_bytes=canonical_json_bytes({"configuration": "locked"}),
        split_plan_bytes=split_plan_bytes,
        split_plan_sha256=hashlib.sha256(split_plan_bytes).hexdigest(),
        segment_boundary_indices=(229,),
        development_records=_records(),
    )


def test_pre_final_contract_is_exact_and_deterministic(tmp_path: Path) -> None:
    first = _artifacts(tmp_path)
    second = _artifacts(tmp_path)

    assert first.names == REQUIRED_PRE_FINAL_NAMES
    assert first == second
    assert len(first.pre_final_id) == 64
    handoff = _handoff(tmp_path)
    manifest = __import__("json").loads(first.artifact_bytes("pre-final-manifest.json"))
    assert manifest["dataset_schema_version"] == "candle-dataset-v2"
    assert manifest["closure_manifest_sha256"] == handoff.closure_manifest_sha256
    assert manifest["segment_manifest_sha256"] == handoff.segment_manifest_sha256
    assert manifest["closure_count"] == 1
    assert manifest["segment_count"] == 2
    assert manifest["closure_ids"] == list(handoff.closure_ids)
    assert manifest["segment_boundary_indices"] == [229]

    assert verify_pre_final_artifacts(
        first,
        expected_handoff=handoff,
        expected_code_commit="a" * 40,
        expected_dataset_id="b" * 64,
    ) == (
        "pre_final_files_verified",
        "pre_final_hashes_verified",
        "pre_final_development_only_verified",
        "pre_final_identity_verified",
    )


def test_pre_final_store_accepts_only_identical_bytes(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    store = LocalPreFinalStore(tmp_path)

    first_paths = store.write(artifacts)
    second_paths = store.write(artifacts)

    assert first_paths == second_paths
    assert store.load(artifacts.pre_final_id) == artifacts


def test_pre_final_verifier_rejects_tampering(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    altered_files = tuple(
        (name, b'{"tampered":true}\n' if name == "configuration.json" else content)
        for name, content in artifacts.files
    )
    tampered = PreFinalArtifacts(artifacts.pre_final_id, altered_files)

    with pytest.raises(PreFinalArtifactError, match="hash mismatch"):
        verify_pre_final_artifacts(tampered)


def test_pre_final_rejects_final_phase_record(tmp_path: Path) -> None:
    split_plan_bytes = canonical_json_bytes({"schema_version": "strategy-split-plan-v1"})
    final_record = StudyCaseEvidence(
        case_id=REQUIRED_DEVELOPMENT_CASE_IDS[0],
        phase=StudyPhase.FINAL,
        fold_number=None,
        terminal_status="completed",
        experiment_id="c" * 64,
        evidence_sha256="d" * 64,
    )

    with pytest.raises(PreFinalArtifactError, match="final-phase"):
        build_pre_final_artifacts(
            dataset_id="b" * 64,
            handoff=_handoff(tmp_path),
            code_commit="a" * 40,
            policy_bytes=canonical_json_bytes({"policy": "locked"}),
            configuration_bytes=canonical_json_bytes({"configuration": "locked"}),
            split_plan_bytes=split_plan_bytes,
            split_plan_sha256=hashlib.sha256(split_plan_bytes).hexdigest(),
            segment_boundary_indices=(229,),
            development_records=(final_record,),
        )


def test_pre_final_rejects_incomplete_fold(tmp_path: Path) -> None:
    split_plan_bytes = canonical_json_bytes({"schema_version": "strategy-split-plan-v1"})

    with pytest.raises(PreFinalArtifactError, match="incomplete development"):
        build_pre_final_artifacts(
            dataset_id="b" * 64,
            handoff=_handoff(tmp_path),
            code_commit="a" * 40,
            policy_bytes=canonical_json_bytes({"policy": "locked"}),
            configuration_bytes=canonical_json_bytes({"configuration": "locked"}),
            split_plan_bytes=split_plan_bytes,
            split_plan_sha256=hashlib.sha256(split_plan_bytes).hexdigest(),
            segment_boundary_indices=(229,),
            development_records=_records()[:1],
        )


def test_pre_final_store_rejects_conflicting_bytes(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    store = LocalPreFinalStore(tmp_path)
    store.write(artifacts)
    configuration_path = (
        tmp_path
        / "data"
        / "historical-validation"
        / "pre-final"
        / artifacts.pre_final_id
        / "configuration.json"
    )
    configuration_path.write_bytes(b'{"conflict":true}\n')

    with pytest.raises(PreFinalArtifactError, match="conflicts"):
        store.write(artifacts)
