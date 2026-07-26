"""Safe CLI handlers for sealed BTCUSDT historical validation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

from gemini_trading.cli.market_data import CliUsageError
from gemini_trading.cli.strategy import load_candidate_strategy_config
from gemini_trading.data.exchange_closures import load_fixed_btcusdt_closure_manifest
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionResult, IngestionService
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.replay import resolve_clean_git_commit
from gemini_trading.safety.execution_mode import load_runtime_policy
from gemini_trading.strategy.artifacts import LocalStrategyStudyStore
from gemini_trading.strategy.final_access import FinalAccessIdentity, FinalAccessStore
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    build_artifact_inventory,
    inventory_root_sha256,
    load_dataset_handoff,
    serialize_dataset_handoff,
    verify_dataset_handoff,
)
from gemini_trading.strategy.pre_final import (
    LocalPreFinalStore,
    PreFinalArtifacts,
    verify_pre_final_artifacts,
)
from gemini_trading.strategy.replay import parse_study_manifest
from gemini_trading.strategy.sealed_evaluator import (
    complete_candidate_strategy_study,
    prepare_candidate_strategy_study,
)
from gemini_trading.strategy.verification import StrategyStudyVerificationService

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FIXED_CONFIG = Path("tests/fixtures/strategy/candidate-v0.1-config.json")
_HANDOFF_NAME = "dataset-handoff.json"
_EXPECTED_EXCLUDED_ROW_SHA256 = "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"
_EXPECTED_SEGMENT_BOUNDARIES = (228,)
_EXPECTED_CANDLE_COUNT = 18_617


def _argument(arguments: argparse.Namespace, name: str) -> str:
    value: object = getattr(arguments, name, None)
    if not isinstance(value, str) or not value:
        raise CliUsageError(f"missing command-line argument: --{name.replace('_', '-')}")
    return value


def _positive_int_argument(arguments: argparse.Namespace, name: str) -> int:
    raw = _argument(arguments, name)
    try:
        value = int(raw)
    except ValueError:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a positive integer") from None
    if value < 1 or str(value) != raw:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a positive integer")
    return value


def _sha256_argument(arguments: argparse.Namespace, name: str) -> str:
    value = _argument(arguments, name)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a lowercase SHA-256 digest")
    return value


def _commit_argument(arguments: argparse.Namespace, name: str) -> str:
    value = _argument(arguments, name)
    if _GIT_COMMIT_PATTERN.fullmatch(value) is None:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a lowercase Git commit")
    return value


def _run_id_argument(arguments: argparse.Namespace) -> str:
    value = _argument(arguments, "run_id")
    if _RUN_ID_PATTERN.fullmatch(value) is None or ".." in value:
        raise CliUsageError("--run-id is invalid")
    return value


def _root(arguments: argparse.Namespace, name: str) -> Path:
    return Path(_argument(arguments, name)).resolve(strict=False)


def _safe_relative(path: Path, root: Path) -> str:
    resolved_root = root.resolve(strict=False)
    try:
        return path.resolve(strict=False).relative_to(resolved_root).as_posix()
    except ValueError:
        raise CliUsageError("result path escaped the configured output root") from None


def resolve_locked_candidate_config(arguments: argparse.Namespace, project_root: Path) -> Path:
    supplied = Path(_argument(arguments, "config")).resolve(strict=False)
    expected = (project_root / _FIXED_CONFIG).resolve(strict=False)
    if supplied != expected:
        raise CliUsageError("sealed validation requires the locked Candidate configuration")
    return expected


def _handoff_path(output_root: Path, dataset_id: str) -> Path:
    return output_root / "data" / "historical-validation" / "handoff" / dataset_id / _HANDOFF_NAME


def _read_handoff(path: Path) -> DatasetHandoffManifest:
    try:
        return load_dataset_handoff(path.read_bytes())
    except OSError:
        raise CliUsageError("dataset handoff is missing") from None


def _object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CliUsageError(f"invalid {description}") from None
    if not isinstance(loaded, dict):
        raise CliUsageError(f"invalid {description}")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise CliUsageError(f"invalid {description}")
    return cast(dict[str, object], mapping)


def _required_str(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise CliUsageError(f"invalid {description} field: {key}")
    return value


def _pre_final_identity(
    output_root: Path, pre_final_id: str
) -> tuple[PreFinalArtifacts, dict[str, object]]:
    artifacts = LocalPreFinalStore(output_root).load(pre_final_id)
    verify_pre_final_artifacts(artifacts)
    manifest = _object(artifacts.artifact_bytes("pre-final-manifest.json"), "pre-final manifest")
    return artifacts, manifest


def _dataset_payload(result: IngestionResult, output_root: Path) -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": result.run_id,
        "dataset_id": result.dataset_id,
        "raw_page_count": result.raw_page_count,
        "candle_count": result.candle_count,
        "paths": {name: _safe_relative(path, output_root) for name, path in result.paths},
    }


def _dataset_ingest(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    closure_manifest, closure_bytes = load_fixed_btcusdt_closure_manifest(project_root)
    request = RetrievalRequest(
        instrument=closure_manifest.instrument,
        timeframe=closure_manifest.timeframe,
        start_time=closure_manifest.start_time,
        end_time=closure_manifest.end_time,
    )
    store = LocalImmutableStore(output_root)
    result = IngestionService(
        provider=BinanceSpotProvider(),
        raw_store=store,
        canonical_store=store,
        closure_manifest=closure_manifest,
        closure_manifest_bytes=closure_bytes,
    ).ingest(request)
    return _dataset_payload(result, output_root)


def _dataset_replay(arguments: argparse.Namespace) -> dict[str, object]:
    run_id = _run_id_argument(arguments)
    output_root = _root(arguments, "output_root")
    store = LocalImmutableStore(output_root)
    result = ReplayService(raw_store=store, canonical_store=store).replay(run_id)
    return _dataset_payload(result, output_root)


def _dataset_verify(arguments: argparse.Namespace) -> dict[str, object]:
    dataset_id = _sha256_argument(arguments, "dataset_id")
    run_id = _run_id_argument(arguments)
    output_root = _root(arguments, "output_root")
    store = LocalImmutableStore(output_root)
    result = VerificationService(raw_store=store, canonical_store=store).verify(dataset_id, run_id)
    return {
        "status": "verified",
        "dataset_id": result.dataset_id,
        "run_id": result.run_id,
        "candle_count": result.candle_count,
        "checks": list(result.checks),
    }


def _strategy_handoff(arguments: argparse.Namespace) -> dict[str, object]:
    run_id = _run_id_argument(arguments)
    dataset_id = _sha256_argument(arguments, "dataset_id")
    source_commit = _commit_argument(arguments, "source_commit")
    workflow_run_id = _positive_int_argument(arguments, "workflow_run_id")
    workflow_run_attempt = _positive_int_argument(arguments, "workflow_run_attempt")
    output_root = _root(arguments, "output_root")
    store = LocalImmutableStore(output_root)
    verification = VerificationService(raw_store=store, canonical_store=store).verify(
        dataset_id,
        run_id,
    )
    dataset = load_verified_dataset(store, dataset_id, require_v3=True)
    raw_root = output_root / "data" / "raw" / "binance_spot" / run_id
    canonical_root = output_root / "data" / "canonical" / dataset_id
    relative_paths = tuple(
        sorted(
            path.relative_to(output_root).as_posix()
            for base in (raw_root, canonical_root)
            for path in base.rglob("*")
            if path.is_file()
        )
    )
    files = build_artifact_inventory(output_root, relative_paths)
    if (
        dataset.manifest.closure_manifest_sha256 is None
        or dataset.manifest.exclusion_manifest_sha256 is None
        or dataset.manifest.segment_manifest_sha256 is None
        or dataset.closure_manifest is None
        or dataset.exclusion_manifest is None
        or dataset.segment_manifest is None
    ):
        raise CliUsageError("verified v3 dataset is missing supporting identity")
    excluded_row_hashes = tuple(
        item.provider_row_sha256 for item in dataset.exclusion_manifest.exclusions
    )
    segment_boundaries = dataset.segment_manifest.boundary_indices
    if (
        dataset.manifest.closure_count != 1
        or dataset.manifest.exclusion_count != 1
        or dataset.manifest.segment_count != 2
        or excluded_row_hashes != (_EXPECTED_EXCLUDED_ROW_SHA256,)
        or segment_boundaries != _EXPECTED_SEGMENT_BOUNDARIES
        or verification.candle_count != _EXPECTED_CANDLE_COUNT
    ):
        raise CliUsageError("verified v3 dataset fixed evidence identity mismatch")
    manifest = DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v3",
        repository="muhamedsohaib/gemini-trading",
        source_commit=source_commit,
        workflow_name="sealed-btcusdt-dataset",
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        job_name="dataset",
        provider=dataset.manifest.provider,
        symbol=dataset.manifest.instrument.symbol,
        base_asset=dataset.manifest.instrument.base_asset,
        quote_asset=dataset.manifest.instrument.quote_asset,
        interval=dataset.manifest.timeframe.value,
        start=dataset.manifest.start_time.isoformat().replace("+00:00", "Z"),
        end_exclusive=dataset.manifest.end_time.isoformat().replace("+00:00", "Z"),
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_schema_version=dataset.manifest.schema_version,
        closure_manifest_path=_safe_relative(
            canonical_root / "exchange-closures.json", output_root
        ),
        closure_manifest_sha256=dataset.manifest.closure_manifest_sha256,
        exclusion_manifest_path=_safe_relative(
            canonical_root / "candle-exclusions.json", output_root
        ),
        exclusion_manifest_sha256=dataset.manifest.exclusion_manifest_sha256,
        segment_manifest_path=_safe_relative(canonical_root / "candle-segments.json", output_root),
        segment_manifest_sha256=dataset.manifest.segment_manifest_sha256,
        closure_count=dataset.manifest.closure_count,
        exclusion_count=dataset.manifest.exclusion_count,
        segment_count=dataset.manifest.segment_count,
        closure_ids=tuple(item.closure_id for item in dataset.closure_manifest.closures),
        excluded_provider_row_sha256=excluded_row_hashes[0],
        segment_boundary_indices=segment_boundaries,
        candle_count=verification.candle_count,
        first_open_time=dataset.manifest.first_open_time.isoformat().replace("+00:00", "Z"),
        last_open_time=dataset.manifest.last_open_time.isoformat().replace("+00:00", "Z"),
        replay_status="completed",
        verification_status="verified",
        files=files,
        inventory_root_sha256=inventory_root_sha256(files),
    )
    path = _handoff_path(output_root, dataset_id)
    write_immutable(path, serialize_dataset_handoff(manifest))
    verify_dataset_handoff(
        manifest,
        output_root,
        expected_commit=source_commit,
        expected_dataset_id=dataset_id,
        expected_run_id=workflow_run_id,
    )
    return {
        "dataset_id": dataset_id,
        "handoff_path": _safe_relative(path, output_root),
        "inventory_root_sha256": manifest.inventory_root_sha256,
        "status": "verified",
    }


def _strategy_prepare(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    handoff_path = Path(_argument(arguments, "handoff")).resolve(strict=False)
    config_path = resolve_locked_candidate_config(arguments, project_root)
    handoff = _read_handoff(handoff_path)
    verify_dataset_handoff(handoff, output_root)
    config = load_candidate_strategy_config(config_path)
    code_commit = resolve_clean_git_commit(project_root)
    if code_commit != handoff.source_commit:
        raise CliUsageError("code commit does not match dataset handoff")
    dataset = load_verified_dataset(
        LocalImmutableStore(output_root), handoff.dataset_id, require_v3=True
    )
    artifacts = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=config.simulation,
        initial_cash=config.initial_cash,
        output_root=output_root,
        code_commit=code_commit,
        handoff=handoff,
    )
    return {"pre_final_id": artifacts.pre_final_id, "status": "prepared"}


def _strategy_authorize_final(arguments: argparse.Namespace) -> dict[str, object]:
    pre_final_id = _sha256_argument(arguments, "pre_final_id")
    workflow_run_id = _positive_int_argument(arguments, "workflow_run_id")
    workflow_run_attempt = _positive_int_argument(arguments, "workflow_run_attempt")
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    artifacts, manifest = _pre_final_identity(output_root, pre_final_id)
    del artifacts
    identity = FinalAccessIdentity(
        code_commit=resolve_clean_git_commit(project_root),
        dataset_id=_required_str(manifest, "dataset_id", "pre-final manifest"),
        configuration_sha256=_required_str(manifest, "configuration_sha256", "pre-final manifest"),
        policy_sha256=_required_str(manifest, "policy_sha256", "pre-final manifest"),
        split_plan_sha256=_required_str(manifest, "split_plan_sha256", "pre-final manifest"),
        pre_final_id=pre_final_id,
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
    )
    receipt = FinalAccessStore(output_root).authorize(identity)
    return {
        "pre_final_id": pre_final_id,
        "receipt_id": receipt.receipt_id,
        "status": "authorized",
    }


def _strategy_finalize(arguments: argparse.Namespace) -> dict[str, object]:
    pre_final_id = _sha256_argument(arguments, "pre_final_id")
    receipt_id = _sha256_argument(arguments, "receipt_id")
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    pre_final, manifest = _pre_final_identity(output_root, pre_final_id)
    dataset_id = _required_str(manifest, "dataset_id", "pre-final manifest")
    handoff = _read_handoff(_handoff_path(output_root, dataset_id))
    verify_dataset_handoff(handoff, output_root)
    code_commit = resolve_clean_git_commit(project_root)
    receipt = FinalAccessStore(output_root).load(receipt_id)
    config = load_candidate_strategy_config(project_root / _FIXED_CONFIG)
    dataset = load_verified_dataset(LocalImmutableStore(output_root), dataset_id, require_v3=True)
    artifacts = complete_candidate_strategy_study(
        pre_final=pre_final,
        receipt=receipt,
        handoff=handoff,
        dataset=dataset,
        simulation=config.simulation,
        initial_cash=config.initial_cash,
        output_root=output_root,
        code_commit=code_commit,
    )
    return {
        "classification": artifacts.classification.value,
        "promotable": False,
        "status": "completed",
        "study_id": artifacts.study_id,
        "study_result_id": artifacts.study_result_id,
    }


def _strategy_resume(arguments: argparse.Namespace) -> dict[str, object]:
    study_id = _sha256_argument(arguments, "study_id")
    receipt_id = _sha256_argument(arguments, "receipt_id")
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    receipt = FinalAccessStore(output_root).load(receipt_id)
    manifest = parse_study_manifest(
        LocalStrategyStudyStore(output_root).read_artifact(study_id, "study-manifest.json")
    )
    if manifest.durable_final_access_receipt_id != receipt.receipt_id:
        raise CliUsageError("receipt does not match strategy study")
    result = StrategyStudyVerificationService(
        root=output_root,
        current_commit_resolver=lambda: resolve_clean_git_commit(project_root),
    ).verify(study_id)
    return {
        "classification": result.classification.value,
        "promotable": False,
        "status": "verified",
        "study_id": result.study_id,
        "study_result_id": result.study_result_id,
    }


def run_historical_validation(arguments: argparse.Namespace) -> dict[str, object]:
    """Run one fixed-scope historical-validation command."""

    load_runtime_policy()
    command = _argument(arguments, "research_command")
    if command == "dataset-ingest":
        return _dataset_ingest(arguments)
    if command == "dataset-replay":
        return _dataset_replay(arguments)
    if command == "dataset-verify":
        return _dataset_verify(arguments)
    if command == "strategy-handoff":
        return _strategy_handoff(arguments)
    if command == "strategy-prepare":
        return _strategy_prepare(arguments)
    if command == "strategy-authorize-final":
        return _strategy_authorize_final(arguments)
    if command == "strategy-finalize":
        return _strategy_finalize(arguments)
    if command == "strategy-resume":
        return _strategy_resume(arguments)
    raise CliUsageError("unsupported historical-validation command")


__all__ = ["resolve_locked_candidate_config", "run_historical_validation"]
