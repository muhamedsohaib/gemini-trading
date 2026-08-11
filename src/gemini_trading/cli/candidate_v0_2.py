"""Safe CLI handlers for Candidate v0.2 development qualification and prospective seal."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from gemini_trading.cli.market_data import CliUsageError
from gemini_trading.cli.strategy import load_candidate_strategy_config
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.replay import resolve_clean_git_commit
from gemini_trading.safety.execution_mode import load_runtime_policy
from gemini_trading.strategy.errors import DatasetHandoffError, FinalAccessError, StudyArtifactError
from gemini_trading.strategy.handoff import load_dataset_handoff, verify_dataset_handoff
from gemini_trading.strategy.prospective_seal import (
    LocalProspectiveFinalSealStore,
    ProspectiveFinalSealRequest,
)
from gemini_trading.strategy.qualification import QualificationClassification
from gemini_trading.strategy.qualification_artifacts import (
    LocalQualificationStore,
    QualificationArtifactContext,
    QualificationArtifacts,
    build_qualification_artifacts,
)
from gemini_trading.strategy.qualification_execution import execute_candidate_v0_2_qualification
from gemini_trading.strategy.qualification_verification import verify_qualification_bundle

_V0_2_STRATEGY_ID = "candidate.multi_model.v0_2"
_V0_2_POLICY_VERSION = "candidate-multi-model-v0.2"
_DEVELOPMENT_CUTOFF = datetime(2026, 7, 1, tzinfo=UTC)
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


def _utc_timestamp(arguments: argparse.Namespace, name: str) -> datetime:
    raw = _argument(arguments, name)
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise CliUsageError(
            f"--{name.replace('_', '-')} must be an ISO-8601 UTC timestamp"
        ) from None
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None or offset.total_seconds() != 0:
        raise CliUsageError(f"--{name.replace('_', '-')} must be an ISO-8601 UTC timestamp")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


def _qualify(arguments: argparse.Namespace) -> dict[str, object]:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    handoff_path = Path(_argument(arguments, "handoff")).resolve(strict=False)
    config = load_candidate_strategy_config(Path(_argument(arguments, "config")))
    if config.strategy_id != _V0_2_STRATEGY_ID or config.policy_version != _V0_2_POLICY_VERSION:
        raise StudyArtifactError("Candidate v0.2 qualification requires the exact v0.2 config")
    code_commit = resolve_clean_git_commit(project_root)
    try:
        handoff = load_dataset_handoff(handoff_path.read_bytes())
    except OSError:
        raise DatasetHandoffError("unable to read dataset handoff") from None
    artifact_root = _qualification_root(handoff_path, output_root)
    verify_dataset_handoff(
        handoff,
        artifact_root,
        expected_commit=code_commit,
        expected_dataset_id=handoff.dataset_id,
        expected_run_id=handoff.workflow_run_id,
    )
    dataset = load_verified_dataset(LocalImmutableStore(artifact_root), handoff.dataset_id)
    qualification = execute_candidate_v0_2_qualification(
        dataset=dataset,
        handoff=handoff,
        simulation=config.simulation,
        initial_cash=config.initial_cash,
        output_root=artifact_root,
        code_commit=code_commit,
    )
    artifacts = build_qualification_artifacts(
        qualification,
        QualificationArtifactContext(
            code_commit=code_commit,
            dataset_id=handoff.dataset_id,
            dataset_handoff_inventory_root=handoff.inventory_root_sha256,
            dataset_run_id=handoff.workflow_run_id,
            workflow_run_id=_positive_integer(arguments, "workflow_run_id"),
            workflow_run_attempt=_positive_integer(arguments, "workflow_run_attempt"),
        ),
    )
    LocalQualificationStore(artifact_root).write(artifacts)
    return {
        "classification": artifacts.classification.value,
        "inventory_root_sha256": artifacts.inventory_root_sha256,
        "promotable": False,
        "qualification_id": artifacts.qualification_id,
        "status": "completed",
    }


def _verified_bundle(arguments: argparse.Namespace) -> QualificationArtifacts:
    project_root = Path(_argument(arguments, "project_root")).resolve(strict=False)
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    qualification_id = _argument(arguments, "qualification_id")
    code_commit = resolve_clean_git_commit(project_root)
    return verify_qualification_bundle(
        output_root,
        qualification_id,
        expected_commit=code_commit,
    )


def _verify(arguments: argparse.Namespace) -> dict[str, object]:
    artifacts = _verified_bundle(arguments)
    return {
        "classification": artifacts.classification.value,
        "inventory_root_sha256": artifacts.inventory_root_sha256,
        "promotable": False,
        "qualification_id": artifacts.qualification_id,
        "status": "verified",
    }


def _seal(arguments: argparse.Namespace) -> dict[str, object]:
    output_root = Path(_argument(arguments, "output_root")).resolve(strict=False)
    verified = _verified_bundle(arguments)
    if verified.classification is not QualificationClassification.QUALIFIED:
        raise FinalAccessError("prospective final seal requires QUALIFIED evidence")
    seal = LocalProspectiveFinalSealStore(output_root).create(
        ProspectiveFinalSealRequest(
            code_commit=verified.context.code_commit,
            dataset_id=verified.context.dataset_id,
            dataset_handoff_inventory_root=verified.context.dataset_handoff_inventory_root,
            qualification_id=verified.qualification_id,
            qualification_inventory_root=verified.inventory_root_sha256,
            qualification_classification=verified.classification,
            workflow_run_id=verified.context.workflow_run_id,
            workflow_run_attempt=verified.context.workflow_run_attempt,
            verified_at=_utc_timestamp(arguments, "verified_at"),
            development_cutoff=_DEVELOPMENT_CUTOFF,
        )
    )
    return {
        "bridge_end": _timestamp(seal.bridge_end),
        "bridge_start": _timestamp(seal.bridge_start),
        "execution_authorized": False,
        "final_end": _timestamp(seal.final_end),
        "final_start": _timestamp(seal.final_start),
        "promotable": False,
        "seal_id": seal.seal_id,
        "status": "sealed",
    }


def run_candidate_v0_2(arguments: argparse.Namespace) -> dict[str, object]:
    """Dispatch one Candidate v0.2 research-only qualification command."""

    load_runtime_policy()
    command = _argument(arguments, "research_command")
    if command == "strategy-v0-2-qualify":
        return _qualify(arguments)
    if command == "strategy-v0-2-qualification-verify":
        return _verify(arguments)
    if command == "strategy-v0-2-seal-prospective-final":
        return _seal(arguments)
    raise CliUsageError("unsupported Candidate v0.2 research command")


__all__ = ["run_candidate_v0_2"]
