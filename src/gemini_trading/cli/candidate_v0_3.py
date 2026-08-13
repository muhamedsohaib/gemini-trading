"""Safe CLI handlers for Candidate v0.3 development qualification."""

from __future__ import annotations

import argparse
from pathlib import Path

from gemini_trading.cli.market_data import CliUsageError
from gemini_trading.cli.strategy import load_candidate_strategy_config
from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.replay import resolve_clean_git_commit
from gemini_trading.safety.execution_mode import load_runtime_policy
from gemini_trading.strategy.errors import DatasetHandoffError, StudyArtifactError
from gemini_trading.strategy.prospective_seal_v0_3 import V03LocalProspectiveFinalSealStore
from gemini_trading.strategy.qualification_artifacts_v0_3 import (
    V03LocalQualificationStore,
    V03QualificationArtifactContext,
    V03QualificationArtifacts,
    build_v0_3_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution_v0_3 import (
    execute_candidate_v0_3_qualification,
)
from gemini_trading.strategy.qualification_verification_v0_3 import (
    verify_candidate_v0_3_qualification,
)
from gemini_trading.strategy.v0_3_stage1 import (
    build_v0_3_closure_manifest,
    create_v0_3_dataset_handoff,
    load_v0_3_dataset_handoff,
    verify_v0_3_dataset_handoff,
)

_V0_3_STRATEGY_ID = "candidate.multi_model.v0_3"
_V0_3_POLICY_VERSION = "candidate-multi-model-v0.3"
_HANDOFF_PREFIX = ("data", "historical-validation", "handoff")


def _argument(arguments: argparse.Namespace, name: str) -> str:
    value: object = getattr(arguments, name, None)
    if not isinstance(value, str) or not value:
        raise CliUsageError(f"missing command-line argument: --{name.replace('_', '-')}")
    return value


def _positive_integer(arguments: argparse.Namespace, name: str) -> int:
    raw = _argument(arguments, name)
    try:
        value = int(raw)
    except ValueError:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a positive integer") from None
    if value < 1:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a positive integer")
    return value


def _safe_relative(path: Path, root: Path) -> str:
    resolved_root = root.resolve(strict=False)
    try:
        return path.resolve(strict=False).relative_to(resolved_root).as_posix()
    except ValueError:
        raise DatasetHandoffError("Candidate v0.3 result path escaped the output root") from None


def _qualification_root(handoff_path: Path, output_root: Path) -> Path:
    resolved_root = output_root.resolve(strict=False)
    resolved_handoff = handoff_path.resolve(strict=False)
    try:
        relative = resolved_handoff.relative_to(resolved_root)
    except ValueError:
        raise DatasetHandoffError(
            "dataset handoff path is outside the Stage 1 artifact root"
        ) from None
    parts = relative.parts
    if len(parts) != 5:
        raise DatasetHandoffError("dataset handoff path does not match the fixed artifact layout")
    if parts[:3] != _HANDOFF_PREFIX or parts[-1] != "dataset-handoff.json":
        raise DatasetHandoffError("dataset handoff path does not match the fixed artifact layout")
    return resolved_root


def _research_only(payload: dict[str, object]) -> dict[str, object]:
    return {
        **payload,
        "boundary": "RESEARCH_ONLY",
        "execution_authorized": False,
        "promotable": False,
    }


def _ingest_stage1(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    closure_manifest, closure_bytes = build_v0_3_closure_manifest(project_root)
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
    return _research_only(
        {
            "status": "completed",
            "run_id": result.run_id,
            "dataset_id": result.dataset_id,
            "raw_page_count": result.raw_page_count,
            "candle_count": result.candle_count,
            "paths": {name: _safe_relative(path, output_root) for name, path in result.paths},
        }
    )


def _handoff_stage1(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    source_commit = _argument(arguments, "source_commit")
    if resolve_clean_git_commit(project_root) != source_commit:
        raise DatasetHandoffError("Candidate v0.3 Stage 1 source commit mismatch")
    manifest, path = create_v0_3_dataset_handoff(
        project_root=project_root,
        output_root=output_root,
        run_id=_argument(arguments, "run_id"),
        dataset_id=_argument(arguments, "dataset_id"),
        source_commit=source_commit,
        workflow_run_id=_positive_integer(arguments, "workflow_run_id"),
        workflow_run_attempt=_positive_integer(arguments, "workflow_run_attempt"),
    )
    return _research_only(
        {
            "dataset_id": manifest.dataset_id,
            "handoff_path": _safe_relative(path, output_root),
            "inventory_root_sha256": manifest.inventory_root_sha256,
            "status": "verified",
        }
    )


def _qualify(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    handoff_path = Path(_argument(arguments, "handoff")).resolve(strict=False)
    config = load_candidate_strategy_config(Path(_argument(arguments, "config")))
    if config.strategy_id != _V0_3_STRATEGY_ID or config.policy_version != _V0_3_POLICY_VERSION:
        raise StudyArtifactError("Candidate v0.3 qualification requires the exact v0.3 config")
    code_commit = resolve_clean_git_commit(project_root)
    try:
        handoff = load_v0_3_dataset_handoff(handoff_path.read_bytes())
    except OSError:
        raise DatasetHandoffError("unable to read dataset handoff") from None
    artifact_root = _qualification_root(handoff_path, output_root)
    verify_v0_3_dataset_handoff(
        handoff,
        artifact_root,
        project_root=project_root,
        expected_commit=code_commit,
        expected_dataset_id=handoff.dataset_id,
        expected_run_id=handoff.workflow_run_id,
    )
    dataset = load_verified_dataset(LocalImmutableStore(artifact_root), handoff.dataset_id)
    qualification = execute_candidate_v0_3_qualification(
        dataset=dataset,
        handoff=handoff,
        simulation=config.simulation,
        initial_cash=config.initial_cash,
        output_root=artifact_root,
        code_commit=code_commit,
    )
    artifacts = build_v0_3_qualification_artifacts(
        qualification,
        V03QualificationArtifactContext(
            code_commit=code_commit,
            dataset_id=handoff.dataset_id,
            dataset_handoff_inventory_root=handoff.inventory_root_sha256,
            dataset_run_id=handoff.workflow_run_id,
            workflow_run_id=_positive_integer(arguments, "workflow_run_id"),
            workflow_run_attempt=_positive_integer(arguments, "workflow_run_attempt"),
        ),
    )
    V03LocalQualificationStore(artifact_root).write(artifacts)
    return _research_only(
        {
            "classification": artifacts.classification.value,
            "inventory_root_sha256": artifacts.inventory_root_sha256,
            "qualification_id": artifacts.qualification_id,
            "status": "completed",
        }
    )


def _verified_bundle(arguments: argparse.Namespace) -> V03QualificationArtifacts:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    qualification_id = _argument(arguments, "qualification_id")
    code_commit = resolve_clean_git_commit(project_root)
    return verify_candidate_v0_3_qualification(
        output_root,
        qualification_id,
        expected_commit=code_commit,
        project_root=project_root,
    )


def _verify(arguments: argparse.Namespace) -> dict[str, object]:
    artifacts = _verified_bundle(arguments)
    return _research_only(
        {
            "classification": artifacts.classification.value,
            "inventory_root_sha256": artifacts.inventory_root_sha256,
            "qualification_id": artifacts.qualification_id,
            "status": "verified",
        }
    )


def _utc_text(value: object) -> str:
    isoformat = getattr(value, "isoformat", None)
    if not callable(isoformat):
        raise StudyArtifactError("Candidate v0.3 seal boundary is not a timestamp")
    text = isoformat()
    if not isinstance(text, str):
        raise StudyArtifactError("Candidate v0.3 seal boundary encoding is invalid")
    return text.replace("+00:00", "Z")


def _seal(arguments: argparse.Namespace) -> dict[str, object]:
    artifacts = _verified_bundle(arguments)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    seal = V03LocalProspectiveFinalSealStore(output_root).create(artifacts)
    return _research_only(
        {
            "bridge_end": _utc_text(seal.bridge_end),
            "bridge_start": _utc_text(seal.bridge_start),
            "final_end": _utc_text(seal.final_end),
            "final_start": _utc_text(seal.final_start),
            "qualification_id": seal.qualification_id,
            "seal_id": seal.seal_id,
            "status": "sealed",
        }
    )


def run_candidate_v0_3(arguments: argparse.Namespace) -> dict[str, object]:
    """Dispatch one Candidate v0.3 research-only qualification command."""

    load_runtime_policy()
    command = _argument(arguments, "research_command")
    if command == "dataset-v0-3-ingest":
        return _ingest_stage1(arguments)
    if command == "strategy-v0-3-handoff":
        return _handoff_stage1(arguments)
    if command == "strategy-v0-3-qualify":
        return _qualify(arguments)
    if command == "strategy-v0-3-verify-qualification":
        return _verify(arguments)
    if command == "strategy-v0-3-create-prospective-seal":
        return _seal(arguments)
    raise CliUsageError("unsupported Candidate v0.3 research command")


__all__ = ["run_candidate_v0_3"]
