"""Regression tests for write-before-read durable final authorization."""

from pathlib import Path

import pytest

from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.final_access import (
    DurableFinalAccessReceipt,
    FinalAccessIdentity,
    FinalAccessStore,
    authorize_then_load_final,
    final_access_seal_id,
)


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


def test_final_rows_load_only_after_receipt_and_stable_seal_exist(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)
    observed: list[bool] = []

    def load_rows() -> tuple[int, ...]:
        base = tmp_path / "data" / "historical-validation" / "final-access"
        seal_path = (
            base
            / "seals"
            / final_access_seal_id(_identity())
            / "final-access-seal.json"
        )
        receipts = tuple((base / "receipts").rglob("final-access-receipt.json"))
        observed.append(seal_path.is_file() and len(receipts) == 1)
        return (1, 2, 3)

    receipt, rows = authorize_then_load_final(store, _identity(), load_rows)

    assert observed == [True]
    assert rows == (1, 2, 3)
    assert store.load(receipt.receipt_id) == receipt


def test_failed_receipt_persistence_never_calls_final_loader() -> None:
    class FailingStore:
        def authorize(self, identity: FinalAccessIdentity) -> DurableFinalAccessReceipt:
            del identity
            raise FinalAccessError("simulated receipt persistence failure")

    called = False

    def load_rows() -> tuple[int, ...]:
        nonlocal called
        called = True
        return (1,)

    store = FailingStore()
    guard = authorize_then_load_final

    with pytest.raises(FinalAccessError, match="persistence failure"):
        guard(store, _identity(), load_rows)  # type: ignore[arg-type]

    assert called is False


def test_repeated_authorization_never_reloads_final_rows(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)

    def initial_loader() -> tuple[int, ...]:
        return (1,)

    authorize_then_load_final(store, _identity(), initial_loader)
    called = False

    def repeated_loader() -> tuple[int, ...]:
        nonlocal called
        called = True
        return (2,)

    with pytest.raises(FinalAccessError, match="seal already exists"):
        authorize_then_load_final(store, _identity(), repeated_loader)

    assert called is False
