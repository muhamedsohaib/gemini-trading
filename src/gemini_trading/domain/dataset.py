"""Retrieval, raw-evidence, canonical-manifest, and provenance contracts."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.time import require_utc
from gemini_trading.domain.timeframe import Timeframe

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


def _require_window(start_time: datetime, end_time: datetime) -> None:
    require_utc(start_time, "start_time")
    require_utc(end_time, "end_time")
    if end_time <= start_time:
        raise ValueError("end_time must be later than start_time")


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """One bounded `[start_time, end_time)` retrieval request."""

    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime

    def __post_init__(self) -> None:
        _require_window(self.start_time, self.end_time)


@dataclass(frozen=True, slots=True)
class RawPage:
    """One immutable provider response page and its retrieval metadata."""

    run_id: str
    sequence: int
    request_parameters: tuple[tuple[str, str], ...]
    retrieved_at: datetime
    server_time_snapshot: datetime
    http_status: int
    response_bytes: bytes
    response_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, "run_id")
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        require_utc(self.retrieved_at, "retrieved_at")
        require_utc(self.server_time_snapshot, "server_time_snapshot")
        if not 100 <= self.http_status <= 599:
            raise ValueError("http_status must be a valid HTTP status")
        _require_sha256(self.response_sha256, "response_sha256")


class RetrievalStatus(StrEnum):
    """Terminal retrieval-run status."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RetrievalManifest:
    """Immutable terminal record for one retrieval run."""

    schema_version: str
    run_id: str
    provider: str
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    server_time_snapshot: datetime | None
    page_hashes: tuple[str, ...]
    retry_count: int
    status: RetrievalStatus
    failure_type: str | None
    failure_message: str | None

    def __post_init__(self) -> None:
        _require_non_empty(self.schema_version, "schema_version")
        _require_non_empty(self.run_id, "run_id")
        _require_non_empty(self.provider, "provider")
        _require_window(self.start_time, self.end_time)
        if self.server_time_snapshot is not None:
            require_utc(self.server_time_snapshot, "server_time_snapshot")
        for page_hash in self.page_hashes:
            _require_sha256(page_hash, "page_hash")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Deterministic metadata derived only from canonical dataset content."""

    schema_version: str
    dataset_id: str
    provider: str
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    first_open_time: datetime
    last_open_time: datetime
    candle_count: int
    canonical_sha256: str

    def __post_init__(self) -> None:
        _require_non_empty(self.schema_version, "schema_version")
        _require_sha256(self.dataset_id, "dataset_id")
        _require_non_empty(self.provider, "provider")
        _require_window(self.start_time, self.end_time)
        require_utc(self.first_open_time, "first_open_time")
        require_utc(self.last_open_time, "last_open_time")
        if self.last_open_time < self.first_open_time:
            raise ValueError("last_open_time must not precede first_open_time")
        if self.candle_count < 1:
            raise ValueError("candle_count must be positive")
        _require_sha256(self.canonical_sha256, "canonical_sha256")


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    """Run-specific receipt linking raw evidence to canonical identity."""

    schema_version: str
    dataset_id: str
    run_id: str
    page_hashes: tuple[str, ...]
    retrieval_manifest_sha256: str
    linked: bool
    created_at: datetime

    def __post_init__(self) -> None:
        _require_non_empty(self.schema_version, "schema_version")
        _require_sha256(self.dataset_id, "dataset_id")
        _require_non_empty(self.run_id, "run_id")
        for page_hash in self.page_hashes:
            _require_sha256(page_hash, "page_hash")
        _require_sha256(self.retrieval_manifest_sha256, "retrieval_manifest_sha256")
        require_utc(self.created_at, "created_at")
