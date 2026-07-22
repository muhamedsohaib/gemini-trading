# Market Data Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, fail-closed Binance Spot candle ingestion core that preserves immutable raw evidence, emits content-addressed canonical JSONL datasets, supports offline replay and verification, and remains restricted to research and paper modes.

**Architecture:** Use a layered functional core with explicit domain contracts, provider and storage protocols, a synchronous Binance Spot public REST adapter, immutable local files, pure normalization and validation functions, deterministic dataset serialization, and orchestration that fails without emitting canonical output when retrieval or integrity checks are incomplete. Canonical content and retrieval provenance remain separate so independent equivalent retrievals produce the same dataset identity.

**Tech Stack:** Python 3.12, standard-library `dataclasses`, `Decimal`, `datetime`, `hashlib`, `json`, `pathlib`, `urllib`, `argparse`, `pytest`, `Hypothesis`, Ruff, Pyright strict mode, pre-commit, detect-secrets, pip-audit, GitHub Actions.

## Global Constraints

- Supported execution modes remain exactly `research` and `paper`; demo, live, production, and unknown modes must fail closed.
- Binance Spot public REST is the only network provider implemented in this milestone and must not accept credentials.
- One retrieval run handles one explicit symbol, one approved interval, and one bounded UTC window.
- Approved intervals are exactly `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, and `1w`.
- Canonical price and volume values use `Decimal`; floats are prohibited at the canonical boundary.
- Window semantics are `[start_time, end_time)`.
- One Binance server-time snapshot governs completion classification for the whole retrieval run.
- Incomplete candles may exist in raw evidence but may never enter canonical output.
- Transient failures receive bounded retries; exhaustion fails closed and writes no canonical dataset.
- Raw pages are stored byte-for-byte and are immutable.
- Canonical JSONL, dataset manifests, and dataset IDs are deterministic.
- Dataset identity is `sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)`.
- Retrieval-run metadata and page identities must not alter canonical JSONL or dataset identity.
- Generated `data/raw/` and `data/canonical/` content must remain untracked.
- Every task follows `docs/operations/market-data-core-step-verification.md` and appends fresh evidence to `reports/verification/market-data-core-progress.md`.
- No task begins while the prior task has an unresolved test, typing, lint, safety, diff-review, or evidence failure.

## File Map

- `src/gemini_trading/domain/instrument.py`: immutable instrument identity and normalization.
- `src/gemini_trading/domain/timeframe.py`: approved intervals and exact durations.
- `src/gemini_trading/domain/candle.py`: immutable canonical candle contract.
- `src/gemini_trading/domain/dataset.py`: retrieval requests, raw pages, manifests, and provenance contracts.
- `src/gemini_trading/data/errors.py`: market-data error taxonomy and safe retry metadata.
- `src/gemini_trading/data/validation/candles.py`: candle geometry, ordering, duplicate, continuity, completion, and window checks.
- `src/gemini_trading/data/normalization/binance_klines.py`: exact Binance kline parsing into canonical candles.
- `src/gemini_trading/data/providers/base.py`: provider page and provider protocol.
- `src/gemini_trading/data/providers/http.py`: injectable standard-library HTTP transport.
- `src/gemini_trading/data/providers/binance_spot.py`: Binance server-time and bounded kline requests plus error classification.
- `src/gemini_trading/data/storage/base.py`: raw and canonical storage protocols.
- `src/gemini_trading/data/storage/local_immutable.py`: immutable local file implementation and conflict detection.
- `src/gemini_trading/data/datasets/canonical_writer.py`: deterministic JSONL, dataset identity, manifest, and provenance generation.
- `src/gemini_trading/data/ingestion/retry.py`: bounded retry policy.
- `src/gemini_trading/data/ingestion/service.py`: online ingestion orchestration.
- `src/gemini_trading/data/ingestion/replay.py`: offline canonical reconstruction from raw pages.
- `src/gemini_trading/data/verification/service.py`: end-to-end hash, linkage, continuity, and identity verification.
- `src/gemini_trading/cli/main.py`: CLI entry point.
- `src/gemini_trading/cli/market_data.py`: `ingest`, `replay`, and `verify` commands.
- `tests/fixtures/binance_spot/`: sanitized public response fixtures.
- `tests/unit/domain/`, `tests/unit/data/`, `tests/property/`, `tests/integration/`, `tests/acceptance/`: deterministic verification layers.
- `tests/live/test_binance_spot_smoke.py`: explicitly opt-in public API smoke test.
- `reports/verification/market-data-core-progress.md`: append-only task evidence.
- `reports/verification/market-data-core-final.md`: final exact-head evidence.

---

### Task 1: Establish the Verification Ledger and Baseline

**Files:**
- Create: `reports/verification/market-data-core-progress.md`
- Modify: `.gitignore`
- Modify: `src/gemini_trading/safety/repository_policy.py`
- Test: `tests/unit/safety/test_repository_policy.py`

**Interfaces:**
- Consumes: existing `validate_tracked_paths(paths: list[str]) -> None`.
- Produces: a committed verification ledger and repository policy that rejects generated market-data directories if tracked.

- [ ] **Step 1: Write the failing repository-policy tests**

Append these tests to `tests/unit/safety/test_repository_policy.py`:

```python
import pytest

from gemini_trading.safety.repository_policy import RepositoryPolicyError, validate_tracked_paths


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/binance_spot/run/page-000001.json",
        "data/canonical/dataset/candles.jsonl",
    ],
)
def test_generated_market_data_must_not_be_tracked(path: str) -> None:
    with pytest.raises(RepositoryPolicyError, match="generated market data"):
        validate_tracked_paths([path])
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
uv run pytest tests/unit/safety/test_repository_policy.py -q
```

Expected: the two new parameter cases fail because generated market-data paths are not yet prohibited.

- [ ] **Step 3: Extend the tracked-file policy**

In `src/gemini_trading/safety/repository_policy.py`, add this constant and check inside `validate_tracked_paths`:

```python
GENERATED_MARKET_DATA_PREFIXES = ("data/raw/", "data/canonical/")


def _reject_generated_market_data(path: str) -> None:
    normalized = path.replace("\\", "/")
    if normalized.startswith(GENERATED_MARKET_DATA_PREFIXES):
        raise RepositoryPolicyError(f"generated market data must not be tracked: {path}")
```

Call `_reject_generated_market_data(path)` for every tracked path before returning successfully.

Append to `.gitignore`:

```gitignore

# Generated market-data evidence and canonical datasets
data/raw/
data/canonical/
```

Create `reports/verification/market-data-core-progress.md` with:

```markdown
# Market Data Core Progress Verification

This append-only log records fresh task and checkpoint evidence for GitHub issue #8.

## Rules

- Record the tested commit or working-tree identity.
- Record exact commands and observed outcomes.
- Record failures and remediation.
- Do not include credentials, authorization headers, or unrestricted API responses.
```

- [ ] **Step 4: Run the complete Task 1 gate**

Run:

```powershell
uv run pytest tests/unit/safety/test_repository_policy.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/safety tests/unit/safety
uv run ruff check src/gemini_trading/safety tests/unit/safety
uv run pyright
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
git diff --check
git status --short
```

Expected: tests pass, Ruff passes, Pyright reports zero errors, policy prints `PASS`, `git diff --check` is silent, and status shows only intended Task 1 files.

- [ ] **Step 5: Append Task 1 evidence and commit**

Append the exact observed commands, results, failures, remediation, and `git diff --stat` to the progress log. Then run:

```powershell
git add .gitignore src/gemini_trading/safety/repository_policy.py tests/unit/safety/test_repository_policy.py reports/verification/market-data-core-progress.md
git commit -m "chore: establish market data verification ledger"
```

---

### Task 2: Define Immutable Domain Contracts and Error Taxonomy

**Files:**
- Create: `src/gemini_trading/domain/__init__.py`
- Create: `src/gemini_trading/domain/instrument.py`
- Create: `src/gemini_trading/domain/timeframe.py`
- Create: `src/gemini_trading/domain/candle.py`
- Create: `src/gemini_trading/domain/dataset.py`
- Create: `src/gemini_trading/data/__init__.py`
- Create: `src/gemini_trading/data/errors.py`
- Test: `tests/unit/domain/test_instrument.py`
- Test: `tests/unit/domain/test_timeframe.py`
- Test: `tests/unit/domain/test_candle.py`
- Test: `tests/unit/domain/test_dataset.py`
- Test: `tests/unit/data/test_errors.py`

**Interfaces:**
- Produces:
  - `Instrument(symbol: str, base_asset: str, quote_asset: str)`.
  - `Timeframe` enum and `duration: timedelta`.
  - `Candle(instrument, timeframe, open_time, close_time, open, high, low, close, volume, completed, source_provider)`.
  - `RetrievalRequest(instrument, timeframe, start_time, end_time)`.
  - `RawPage`, `RetrievalManifest`, `DatasetManifest`, `DatasetProvenance`.
  - `MarketDataError` subclasses used by every later task.

- [ ] **Step 1: Write failing domain tests**

Create focused tests proving uppercase normalization, symbol consistency, curated intervals, UTC-only timestamps, immutable dataclasses, finite decimals, `[start,end)` validation, and safe error metadata. Use these exact assertions:

```python
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def test_instrument_normalizes_and_requires_explicit_consistency() -> None:
    instrument = Instrument(symbol="ethusdt", base_asset="eth", quote_asset="usdt")
    assert instrument.symbol == "ETHUSDT"
    assert instrument.base_asset == "ETH"
    assert instrument.quote_asset == "USDT"
    with pytest.raises(ValueError, match="must equal base_asset \+ quote_asset"):
        Instrument(symbol="BTCUSDT", base_asset="ETH", quote_asset="USDT")


def test_timeframe_set_is_curated() -> None:
    assert {item.value for item in Timeframe} == {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}
    assert Timeframe.H4.duration == timedelta(hours=4)


def test_retrieval_request_rejects_naive_or_reversed_window() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    with pytest.raises(ValueError, match="UTC-aware"):
        RetrievalRequest(instrument, Timeframe.H4, datetime(2025, 1, 1), datetime(2025, 1, 2))
    with pytest.raises(ValueError, match="later than"):
        RetrievalRequest(
            instrument,
            Timeframe.H4,
            datetime(2025, 1, 2, tzinfo=UTC),
            datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_candle_is_immutable_and_rejects_non_finite_decimal() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    candle = Candle(
        instrument=instrument,
        timeframe=Timeframe.H4,
        open_time=datetime(2025, 1, 1, tzinfo=UTC),
        close_time=datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("90.00"),
        close=Decimal("105.00"),
        volume=Decimal("12.5000"),
        completed=True,
        source_provider="binance_spot",
    )
    with pytest.raises(FrozenInstanceError):
        candle.close = Decimal("1")  # type: ignore[misc]
    with pytest.raises(ValueError, match="finite"):
        Candle(**{**candle.__dict__, "close": Decimal("NaN")})  # type: ignore[arg-type]
```

Use `dataclasses.replace(candle, close=Decimal("NaN"))` instead of `__dict__` if slots are enabled.

- [ ] **Step 2: Run the focused tests and confirm import failures**

Run:

```powershell
uv run pytest tests/unit/domain tests/unit/data/test_errors.py -q
```

Expected: collection fails because the new modules do not exist.

- [ ] **Step 3: Implement the contracts**

Implement frozen, slotted dataclasses. Use this UTC helper in `src/gemini_trading/domain/dataset.py` and `candle.py`:

```python
from datetime import UTC, datetime


def require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC-aware")
```

Define `Timeframe` exactly:

```python
from datetime import timedelta
from enum import StrEnum


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def duration(self) -> timedelta:
        return {
            Timeframe.M1: timedelta(minutes=1),
            Timeframe.M5: timedelta(minutes=5),
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.D1: timedelta(days=1),
            Timeframe.W1: timedelta(days=7),
        }[self]
```

Define the error hierarchy in `data/errors.py` with no raw response body fields:

```python
class MarketDataError(RuntimeError):
    pass


class ProviderConnectionError(MarketDataError):
    pass


class ProviderRateLimitError(MarketDataError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderResponseError(MarketDataError):
    def __init__(self, message: str, status_code: int, retryable: bool) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ProviderSchemaError(MarketDataError):
    pass


class InvalidRetrievalWindowError(MarketDataError):
    pass


class CandleValidationError(MarketDataError):
    pass


class DuplicateCandleError(CandleValidationError):
    pass


class OutOfOrderCandleError(CandleValidationError):
    pass


class CandleGapError(CandleValidationError):
    pass


class IncompleteWindowError(CandleValidationError):
    pass


class RawStorageConflictError(MarketDataError):
    pass


class CanonicalDatasetWriteError(MarketDataError):
    pass
```

- [ ] **Step 4: Run the complete Task 2 gate**

Run:

```powershell
uv run pytest tests/unit/domain tests/unit/data/test_errors.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/domain src/gemini_trading/data/errors.py tests/unit/domain tests/unit/data/test_errors.py
uv run ruff check src/gemini_trading/domain src/gemini_trading/data/errors.py tests/unit/domain tests/unit/data/test_errors.py
uv run pyright
git diff --check
git status --short
```

Expected: all selected tests pass, Ruff passes, Pyright reports zero errors, diff check is silent, and only Task 2 files plus the appended verification log are modified.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/domain src/gemini_trading/data tests/unit/domain tests/unit/data/test_errors.py reports/verification/market-data-core-progress.md
git commit -m "feat: define market data domain contracts"
```

---

### Task 3: Implement Canonical Candle and Window Validation

**Files:**
- Create: `src/gemini_trading/data/validation/__init__.py`
- Create: `src/gemini_trading/data/validation/candles.py`
- Test: `tests/unit/data/validation/test_candles.py`
- Test: `tests/property/test_candle_validation.py`

**Interfaces:**
- Consumes: `Candle`, `RetrievalRequest`.
- Produces:
  - `validate_candle(candle: Candle) -> None`.
  - `validate_candle_sequence(candles: Sequence[Candle], request: RetrievalRequest) -> None`.
  - `completed_candles(candles: Sequence[Candle], server_time: datetime) -> tuple[Candle, ...]`.

- [ ] **Step 1: Write focused and property tests**

Tests must prove positive prices, non-negative volume, OHLC geometry, strict order, duplicate rejection, exact interval continuity, request-window containment, at least one completed candle, and incomplete-candle exclusion. Include:

```python
def test_duplicate_open_time_fails_closed(two_valid_candles: tuple[Candle, Candle], request: RetrievalRequest) -> None:
    first, second = two_valid_candles
    duplicate = replace(second, open_time=first.open_time)
    with pytest.raises(DuplicateCandleError):
        validate_candle_sequence((first, duplicate), request)


def test_internal_gap_fails_closed(two_valid_candles: tuple[Candle, Candle], request: RetrievalRequest) -> None:
    first, second = two_valid_candles
    gapped = replace(
        second,
        open_time=second.open_time + request.timeframe.duration,
        close_time=second.close_time + request.timeframe.duration,
    )
    with pytest.raises(CandleGapError):
        validate_candle_sequence((first, gapped), request)


def test_incomplete_candle_is_excluded_by_single_server_snapshot(candle: Candle) -> None:
    server_time = candle.close_time
    assert completed_candles((candle,), server_time) == ()
```

Property tests must generate finite positive decimals and prove that changing one valid sequence into a duplicate, inversion, or gap is always rejected.

- [ ] **Step 2: Run tests and confirm module-not-found failure**

```powershell
uv run pytest tests/unit/data/validation tests/property/test_candle_validation.py -q
```

Expected: collection fails because validation modules are absent.

- [ ] **Step 3: Implement pure validation**

The sequence validator must check in this order: non-empty, per-candle geometry, instrument/timeframe equality, request-window containment, completion, duplicate, ordering, and exact continuity. Use:

```python
def completed_candles(candles: Sequence[Candle], server_time: datetime) -> tuple[Candle, ...]:
    require_utc(server_time, "server_time")
    return tuple(replace(candle, completed=True) for candle in candles if candle.close_time < server_time)
```

Provider-normalized candles enter with their observed completion flag set to `False`; this function is the only place that promotes them to completed canonical candidates.

- [ ] **Step 4: Run the complete Task 3 gate**

```powershell
uv run pytest tests/unit/data/validation tests/property/test_candle_validation.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/validation tests/unit/data/validation tests/property/test_candle_validation.py
uv run ruff check src/gemini_trading/data/validation tests/unit/data/validation tests/property/test_candle_validation.py
uv run pyright
git diff --check
git diff --stat
```

Expected: all selected tests pass, Pyright has zero errors, and no provider, storage, execution, or strategy files changed.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/data/validation tests/unit/data/validation tests/property/test_candle_validation.py reports/verification/market-data-core-progress.md
git commit -m "feat: validate canonical candle sequences"
```

---

### Task 4: Normalize Binance Kline Payloads Without Precision Loss

**Files:**
- Create: `src/gemini_trading/data/normalization/__init__.py`
- Create: `src/gemini_trading/data/normalization/binance_klines.py`
- Create: `tests/fixtures/binance_spot/klines_valid_single_page.json`
- Create: `tests/fixtures/binance_spot/klines_malformed_shape.json`
- Create: `tests/fixtures/binance_spot/klines_invalid_decimal.json`
- Test: `tests/unit/data/normalization/test_binance_klines.py`
- Test: `tests/property/test_binance_normalization.py`

**Interfaces:**
- Consumes: exact response `bytes`, `Instrument`, `Timeframe`.
- Produces: `normalize_binance_klines(payload: bytes, instrument: Instrument, timeframe: Timeframe) -> tuple[Candle, ...]`.

- [ ] **Step 1: Commit sanitized public fixtures and failing tests**

The valid fixture must contain a small fixed historical public response with all Binance kline array fields. Tests must assert exact decimal strings survive:

```python
def test_normalization_preserves_decimal_exponents(valid_payload: bytes, instrument: Instrument) -> None:
    candles = normalize_binance_klines(valid_payload, instrument, Timeframe.H4)
    assert format(candles[0].open, "f") == "3400.12000000"
    assert format(candles[0].volume, "f") == "12.50000000"
    assert candles[0].completed is False
```

Malformed row length, non-list root, invalid UTF-8, invalid JSON, invalid milliseconds, and non-finite decimal values must raise `ProviderSchemaError` without including the full payload in the message.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/data/normalization tests/property/test_binance_normalization.py -q
```

Expected: import failure because the normalizer does not exist.

- [ ] **Step 3: Implement strict parsing**

Parse with `json.loads(payload.decode("utf-8"))`; require a list root and rows with at least 7 fields. Use indices `0,1,2,3,4,5,6` for open time, OHLC, volume, and close time. Convert milliseconds using:

```python
def _utc_from_milliseconds(value: object, field_name: str) -> datetime:
    if not isinstance(value, int):
        raise ProviderSchemaError(f"{field_name} must be integer milliseconds")
    return datetime.fromtimestamp(value / 1000, tz=UTC)
```

Convert numeric strings using `Decimal(str(value))`, reject non-finite values, and never convert through `float`.

- [ ] **Step 4: Run the complete Task 4 gate**

```powershell
uv run pytest tests/unit/data/normalization tests/property/test_binance_normalization.py tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/normalization tests/unit/data/normalization tests/property/test_binance_normalization.py
uv run ruff check src/gemini_trading/data/normalization tests/unit/data/normalization tests/property/test_binance_normalization.py
uv run pyright
uv run detect-secrets scan --baseline .secrets.baseline tests/fixtures/binance_spot
git diff --check
```

Expected: tests pass, secret scan reports no new secrets, and fixtures contain public market data only.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/data/normalization tests/fixtures/binance_spot tests/unit/data/normalization tests/property/test_binance_normalization.py reports/verification/market-data-core-progress.md
git commit -m "feat: normalize Binance kline payloads"
```

---

### Task 5: Build the Provider Protocol and Binance Spot REST Adapter

**Files:**
- Create: `src/gemini_trading/data/providers/__init__.py`
- Create: `src/gemini_trading/data/providers/base.py`
- Create: `src/gemini_trading/data/providers/http.py`
- Create: `src/gemini_trading/data/providers/binance_spot.py`
- Test: `tests/unit/data/providers/test_http.py`
- Test: `tests/unit/data/providers/test_binance_spot.py`
- Test: `tests/integration/test_binance_provider_contract.py`

**Interfaces:**
- Produces:
  - `HttpResponse(status_code: int, headers: Mapping[str, str], body: bytes)`.
  - `HttpTransport.get(url: str, timeout_seconds: float) -> HttpResponse`.
  - `ProviderPage(request_url: str, request_parameters: Mapping[str, str], response: HttpResponse, retrieved_at: datetime)`.
  - `MarketDataProvider.fetch_server_time() -> datetime`.
  - `MarketDataProvider.fetch_klines(request: RetrievalRequest, cursor: datetime, limit: int = 1000) -> ProviderPage`.

- [ ] **Step 1: Write transport and adapter tests with an injected fake transport**

Tests must prove:

- base URL is exactly `https://api.binance.com` by default;
- server time uses `/api/v3/time`;
- klines use `/api/v3/klines` with `symbol`, `interval`, `startTime`, `endTime`, and `limit=1000`;
- cursor and end are integer UTC milliseconds;
- no credential or signature parameter exists;
- body bytes are returned unchanged;
- 429 becomes `ProviderRateLimitError` and parses numeric `Retry-After`;
- 500-599 becomes retryable `ProviderResponseError`;
- other 400 errors become non-retryable `ProviderResponseError`;
- network exceptions become `ProviderConnectionError`;
- malformed server-time JSON becomes `ProviderSchemaError`.

- [ ] **Step 2: Run tests and confirm import failure**

```powershell
uv run pytest tests/unit/data/providers tests/integration/test_binance_provider_contract.py -q
```

Expected: collection fails because provider modules do not exist.

- [ ] **Step 3: Implement the standard-library transport and adapter**

`UrllibTransport.get` must use `urllib.request.Request(url, method="GET")` and return body bytes and lowercase-safe headers. Catch `HTTPError` and return its status/body/headers so the adapter classifies it; catch `URLError`, `TimeoutError`, and `OSError` and raise `ProviderConnectionError("Binance public REST connection failed")` without embedding the URL query or response body.

Build query strings with `urllib.parse.urlencode`. Convert UTC datetimes with:

```python
def _milliseconds(value: datetime) -> int:
    require_utc(value, "timestamp")
    return int(value.timestamp() * 1000)
```

The adapter must expose no API-key constructor argument and must not read environment credentials.

- [ ] **Step 4: Run the complete Task 5 gate**

```powershell
uv run pytest tests/unit/data/providers tests/integration/test_binance_provider_contract.py tests/unit/data/normalization tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/providers tests/unit/data/providers tests/integration/test_binance_provider_contract.py
uv run ruff check src/gemini_trading/data/providers tests/unit/data/providers tests/integration/test_binance_provider_contract.py
uv run pyright
Select-String -Path src/gemini_trading/data/providers/*.py -Pattern 'api.key|secret|signature|authorization' -CaseSensitive:$false
git diff --check
```

Expected: tests and static checks pass; `Select-String` produces no credential-bearing implementation match.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/data/providers tests/unit/data/providers tests/integration/test_binance_provider_contract.py reports/verification/market-data-core-progress.md
git commit -m "feat: add Binance Spot market data provider"
```

---

### Task 6: Implement Immutable Raw and Canonical Local Storage

**Files:**
- Create: `src/gemini_trading/data/storage/__init__.py`
- Create: `src/gemini_trading/data/storage/base.py`
- Create: `src/gemini_trading/data/storage/local_immutable.py`
- Test: `tests/unit/data/storage/test_local_immutable.py`
- Test: `tests/property/test_immutable_storage.py`

**Interfaces:**
- Produces:
  - `RawStore.write_page(page: RawPage) -> Path`.
  - `RawStore.write_retrieval_manifest(manifest: RetrievalManifest) -> Path`.
  - `RawStore.read_run(run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]`.
  - `CanonicalStore.write_dataset(dataset_id: str, jsonl_bytes: bytes, manifest_bytes: bytes) -> tuple[Path, Path]`.
  - `CanonicalStore.write_provenance(dataset_id: str, run_id: str, receipt_bytes: bytes) -> Path`.
  - `write_immutable(path: Path, content: bytes) -> Path`.

- [ ] **Step 1: Write failing immutability tests**

Tests must prove first write succeeds, identical repeat write is idempotent, different bytes at the same identity raise `RawStorageConflictError`, directory traversal run IDs are rejected, page files use six-digit sequence names, and no partial temporary file remains after a failed write.

```python
def test_conflicting_existing_bytes_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "value.json"
    write_immutable(path, b"one")
    with pytest.raises(RawStorageConflictError):
        write_immutable(path, b"two")
    assert path.read_bytes() == b"one"
```

Property tests must prove arbitrary byte strings are either stored exactly or rejected without changing prior content.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/data/storage tests/property/test_immutable_storage.py -q
```

Expected: import failure because storage modules do not exist.

- [ ] **Step 3: Implement atomic immutable writes**

Use exclusive creation:

```python
def write_immutable(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if path.read_bytes() != content:
            raise RawStorageConflictError(f"immutable path conflicts: {path}") from None
    return path
```

Validate identity segments with a strict regex such as `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`; reject separators, `..`, and empty values before path construction.

- [ ] **Step 4: Run the complete Task 6 gate**

```powershell
uv run pytest tests/unit/data/storage tests/property/test_immutable_storage.py tests/unit/data/normalization tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/storage tests/unit/data/storage tests/property/test_immutable_storage.py
uv run ruff check src/gemini_trading/data/storage tests/unit/data/storage tests/property/test_immutable_storage.py
uv run pyright
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: generated data untracked')"
git diff --check
```

Expected: all checks pass and no generated `data/` content appears in `git status --short`.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/data/storage tests/unit/data/storage tests/property/test_immutable_storage.py reports/verification/market-data-core-progress.md
git commit -m "feat: add immutable local market data storage"
```

---

### Task 7: Produce Deterministic Canonical JSONL, Identity, Manifest, and Provenance

**Files:**
- Create: `src/gemini_trading/data/datasets/__init__.py`
- Create: `src/gemini_trading/data/datasets/canonical_writer.py`
- Test: `tests/unit/data/datasets/test_canonical_writer.py`
- Test: `tests/property/test_dataset_identity.py`

**Interfaces:**
- Produces:
  - `serialize_candles(candles: Sequence[Candle]) -> bytes`.
  - `dataset_id(schema_version: str, canonical_bytes: bytes) -> str`.
  - `build_dataset_manifest(...) -> DatasetManifest`.
  - `serialize_dataset_manifest(manifest: DatasetManifest) -> bytes`.
  - `build_provenance(...) -> DatasetProvenance`.
  - `serialize_provenance(receipt: DatasetProvenance) -> bytes`.

- [ ] **Step 1: Write determinism and provenance-isolation tests**

Tests must assert:

```python
def test_dataset_identity_formula(canonical_bytes: bytes) -> None:
    expected = hashlib.sha256(b"market-candle-v1\n" + canonical_bytes).hexdigest()
    assert dataset_id("market-candle-v1", canonical_bytes) == expected


def test_retrieval_metadata_does_not_change_canonical_identity(candles: tuple[Candle, ...]) -> None:
    canonical = serialize_candles(candles)
    first = build_provenance(dataset_id("market-candle-v1", canonical), "run-a", ("hash-a",), "manifest-a", fixed_time)
    second = build_provenance(dataset_id("market-candle-v1", canonical), "run-b", ("hash-b",), "manifest-b", fixed_time)
    assert first.dataset_id == second.dataset_id
    assert serialize_provenance(first) != serialize_provenance(second)
```

Also assert stable field order, one trailing newline per row, `Z` UTC timestamps with milliseconds, exact decimal strings including trailing zeros, deterministic manifest bytes, and SHA-256 lowercase hex length 64.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/data/datasets tests/property/test_dataset_identity.py -q
```

Expected: import failure because dataset writer does not exist.

- [ ] **Step 3: Implement canonical serialization**

Use explicit insertion-ordered dict construction and compact JSON:

```python
def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
```

For JSONL, concatenate one `_json_bytes` call per candle. Use `format(decimal_value, "f")`. Use `value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")`. Dataset manifests must exclude run ID, page hashes, and creation time. Provenance receipts must include them.

- [ ] **Step 4: Run the complete Task 7 gate**

```powershell
uv run pytest tests/unit/data/datasets tests/property/test_dataset_identity.py tests/unit/data/storage tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/datasets tests/unit/data/datasets tests/property/test_dataset_identity.py
uv run ruff check src/gemini_trading/data/datasets tests/unit/data/datasets tests/property/test_dataset_identity.py
uv run pyright
git diff --check
```

Expected: deterministic tests pass repeatedly. Run the identity test twice and confirm the same expected hash both times.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add src/gemini_trading/data/datasets tests/unit/data/datasets tests/property/test_dataset_identity.py reports/verification/market-data-core-progress.md
git commit -m "feat: create content addressed candle datasets"
```

---

### Task 8: Orchestrate Bounded Retrieval, Retries, Pagination, and Fail-Closed Ingestion

**Files:**
- Create: `src/gemini_trading/data/ingestion/__init__.py`
- Create: `src/gemini_trading/data/ingestion/retry.py`
- Create: `src/gemini_trading/data/ingestion/service.py`
- Test: `tests/unit/data/ingestion/test_retry.py`
- Test: `tests/unit/data/ingestion/test_service.py`
- Create: `tests/fixtures/binance_spot/klines_valid_two_pages_page_1.json`
- Create: `tests/fixtures/binance_spot/klines_valid_two_pages_page_2.json`
- Create: `tests/fixtures/binance_spot/klines_internal_gap.json`

**Interfaces:**
- Produces:
  - `RetryPolicy(max_attempts: int = 3, base_delay_seconds: float = 0.5)`.
  - `IngestionResult(run_id: str, dataset_id: str, raw_page_count: int, candle_count: int, paths: Mapping[str, Path])`.
  - `IngestionService.ingest(request: RetrievalRequest) -> IngestionResult`.

- [ ] **Step 1: Write failing orchestration tests with deterministic fakes**

Inject provider, raw store, canonical store, clock, sleep, and run-ID factory. Tests must prove:

- exactly one server-time call per run;
- page is persisted before normalization or validation;
- cursor advances by the last open time plus interval duration;
- cursor never repeats or exceeds end;
- no-progress empty page fails with `IncompleteWindowError`;
- transient error then success retries with observed delay;
- retry exhaustion writes a failed retrieval manifest and no canonical output;
- malformed page writes raw evidence then fails;
- incomplete final candle is excluded;
- internal gap emits no canonical dataset;
- zero completed candles emits no canonical dataset;
- successful ingestion writes deterministic manifest and one provenance receipt.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/data/ingestion -q
```

Expected: collection fails because ingestion modules do not exist.

- [ ] **Step 3: Implement retry policy**

`RetryPolicy.delay_for(attempt_number, error)` must return `max(base_delay_seconds * 2 ** (attempt_number - 1), retry_after)` for rate limits and exponential delay otherwise. Attempts are numbered from 1. Reject `max_attempts < 1` and negative base delay.

- [ ] **Step 4: Implement ingestion service in strict order**

The implementation sequence must be:

```text
create run identity
capture server time with bounded retry
fetch page with bounded retry
construct RawPage
persist RawPage
normalize page
append normalized candles
validate cursor progress
continue until provider returns fewer than limit or cursor reaches end
classify completed candles using the one server snapshot
validate canonical sequence
serialize canonical bytes
write canonical bytes and deterministic manifest
hash retrieval manifest
write provenance receipt
return result
```

On any exception after run creation, write a failed retrieval manifest containing safe error class and message, then re-raise. Never write canonical output before all page retrieval and validation succeeds.

- [ ] **Step 5: Run the complete Task 8 gate and first checkpoint**

```powershell
uv run pytest tests/unit/data/ingestion tests/unit/data tests/property tests/regression tests/unit/safety -q
uv run pre-commit run --all-files
uv run pyright
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
$env:GEMINI_TRADING_MODE = 'live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $code=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($code -eq 0) { throw 'live mode was accepted' } else { Write-Host 'PASS: live mode rejected' }
git diff --check
git status --short
```

Expected: all deterministic tests and hooks pass, build succeeds, audit finds no known third-party vulnerabilities, policy passes, live mode exits non-zero, and only intended source/test/report files are present.

- [ ] **Step 6: Append task and checkpoint evidence, commit, and push**

```powershell
git add src/gemini_trading/data/ingestion tests/unit/data/ingestion tests/fixtures/binance_spot reports/verification/market-data-core-progress.md
git commit -m "feat: orchestrate fail closed market data ingestion"
git push
```

Record the resulting GitHub commit SHA. Do not begin Task 9 until GitHub `quality` and `gitleaks` pass on that SHA.

---

### Task 9: Implement Offline Replay and Independent Verification

**Files:**
- Create: `src/gemini_trading/data/ingestion/replay.py`
- Create: `src/gemini_trading/data/verification/__init__.py`
- Create: `src/gemini_trading/data/verification/service.py`
- Test: `tests/unit/data/ingestion/test_replay.py`
- Test: `tests/unit/data/verification/test_service.py`
- Test: `tests/integration/test_replay_without_network.py`

**Interfaces:**
- Produces:
  - `ReplayService.replay(run_id: str) -> IngestionResult` with no provider dependency.
  - `VerificationResult(dataset_id: str, run_id: str, candle_count: int, checks: tuple[str, ...])`.
  - `VerificationService.verify(dataset_id: str, run_id: str) -> VerificationResult`.

- [ ] **Step 1: Write replay and tamper-detection tests**

Tests must prove replay has no provider constructor argument and performs no network call, reconstructs identical JSONL/manifest/dataset ID, creates a separate provenance receipt for each equivalent run, and fails on altered page bytes, altered page hash, altered retrieval manifest, altered JSONL, altered dataset manifest, wrong dataset directory name, wrong run linkage, duplicate candles, gaps, or incomplete candles.

```python
def test_replay_service_has_no_provider_dependency() -> None:
    parameters = inspect.signature(ReplayService).parameters
    assert "provider" not in parameters


def test_replay_reproduces_identical_identity(first_result: IngestionResult, replay_service: ReplayService) -> None:
    replayed = replay_service.replay(first_result.run_id)
    assert replayed.dataset_id == first_result.dataset_id
    assert replayed.paths["candles"].read_bytes() == first_result.paths["candles"].read_bytes()
```

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py -q
```

Expected: import failure because replay and verification services are absent.

- [ ] **Step 3: Implement replay from raw evidence only**

Replay must read and hash-verify the retrieval manifest and every listed page before normalization. It must use the stored server-time snapshot and request. It must call the same normalization, completion, sequence validation, serialization, manifest, and provenance functions as online ingestion.

- [ ] **Step 4: Implement verification as recomputation, not trust**

Verification must recompute raw page hashes, retrieval-manifest hash, canonical JSONL hash, dataset ID, deterministic dataset-manifest bytes, provenance linkage, parsed candle continuity, and completion state. It returns named passed checks only after every recomputation succeeds.

- [ ] **Step 5: Run the complete Task 9 gate**

```powershell
uv run pytest tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py tests/unit/data tests/property tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py
uv run ruff check src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py
uv run pyright
git diff --check
```

Expected: replay and tamper tests pass; no network fixture or provider is used by replay.

- [ ] **Step 6: Append evidence and commit**

```powershell
git add src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py reports/verification/market-data-core-progress.md
git commit -m "feat: replay and verify canonical market data"
```

---

### Task 10: Add the Safe Market-Data CLI

**Files:**
- Create: `src/gemini_trading/cli/__init__.py`
- Create: `src/gemini_trading/cli/main.py`
- Create: `src/gemini_trading/cli/market_data.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/cli/test_market_data.py`
- Test: `tests/acceptance/test_market_data_cli.py`

**Interfaces:**
- Produces executable `gemini-trading` with:
  - `market-data ingest`.
  - `market-data replay`.
  - `market-data verify`.

- [ ] **Step 1: Write failing CLI tests**

Use injected service factories and captured stdout/stderr. Tests must assert required explicit `--symbol`, `--base-asset`, `--quote-asset`, `--interval`, `--start`, `--end`, `--output-root`; supported interval rejection before network access; safe JSON summary output; non-zero exit on ingestion/replay/verification failure; no raw body, environment dump, authorization string, or traceback in normal user-facing errors.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
uv run pytest tests/unit/cli tests/acceptance/test_market_data_cli.py -q
```

Expected: import or entry-point failure because CLI files and script entry do not exist.

- [ ] **Step 3: Add the console script and commands**

Add to `pyproject.toml`:

```toml
[project.scripts]
gemini-trading = "gemini_trading.cli.main:main"
```

`main(argv: Sequence[str] | None = None) -> int` must parse subcommands, call `load_runtime_policy()` before any ingestion, accept only research or paper mode, print compact safe JSON summaries, and catch `MarketDataError` to print `{"status":"failed","error_type":"...","message":"..."}` to stderr with exit code 2.

- [ ] **Step 4: Run the complete Task 10 gate**

```powershell
uv sync --all-groups --frozen
uv run pytest tests/unit/cli tests/acceptance/test_market_data_cli.py tests/unit/data tests/property tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/cli tests/unit/cli tests/acceptance/test_market_data_cli.py
uv run ruff check src/gemini_trading/cli tests/unit/cli tests/acceptance/test_market_data_cli.py
uv run pyright
uv run gemini-trading --help
uv run gemini-trading market-data --help
git diff --check
```

Expected: tests pass, entry point resolves, help lists exactly `ingest`, `replay`, and `verify`, and live mode remains rejected.

- [ ] **Step 5: Append evidence and commit**

```powershell
git add pyproject.toml uv.lock src/gemini_trading/cli tests/unit/cli tests/acceptance/test_market_data_cli.py reports/verification/market-data-core-progress.md
git commit -m "feat: expose safe market data CLI"
```

---

### Task 11: Prove the End-to-End ETHUSDT 4h Acceptance Case and Generic Boundaries

**Files:**
- Create: `tests/fixtures/binance_spot/ethusdt_4h_acceptance_page_1.json`
- Create: `tests/fixtures/binance_spot/ethusdt_4h_acceptance_page_2.json`
- Create: `tests/acceptance/test_market_data_ingestion.py`
- Create: `tests/integration/test_storage_adapter_equivalence.py`
- Create: `tests/live/test_binance_spot_smoke.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: complete online-ingestion, replay, verification, and storage interfaces.
- Produces: deterministic acceptance evidence and an opt-in live public API smoke test.

- [ ] **Step 1: Write the acceptance test before adding fixtures**

The deterministic acceptance test must use a fixed `ETHUSDT`, `4h`, UTC window and assert:

- all raw pages exist and match fixture bytes;
- retrieval manifest status is completed;
- canonical candles are ordered, gap-free, and completed;
- exact decimals retain scale;
- dataset ID matches a fixed expected SHA-256 literal calculated from committed fixture output;
- replay produces identical JSONL and deterministic manifest bytes;
- verification returns every named check;
- a second run with different run ID and retrieval timestamps produces the same dataset ID and separate provenance receipt;
- alternate in-memory and local storage adapters produce identical canonical bytes;
- no ETH-specific condition exists outside test fixtures or command inputs.

- [ ] **Step 2: Run the acceptance test and confirm fixture failure**

```powershell
uv run pytest tests/acceptance/test_market_data_ingestion.py tests/integration/test_storage_adapter_equivalence.py -q
```

Expected: failure because the acceptance fixtures and fixed expected identity are not yet present.

- [ ] **Step 3: Add sanitized fixtures and fixed expected identity**

Commit only the bounded public response bytes required by the test. Generate the expected canonical JSONL once through the reviewed serializer, inspect it manually, calculate its hash independently with PowerShell, and hard-code the expected 64-character hash in the test:

```powershell
$bytes = [System.IO.File]::ReadAllBytes($canonicalPath)
$prefix = [System.Text.Encoding]::UTF8.GetBytes("market-candle-v1`n")
$combined = New-Object byte[] ($prefix.Length + $bytes.Length)
[Array]::Copy($prefix, 0, $combined, 0, $prefix.Length)
[Array]::Copy($bytes, 0, $combined, $prefix.Length, $bytes.Length)
$hash = [System.Security.Cryptography.SHA256]::HashData($combined)
[Convert]::ToHexString($hash).ToLowerInvariant()
```

The independently calculated value must equal the Python dataset ID.

- [ ] **Step 4: Add an explicitly opt-in live smoke test**

Register marker in `pyproject.toml`:

```toml
markers = ["live_api: opt-in public API smoke tests"]
```

The live test must be skipped unless `GEMINI_TRADING_RUN_LIVE_API_TESTS=1`, request a small old completed window, use no credentials, assert server-time and response shape only, and write no repository data.

- [ ] **Step 5: Run the complete Task 11 gate and second checkpoint**

```powershell
uv run pytest -m "not live_api"
uv run pre-commit run --all-files
uv run pyright
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
uv run detect-secrets scan --baseline .secrets.baseline
$env:GEMINI_TRADING_MODE = 'live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $code=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($code -eq 0) { throw 'live mode was accepted' } else { Write-Host 'PASS: live mode rejected' }
git diff --check
git status --short
```

Expected: deterministic suite passes without internet, hooks and scans pass, package builds, live mode fails closed, and no generated data is tracked.

- [ ] **Step 6: Append evidence, commit, push, and require remote checks**

```powershell
git add pyproject.toml tests/fixtures/binance_spot tests/acceptance/test_market_data_ingestion.py tests/integration/test_storage_adapter_equivalence.py tests/live/test_binance_spot_smoke.py reports/verification/market-data-core-progress.md
git commit -m "test: prove reproducible Binance candle ingestion"
git push
```

Do not begin finalization until GitHub `quality` and `gitleaks` both pass on the pushed SHA.

---

### Task 12: Document Operations, Final Verification, and Pull Request Evidence

**Files:**
- Create: `docs/architecture/adr/0002-market-data-core.md`
- Create: `docs/operations/binance-market-data.md`
- Modify: `README.md`
- Create: `reports/verification/market-data-core-final.md`
- Modify: `reports/verification/market-data-core-progress.md`

**Interfaces:**
- Produces: operator instructions, architecture rationale, exact-head final evidence, and PR-ready documentation.

- [ ] **Step 1: Write documentation acceptance checks**

Create `tests/acceptance/test_market_data_documentation.py` that asserts the README and operations guide contain the exact CLI commands, supported intervals, `[start,end)` semantics, completed-candle rule, raw/canonical directory behavior, replay/verify instructions, paper-only warning, issue #7 database deferral, issue #8 verification protocol, and no profitability claim.

- [ ] **Step 2: Run documentation test and confirm failure**

```powershell
uv run pytest tests/acceptance/test_market_data_documentation.py -q
```

Expected: failure because required documentation does not yet exist.

- [ ] **Step 3: Write ADR, operator guide, and README updates**

The ADR must record layered architecture, standard-library synchronous HTTP, immutable local files, deterministic canonical/provenance separation, fail-closed behavior, and deferred database storage. The operator guide must include safe PowerShell examples for ingest, replay, verify, optional live smoke testing, interpreting manifests, handling failures, and deleting local generated data without deleting committed fixtures.

- [ ] **Step 4: Run the final exact-head local verification**

Before generating the report, commit documentation and test changes, then capture the exact commit SHA:

```powershell
git add README.md docs/architecture/adr/0002-market-data-core.md docs/operations/binance-market-data.md tests/acceptance/test_market_data_documentation.py reports/verification/market-data-core-progress.md
git commit -m "docs: document verified market data core"
$head = git rev-parse HEAD
Write-Host $head
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run pytest -m "not live_api"
uv run ruff format --check .
uv run ruff check .
uv run pyright
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
uv run detect-secrets scan --baseline .secrets.baseline
$env:GEMINI_TRADING_MODE = 'live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $unsafe=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($unsafe -eq 0) { throw 'live mode was accepted' } else { Write-Host "PASS: live mode rejected with exit code $unsafe" }
git diff --check
git status --short
git rev-parse HEAD
```

Expected: every check passes, unsafe mode exits non-zero, status is clean, and the ending SHA equals `$head`.

- [ ] **Step 5: Create and commit the final verification report**

`reports/verification/market-data-core-final.md` must record the exact tested SHA, date, platform, Python version, each command, observed result, test count, coverage, fixed acceptance dataset ID, CI status, limitations, live smoke-test status, and explicit statement that the milestone establishes data trust rather than profitability. It must not claim a check that was not observed.

Commit:

```powershell
git add reports/verification/market-data-core-final.md reports/verification/market-data-core-progress.md
git commit -m "docs: publish market data core verification evidence"
git push
```

- [ ] **Step 6: Verify the report commit and remote checks**

Run the final deterministic verification again on the report commit because the exact PR head changed:

```powershell
uv run pre-commit run --all-files
uv run pytest -m "not live_api"
uv run pyright
git status --short
git rev-parse HEAD
```

Require GitHub `quality` and `gitleaks` to pass on this exact SHA. Append the exact SHA and remote conclusions to the final report only if a follow-up report commit will itself be reverified; otherwise place remote conclusions in the pull-request description to avoid an infinite report-commit cycle.

- [ ] **Step 7: Open the pull request and complete review gates**

Open a pull request from `feature/market-data-core` to protected `main` with:

```text
Title: feat: add verified Binance market data core
```

The PR body must summarize architecture, public adapter, immutable storage, canonical identity, replay, verification, acceptance evidence, issue #7 deferral, issue #8 protocol, exact-head checks, known limitations, and the absence of profitability claims. Keep the branch until review and merge are complete. After squash merge, verify the merged `main` with focused acceptance, full deterministic tests, Pyright, pre-commit, and a clean working tree before closing issue #8.
