"""Prospective calendar boundaries for Candidate v0.2 final validation."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be UTC-aware")
    return value.astimezone(UTC)


def _add_months(value: datetime, months: int) -> datetime:
    zero_based_month = value.month - 1 + months
    year = value.year + zero_based_month // 12
    month = zero_based_month % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _strict_next_month_boundary(value: datetime) -> datetime:
    current_month = value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return _add_months(current_month, 1)


@dataclass(frozen=True, slots=True)
class ProspectiveFinalWindow:
    """One bridge quarantine followed by an exactly 18-month future final era."""

    development_cutoff: datetime
    verified_at: datetime
    bridge_start: datetime
    bridge_end: datetime
    final_start: datetime
    final_end: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "development_cutoff",
            "verified_at",
            "bridge_start",
            "bridge_end",
            "final_start",
            "final_end",
        ):
            _utc(getattr(self, field_name), field_name)
        if self.verified_at < self.development_cutoff:
            raise ValueError("verification timestamp must not precede development cutoff")
        if self.bridge_start != self.development_cutoff:
            raise ValueError("bridge must start at the development cutoff")
        if self.bridge_end != self.final_start:
            raise ValueError("bridge must end at the prospective final start")
        if self.final_start <= self.verified_at:
            raise ValueError("prospective final start must be strictly after verification")
        if self.final_start != self.final_start.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ):
            raise ValueError("prospective final start must be a UTC month boundary")
        if self.final_end != _add_months(self.final_start, 18):
            raise ValueError("prospective final era must span exactly 18 calendar months")

    @classmethod
    def from_verified_at(
        cls,
        *,
        development_cutoff: datetime,
        verified_at: datetime,
    ) -> "ProspectiveFinalWindow":
        """Derive the first month boundary strictly after verified qualification."""

        cutoff = _utc(development_cutoff, "development_cutoff")
        verification = _utc(verified_at, "verified_at")
        if verification < cutoff:
            raise ValueError("verification timestamp must not precede development cutoff")
        final_start = _strict_next_month_boundary(verification)
        return cls(
            development_cutoff=cutoff,
            verified_at=verification,
            bridge_start=cutoff,
            bridge_end=final_start,
            final_start=final_start,
            final_end=_add_months(final_start, 18),
        )


__all__ = ["ProspectiveFinalWindow"]
