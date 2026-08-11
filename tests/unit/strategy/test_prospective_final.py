"""RED tests for Candidate v0.2 prospective final-era calendar boundaries."""

from datetime import UTC, datetime

import pytest

from gemini_trading.strategy.prospective_final import ProspectiveFinalWindow

_DEVELOPMENT_CUTOFF = datetime(2026, 7, 1, tzinfo=UTC)


def test_august_verification_starts_september_and_seals_eighteen_months() -> None:
    window = ProspectiveFinalWindow.from_verified_at(
        development_cutoff=_DEVELOPMENT_CUTOFF,
        verified_at=datetime(2026, 8, 10, 15, 52, tzinfo=UTC),
    )

    assert window.bridge_start == _DEVELOPMENT_CUTOFF
    assert window.bridge_end == datetime(2026, 9, 1, tzinfo=UTC)
    assert window.final_start == datetime(2026, 9, 1, tzinfo=UTC)
    assert window.final_end == datetime(2028, 3, 1, tzinfo=UTC)


def test_verification_on_month_boundary_starts_at_next_month_boundary() -> None:
    window = ProspectiveFinalWindow.from_verified_at(
        development_cutoff=_DEVELOPMENT_CUTOFF,
        verified_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert window.final_start == datetime(2026, 10, 1, tzinfo=UTC)
    assert window.final_end == datetime(2028, 4, 1, tzinfo=UTC)


def test_verification_before_development_cutoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="verification timestamp"):
        ProspectiveFinalWindow.from_verified_at(
            development_cutoff=_DEVELOPMENT_CUTOFF,
            verified_at=datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
