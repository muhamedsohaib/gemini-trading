"""Tests for immutable account and ledger contracts."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot, LedgerEntry


def test_initial_account_is_cash_only_and_immutable() -> None:
    account = AccountSnapshot.initial(Decimal("1000.00"))

    assert account.cash == Decimal("1000.00")
    assert account.marked_equity == Decimal("1000.00")
    assert account.position_quantity == Decimal("0")
    with pytest.raises(FrozenInstanceError):
        account.cash = Decimal("0")  # type: ignore[misc]


def test_account_rejects_negative_cash_or_position() -> None:
    with pytest.raises(ValueError, match="cash"):
        AccountSnapshot.initial(Decimal("-1"))
    with pytest.raises(ValueError, match="position"):
        AccountSnapshot(
            cash=Decimal("10"),
            reserved_cash=Decimal("0"),
            position_quantity=Decimal("-1"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
            cumulative_fees=Decimal("0"),
            cumulative_execution_costs=Decimal("0"),
            marked_equity=Decimal("10"),
            peak_equity=Decimal("10"),
            drawdown=Decimal("0"),
        )


def test_account_validates_reservation_position_basis_and_drawdown() -> None:
    account = AccountSnapshot.initial(Decimal("100"))

    with pytest.raises(ValueError, match="reserved_cash"):
        replace(account, reserved_cash=Decimal("101"))
    with pytest.raises(ValueError, match="average_entry_price"):
        replace(account, average_entry_price=Decimal("1"))
    with pytest.raises(ValueError, match="drawdown"):
        replace(account, drawdown=Decimal("1.1"))


def test_ledger_entry_validates_sequence_balances_and_identifiers() -> None:
    entry = LedgerEntry(
        sequence=1,
        event_type="fill",
        order_id="order-1",
        fill_id="fill-1",
        cash_delta=Decimal("-10"),
        position_delta=Decimal("0.1"),
        fee_delta=Decimal("0.01"),
        resulting_cash=Decimal("90"),
        resulting_position=Decimal("0.1"),
    )

    assert entry.event_type == "fill"
    with pytest.raises(ValueError, match="sequence"):
        replace(entry, sequence=0)
    with pytest.raises(ValueError, match="resulting_cash"):
        replace(entry, resulting_cash=Decimal("-1"))
    with pytest.raises(ValueError, match="event_type"):
        replace(entry, event_type="   ")
