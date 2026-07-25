"""Independent verification of the sealed historical-validation evidence chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES
from gemini_trading.strategy.errors import StudyVerificationError
from gemini_trading.strategy.final_access import (
    FinalAccessIdentity,
    FinalAccessStore,
    ResumeDecision,
    assess_exact_resume,
)
from gemini_trading.strategy.handoff import (
    build_artifact_inventory,
    load_dataset_handoff,
    verify_dataset_handoff,
)
from gemini_trading.strategy.pre_final import LocalPreFinalStore, verify_pre_final_artifacts
from gemini_trading.strategy.replay import StoredStrategyStudyManifest


def _object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyVerificationError(f"invalid {description} JSON") from None
    if not isinstance(loaded, dict):
        raise StudyVerificationError(f"invalid {description} JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise StudyVerificationError(f"invalid {description} JSON object")
    return cast(dict[str, object], mapping)


def _required_str(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise StudyVerificationError(f"invalid {description} field: {key}")
    return value


def verify_sealed_evidence_chain(
    *,
    root: Path,
    study_id: str,
    manifest: StoredStrategyStudyManifest,
) -> tuple[str, ...]:
    """Verify every persisted identity from handoff through exact-resume evidence."""

    if (
        manifest.pre_final_id is None
        or manifest.dataset_handoff_inventory_root is None
        or manifest.durable_final_access_receipt_id is None
    ):
        return ()

    pre_final = LocalPreFinalStore(root).load(manifest.pre_final_id)
    pre_final_manifest = _object(
        pre_final.artifact_bytes("pre-final-manifest.json"),
        "pre-final manifest",
    )
    dataset_id = _required_str(pre_final_manifest, "dataset_id", "pre-final manifest")
    handoff_path = (
        root / "data" / "historical-validation" / "handoff" / dataset_id / "dataset-handoff.json"
    )
    try:
        handoff = load_dataset_handoff(handoff_path.read_bytes())
    except OSError:
        raise StudyVerificationError("sealed dataset handoff is missing") from None
    try:
        verify_dataset_handoff(
            handoff,
            root,
            expected_commit=manifest.code_commit,
            expected_dataset_id=dataset_id,
        )
    except Exception:
        raise StudyVerificationError("sealed dataset handoff verification failed") from None
    if handoff.inventory_root_sha256 != manifest.dataset_handoff_inventory_root:
        raise StudyVerificationError("sealed dataset handoff inventory root mismatch")

    try:
        verify_pre_final_artifacts(
            pre_final,
            expected_handoff=handoff,
            expected_code_commit=manifest.code_commit,
            expected_dataset_id=dataset_id,
        )
    except Exception:
        raise StudyVerificationError("sealed pre-final verification failed") from None
    if pre_final.pre_final_id != manifest.pre_final_id:
        raise StudyVerificationError("sealed pre-final identity mismatch")

    receipt = FinalAccessStore(root).load(manifest.durable_final_access_receipt_id)
    expected_identity = FinalAccessIdentity(
        code_commit=manifest.code_commit,
        dataset_id=dataset_id,
        configuration_sha256=manifest.configuration_sha256,
        policy_sha256=manifest.policy_sha256,
        split_plan_sha256=manifest.split_plan_sha256,
        pre_final_id=manifest.pre_final_id,
        workflow_run_id=receipt.identity.workflow_run_id,
        workflow_run_attempt=receipt.identity.workflow_run_attempt,
    )
    if receipt.identity != expected_identity:
        raise StudyVerificationError("durable final-access identity mismatch")
    if receipt.receipt_id != manifest.final_test_receipt_id:
        raise StudyVerificationError("study final receipt identity mismatch")
    if receipt.receipt_id != manifest.durable_final_access_receipt_id:
        raise StudyVerificationError("durable final receipt manifest mismatch")
    if receipt.evaluation_count != 1 or manifest.final_evaluation_count != 1:
        raise StudyVerificationError("sealed final test was not accessed exactly once")

    study_paths = tuple(
        f"data/strategy-studies/{study_id}/{name}" for name in REQUIRED_STUDY_ARTIFACT_NAMES
    )
    inventory = build_artifact_inventory(root, study_paths)
    assessment = assess_exact_resume(
        receipt=receipt,
        identity=expected_identity,
        completed_final_files=inventory,
        artifact_root=root,
    )
    if assessment.decision is not ResumeDecision.ALLOWED:
        raise StudyVerificationError("sealed exact-resume evidence is incomplete")

    return (
        "dataset_handoff_verified",
        "durable_final_access_verified",
        "exact_resume_policy_verified",
        "pre_final_identity_verified",
        "single_final_access_verified",
    )


__all__ = ["verify_sealed_evidence_chain"]
