"""Unit tests for durable final-test access authorization."""

from dataclasses import replace
from pathlib import Path

import pytest

from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.final_access import (
    FinalAccessIdentity,
    FinalAccessStore,
    ResumeDecision,
    assess_exact_resume,
    load_receipt,
    serialize_receipt,
)
from gemini_trading.strategy.handoff import build_artifact_inventory


def _identity() -> FinalAccessIdentity:
    return FinalAccessIdentity(
        code_commit="a" * 40,
        dataset_id="b" * 64,
        configuration_sha256="c" * 64,
        policy_sha256="d" * 64,
        split_plan_sha256="e" * 64,
        pre_final_id="f" * 64,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )


def test_authorize_writes_one_immutable_receipt(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)

    receipt = store.authorize(_identity())

    assert store.load(receipt.receipt_id) == receipt
    assert load_receipt(serialize_receipt(receipt)) == receipt
    with pytest.raises(FinalAccessError, match="already exists"):
        store.authorize(_identity())


def test_changed_run_attempt_cannot_reuse_receipt(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)
    receipt = store.authorize(_identity())
    changed = replace(_identity(), workflow_run_attempt=2)

    with pytest.raises(FinalAccessError, match="identity mismatch"):
        store.require(receipt.receipt_id, changed)


def test_receipt_rejects_noncanonical_encoding(tmp_path: Path) -> None:
    receipt = FinalAccessStore(tmp_path).authorize(_identity())
    raw = serialize_receipt(receipt)

    with pytest.raises(FinalAccessError, match="canonical"):
        load_receipt(raw.replace(b'"receipt_id":', b'"receipt_id": '))


def test_exact_resume_requires_complete_untampered_outputs(tmp_path: Path) -> None:
    receipt = FinalAccessStore(tmp_path).authorize(_identity())
    output = tmp_path / "completed.json"
    output.write_bytes(b"{}\n")
    inventory = build_artifact_inventory(tmp_path, ("completed.json",))

    allowed = assess_exact_resume(
        receipt=receipt,
        identity=_identity(),
        completed_final_files=inventory,
        artifact_root=tmp_path,
    )

    assert allowed.decision is ResumeDecision.ALLOWED
    assert allowed.checks == (
        "identity_match",
        "final_outputs_complete",
        "provider_free_resume_only",
    )

    output.write_bytes(b'{"tampered":true}\n')
    rejected = assess_exact_resume(
        receipt=receipt,
        identity=_identity(),
        completed_final_files=inventory,
        artifact_root=tmp_path,
    )
    assert rejected.decision is ResumeDecision.INCONCLUSIVE
    assert rejected.checks == ("final_outputs_tampered",)


def test_exact_resume_rejects_identity_mismatch_and_missing_outputs(tmp_path: Path) -> None:
    receipt = FinalAccessStore(tmp_path).authorize(_identity())

    mismatch = assess_exact_resume(
        receipt=receipt,
        identity=replace(_identity(), workflow_run_attempt=2),
        completed_final_files=(),
        artifact_root=tmp_path,
    )
    missing = assess_exact_resume(
        receipt=receipt,
        identity=_identity(),
        completed_final_files=(),
        artifact_root=tmp_path,
    )

    assert mismatch.decision is ResumeDecision.INCONCLUSIVE
    assert mismatch.checks == ("identity_mismatch",)
    assert missing.decision is ResumeDecision.INCONCLUSIVE
    assert missing.checks == ("final_outputs_missing",)


def test_invalid_identity_values_fail_closed() -> None:
    with pytest.raises(FinalAccessError, match="code commit"):
        replace(_identity(), code_commit="not-a-commit")
    with pytest.raises(FinalAccessError, match="workflow run attempt"):
        replace(_identity(), workflow_run_attempt=0)
