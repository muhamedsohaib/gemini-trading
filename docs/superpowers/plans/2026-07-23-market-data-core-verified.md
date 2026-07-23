# Market Data Core Verified Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, fail-closed Binance Spot candle ingestion core that preserves immutable raw evidence, emits content-addressed canonical JSONL datasets, supports offline replay and independent verification, and remains restricted to research and paper modes.

**Architecture:** Domain values and pure validation are isolated from provider, transport, storage, and CLI code. The synchronous Binance public REST adapter returns exact response bytes; an ingestion service persists each page before parsing, classifies completion from one server-time snapshot, validates the full completed sequence, and only then writes deterministic canonical content. Retrieval provenance is stored separately from canonical identity.

**Tech Stack:** Python 3.12, Python standard library only at runtime, `pytest`, `Hypothesis`, Ruff, Pyright strict mode, pre-commit, detect-secrets, pip-audit, GitHub Actions.

## Global Constraints

- Execution modes remain exactly `research` and `paper`; `demo`, `live`, `production`, and unknown values fail closed.
- The public Binance adapter accepts no credential, API key, secret, signature, or authorization input.
- Each run handles one explicit instrument, one approved interval, and one bounded UTC window.
- Approved intervals are exactly `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, and `1w`.
- Canonical prices and volume are finite `Decimal` values; no canonical conversion passes through `float`.
- Retrieval windows use `[start_time, end_time)`.
- One Binance server-time snapshot governs the entire run.
- A candle is completed only when `close_time < server_time_snapshot`.
- Raw responses are persisted byte-for-byte before normalization.
- Incomplete candles may exist in raw pages but never in canonical output.
- Internal gaps, duplicates, reversals, malformed payloads, retry exhaustion, storage conflicts, or zero completed candles emit no canonical dataset.
- Canonical dataset identity is `sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)`.
- Run IDs, retrieval timestamps, page numbers, page hashes, and server time never alter canonical JSONL or dataset identity.
- `data/raw/` and `data/canonical/` are generated, ignored, and forbidden from Git tracking.
- Every task follows `docs/operations/market-data-core-step-verification.md` and appends observed evidence to `reports/verification/market-data-core-progress.md`.
- A task cannot be marked complete or used as the base for another task until its full gate passes.

## Normative Interface Contracts

Implement these exact public names and field types. Additional private helpers are allowed only when they do not change these contracts.

```python
# src/gemini_trading/domain/instrument.py
@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    base_asset: str
    quote_asset: str

# src/gemini_trading/domain/timeframe.py
class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def duration(self) -> timedelta: ...

# src/gemini_trading/domain/candle.py
@dataclass(frozen=True, slots=True)
class Candle:
    instrument: Instrument
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    completed: bool
    source_provider: str

# src/gemini_trading/domain/dataset.py
@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime

@dataclass(frozen=True, slots=True)
class RawPage:
    run_id: str
    sequence: int
    request_parameters: tuple[tuple[str, str], ...]
    retrieved_at: datetime
    server_time_snapshot: datetime
    http_status: int
    response_bytes: bytes
    response_sha256: str

class RetrievalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass(frozen=True, slots=True)
class RetrievalManifest:
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

@dataclass(frozen=True, slots=True)
class DatasetManifest:
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

@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    schema_version: str
    dataset_id: str
    run_id: str
    page_hashes: tuple[str, ...]
    retrieval_manifest_sha256: str
    linked: bool
    created_at: datetime
```

Provider and storage contracts:

```python
@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

class HttpTransport(Protocol):
    def get(self, url: str, timeout_seconds: float) -> HttpResponse: ...

@dataclass(frozen=True, slots=True)
class ProviderPage:
    request_parameters: tuple[tuple[str, str], ...]
    response: HttpResponse
    retrieved_at: datetime

class MarketDataProvider(Protocol):
    def fetch_server_time(self) -> datetime: ...
    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage: ...

class RawStore(Protocol):
    def write_page(self, page: RawPage) -> Path: ...
    def write_retrieval_manifest(self, manifest: RetrievalManifest) -> Path: ...
    def read_run(self, run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]: ...

class CanonicalStore(Protocol):
    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]: ...
    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path: ...
```

## Normative Retrieval Termination

The ingestion loop stops only under one of these conditions:

1. `cursor >= request.end_time`; or
2. a returned page contains at least one candle whose `close_time >= server_time_snapshot`.

A page containing an incomplete candle is the terminal guard page. It is preserved raw, all its rows are normalized, and only rows with `close_time < server_time_snapshot` may become canonical. A page having fewer than `limit` rows is not by itself a success condition. When a non-terminal page returns no rows while `cursor < request.end_time`, raise `IncompleteWindowError`. This prevents a short or empty response from silently truncating the requested completed history.

## Normative Immutable Write Algorithm

No final destination may contain partial bytes. Implement `write_immutable` using a same-directory temporary file and an atomic hard link:

```python
def write_immutable(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise RawStorageConflictError(f"immutable path conflicts: {path}") from None
    finally:
        temp.unlink(missing_ok=True)
    return path
```

The test suite must prove that a simulated write failure leaves no final destination file and that an existing conflicting destination remains unchanged.

---

### Task 1: Verification Ledger and Generated-Data Guard

**Files:**
- Create: `reports/verification/market-data-core-progress.md`
- Modify: `.gitignore`
- Modify: `src/gemini_trading/safety/repository_policy.py`
- Modify: `tests/unit/safety/test_repository_policy.py`

**Produces:** tracked-file rejection for `data/raw/` and `data/canonical/`, plus the append-only evidence ledger.

- [ ] Add parameterized failing tests for both generated prefixes.
- [ ] Run `uv run pytest tests/unit/safety/test_repository_policy.py -q`; observe the new cases fail.
- [ ] Add `GENERATED_MARKET_DATA_PREFIXES = ("data/raw/", "data/canonical/")` and reject normalized tracked paths beginning with either prefix using `RepositoryPolicyError("generated market data must not be tracked: ...")`.
- [ ] Add both directories to `.gitignore`.
- [ ] Create the progress log with rules requiring tested SHA, commands, outcomes, failures, remediation, and limitations.
- [ ] Run:

```powershell
uv run pytest tests/unit/safety/test_repository_policy.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/safety tests/unit/safety
uv run ruff check src/gemini_trading/safety tests/unit/safety
uv run pyright
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
git diff --check
git status --short
```

- [ ] Append observed evidence and commit:

```powershell
git add .gitignore src/gemini_trading/safety/repository_policy.py tests/unit/safety/test_repository_policy.py reports/verification/market-data-core-progress.md
git commit -m "chore: establish market data verification ledger"
```

---

### Task 2: Domain Contracts and Error Taxonomy

**Files:**
- Create: `src/gemini_trading/domain/__init__.py`
- Create: `src/gemini_trading/domain/time.py`
- Create: `src/gemini_trading/domain/instrument.py`
- Create: `src/gemini_trading/domain/timeframe.py`
- Create: `src/gemini_trading/domain/candle.py`
- Create: `src/gemini_trading/domain/dataset.py`
- Create: `src/gemini_trading/data/__init__.py`
- Create: `src/gemini_trading/data/errors.py`
- Create: `tests/unit/domain/test_instrument.py`
- Create: `tests/unit/domain/test_timeframe.py`
- Create: `tests/unit/domain/test_candle.py`
- Create: `tests/unit/domain/test_dataset.py`
- Create: `tests/unit/data/test_errors.py`

**Produces:** every normative domain contract above and the complete error hierarchy.

- [ ] Write failing tests for uppercase normalization, `symbol == base_asset + quote_asset`, identifier regex `^[A-Z0-9]{2,30}$`, curated timeframe set, exact durations, UTC-aware-only timestamps, millisecond-aligned candle timestamps, finite decimals, frozen dataclasses, reversed windows, and safe error metadata.
- [ ] Use `dataclasses.replace(candle, close=Decimal("NaN"))` in the non-finite test; do not use `__dict__` because the contract requires slots.
- [ ] Run `uv run pytest tests/unit/domain tests/unit/data/test_errors.py -q`; observe import failures.
- [ ] Implement one shared helper in `domain/time.py`:

```python
def require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be UTC-aware")
```

- [ ] Implement `Instrument.__post_init__` by stripping and uppercasing all fields with `object.__setattr__`, validating each identifier, and requiring exact concatenation.
- [ ] Implement `Timeframe.duration` with exact timedeltas.
- [ ] Implement `Candle.__post_init__` to require UTC, `open_time < close_time`, millisecond alignment, non-empty provider, and finite decimals. Leave OHLC geometry and sign rules to Task 3.
- [ ] Implement `RetrievalRequest.__post_init__` to require UTC and `end_time > start_time`.
- [ ] Implement these exact errors in `data/errors.py`: `MarketDataError`, `ProviderConnectionError`, `ProviderRateLimitError(retry_after_seconds)`, `ProviderResponseError(status_code, retryable)`, `ProviderSchemaError`, `InvalidRetrievalWindowError`, `CandleValidationError`, `DuplicateCandleError`, `OutOfOrderCandleError`, `CandleGapError`, `IncompleteWindowError`, `RawStorageConflictError`, and `CanonicalDatasetWriteError`. No error stores raw body bytes.
- [ ] Run:

```powershell
uv run pytest tests/unit/domain tests/unit/data/test_errors.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/domain src/gemini_trading/data/errors.py tests/unit/domain tests/unit/data/test_errors.py
uv run ruff check src/gemini_trading/domain src/gemini_trading/data/errors.py tests/unit/domain tests/unit/data/test_errors.py
uv run pyright
git diff --check
```

- [ ] Append evidence and commit `feat: define market data domain contracts`.

---

### Task 3: Pure Candle Validation

**Files:**
- Create: `src/gemini_trading/data/validation/__init__.py`
- Create: `src/gemini_trading/data/validation/candles.py`
- Create: `tests/unit/data/validation/test_candles.py`
- Create: `tests/property/test_candle_validation.py`

**Produces:**

```python
def validate_candle(candle: Candle) -> None: ...
def completed_candles(candles: Sequence[Candle], server_time: datetime) -> tuple[Candle, ...]: ...
def validate_candle_sequence(candles: Sequence[Candle], request: RetrievalRequest) -> None: ...
```

- [ ] Write failing unit tests for non-positive OHLC, negative volume, zero volume accepted, `low <= open <= high`, `low <= close <= high`, mixed instrument/timeframe, outside-window open times, incomplete canonical candle, duplicate, reversal, gap, and empty sequence.
- [ ] Write Hypothesis tests that mutate valid sequences into duplicates, reversals, and gaps and always observe the corresponding exception.
- [ ] Run focused tests and observe import failure.
- [ ] Implement `completed_candles` using `dataclasses.replace(candle, completed=True)` only when `candle.close_time < server_time`; it returns no incomplete candle.
- [ ] Implement sequence checks in exact order: non-empty, per-candle geometry, identity consistency, request containment, completed flag, duplicate, strict order, then exact `timeframe.duration` continuity.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/validation tests/property/test_candle_validation.py tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/validation tests/unit/data/validation tests/property/test_candle_validation.py
uv run ruff check src/gemini_trading/data/validation tests/unit/data/validation tests/property/test_candle_validation.py
uv run pyright
git diff --check
```

- [ ] Append evidence and commit `feat: validate canonical candle sequences`.

---

### Task 4: Strict Binance Kline Normalization

**Files:**
- Create: `src/gemini_trading/data/normalization/__init__.py`
- Create: `src/gemini_trading/data/normalization/binance_klines.py`
- Create: `tests/fixtures/binance_spot/klines_valid_single_page.json`
- Create: `tests/fixtures/binance_spot/klines_malformed_shape.json`
- Create: `tests/fixtures/binance_spot/klines_invalid_decimal.json`
- Create: `tests/unit/data/normalization/test_binance_klines.py`
- Create: `tests/property/test_binance_normalization.py`

**Produces:**

```python
def normalize_binance_klines(
    payload: bytes,
    instrument: Instrument,
    timeframe: Timeframe,
) -> tuple[Candle, ...]: ...
```

- [ ] Add sanitized public fixtures and failing tests for exact decimal exponent preservation, row shape, invalid UTF-8, invalid JSON, non-list root, invalid millisecond types, non-finite decimals, and safe exception messages.
- [ ] Run focused tests and observe import failure.
- [ ] Decode UTF-8, parse JSON, require a list root and each row to be a list with at least 7 fields.
- [ ] Read indices `0,1,2,3,4,5,6` as open time, open, high, low, close, volume, close time.
- [ ] Convert integer milliseconds with `datetime.fromtimestamp(value / 1000, tz=UTC)` only after confirming `type(value) is int`.
- [ ] Convert numeric fields with `Decimal(str(value))`; reject non-finite values; never call `float`.
- [ ] Create candles with `completed=False` and `source_provider="binance_spot"`.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/normalization tests/property/test_binance_normalization.py tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/normalization tests/unit/data/normalization tests/property/test_binance_normalization.py
uv run ruff check src/gemini_trading/data/normalization tests/unit/data/normalization tests/property/test_binance_normalization.py
uv run pyright
uv run pre-commit run detect-secrets --all-files
git diff --check
```

- [ ] Append evidence and commit `feat: normalize Binance kline payloads`.

---

### Task 5: HTTP Transport and Binance Spot Provider

**Files:**
- Create: `src/gemini_trading/data/providers/__init__.py`
- Create: `src/gemini_trading/data/providers/base.py`
- Create: `src/gemini_trading/data/providers/http.py`
- Create: `src/gemini_trading/data/providers/binance_spot.py`
- Create: `tests/unit/data/providers/test_http.py`
- Create: `tests/unit/data/providers/test_binance_spot.py`
- Create: `tests/integration/test_binance_provider_contract.py`

**Produces:** every normative provider/HTTP contract above and `BinanceSpotProvider`.

- [ ] Write failing tests using an injected fake transport. Assert exact endpoints `/api/v3/time` and `/api/v3/klines`; exact query keys `symbol`, `interval`, `startTime`, `endTime`, `limit`; integer UTC milliseconds; unchanged response bytes; no credential parameters; 429 mapping with `Retry-After`; 5xx retryable mapping; other 4xx permanent mapping; connection exception mapping; malformed server-time schema rejection.
- [ ] Run focused tests and observe import failure.
- [ ] Implement `UrllibTransport.get` using `urllib.request.Request(method="GET")`. Return `HTTPError` status/body/headers to the adapter for classification; convert `URLError`, `TimeoutError`, and `OSError` to a body-free `ProviderConnectionError`.
- [ ] Implement `BinanceSpotProvider(base_url="https://api.binance.com", timeout_seconds=10.0, transport=UrllibTransport(), clock=...)`. Do not define credential parameters and do not read credential environment variables.
- [ ] Use `urllib.parse.urlencode` and stable sorted request parameter tuples.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/providers tests/integration/test_binance_provider_contract.py tests/unit/data/normalization tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/providers tests/unit/data/providers tests/integration/test_binance_provider_contract.py
uv run ruff check src/gemini_trading/data/providers tests/unit/data/providers tests/integration/test_binance_provider_contract.py
uv run pyright
$matches = Select-String -Path src/gemini_trading/data/providers/*.py -Pattern 'api[_-]?key|secret|signature|authorization' -CaseSensitive:$false; if ($matches) { $matches; throw 'credential surface found' } else { Write-Host 'PASS: no credential surface' }
git diff --check
```

- [ ] Append evidence and commit `feat: add Binance Spot market data provider`.

---

### Task 6: Immutable Local Storage

**Files:**
- Create: `src/gemini_trading/data/storage/__init__.py`
- Create: `src/gemini_trading/data/storage/base.py`
- Create: `src/gemini_trading/data/storage/local_immutable.py`
- Create: `tests/unit/data/storage/test_local_immutable.py`
- Create: `tests/property/test_immutable_storage.py`

**Produces:** normative storage protocols and `LocalImmutableStore`.

- [ ] Write failing tests for exact bytes, idempotent identical writes, conflict rejection, path traversal rejection, six-digit page names, simulated temporary-write failure, no partial final file, and unchanged existing conflict target.
- [ ] Run focused tests and observe import failure.
- [ ] Implement strict identity segments matching `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` and reject separators or `..`.
- [ ] Implement the normative hard-link `write_immutable` algorithm above.
- [ ] Store raw pages at `data/raw/binance_spot/<run-id>/page-000001.json` and the stable JSON retrieval manifest at `retrieval-manifest.json`.
- [ ] Store canonical files at `data/canonical/<dataset-id>/candles.jsonl`, `dataset-manifest.json`, and `provenance/<run-id>.json`.
- [ ] Implement read methods that reconstruct typed domain objects and verify file existence; hash verification remains Task 9.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/storage tests/property/test_immutable_storage.py tests/unit/data/normalization tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/storage tests/unit/data/storage tests/property/test_immutable_storage.py
uv run ruff check src/gemini_trading/data/storage tests/unit/data/storage tests/property/test_immutable_storage.py
uv run pyright
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: generated data untracked')"
git diff --check
```

- [ ] Append evidence and commit `feat: add immutable local market data storage`.

---

### Task 7: Deterministic Canonical Dataset Writer

**Files:**
- Create: `src/gemini_trading/data/datasets/__init__.py`
- Create: `src/gemini_trading/data/datasets/canonical_writer.py`
- Create: `tests/unit/data/datasets/test_canonical_writer.py`
- Create: `tests/property/test_dataset_identity.py`

**Produces:**

```python
def serialize_candles(candles: Sequence[Candle]) -> bytes: ...
def dataset_id(schema_version: str, canonical_bytes: bytes) -> str: ...
def build_dataset_manifest(...) -> DatasetManifest: ...
def serialize_dataset_manifest(manifest: DatasetManifest) -> bytes: ...
def build_provenance(...) -> DatasetProvenance: ...
def serialize_provenance(receipt: DatasetProvenance) -> bytes: ...
```

- [ ] Write failing tests for fixed field order, compact UTF-8 JSON, one newline per row, UTC `Z` milliseconds, trailing decimal zeros, exact identity formula, deterministic manifest bytes, and run/provenance isolation.
- [ ] Write Hypothesis tests proving identical candles always produce identical bytes and identity; changing any canonical value changes bytes and normally changes identity; changing only run metadata never changes canonical bytes or identity.
- [ ] Run focused tests and observe import failure.
- [ ] Serialize explicit ordered dictionaries with `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`.
- [ ] Serialize decimals with `format(value, "f")` and times with `astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")`.
- [ ] Exclude run ID, page hashes, server time, retrieval time, and creation time from JSONL and `DatasetManifest`.
- [ ] Include those values only in `DatasetProvenance`.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/datasets tests/property/test_dataset_identity.py tests/unit/data/storage tests/unit/data/validation tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/datasets tests/unit/data/datasets tests/property/test_dataset_identity.py
uv run ruff check src/gemini_trading/data/datasets tests/unit/data/datasets tests/property/test_dataset_identity.py
uv run pyright
git diff --check
```

- [ ] Append evidence and commit `feat: create content addressed candle datasets`.

---

### Task 8: Retry Policy and Fail-Closed Ingestion

**Files:**
- Create: `src/gemini_trading/data/ingestion/__init__.py`
- Create: `src/gemini_trading/data/ingestion/retry.py`
- Create: `src/gemini_trading/data/ingestion/service.py`
- Create: `tests/unit/data/ingestion/test_retry.py`
- Create: `tests/unit/data/ingestion/test_service.py`
- Create: `tests/fixtures/binance_spot/klines_valid_two_pages_page_1.json`
- Create: `tests/fixtures/binance_spot/klines_valid_two_pages_page_2.json`
- Create: `tests/fixtures/binance_spot/klines_internal_gap.json`

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5

@dataclass(frozen=True, slots=True)
class IngestionResult:
    run_id: str
    dataset_id: str
    raw_page_count: int
    candle_count: int
    paths: tuple[tuple[str, Path], ...]

class IngestionService:
    def ingest(self, request: RetrievalRequest) -> IngestionResult: ...
```

- [ ] Write failing deterministic tests with fake provider, stores, clock, sleeper, and run-ID factory. Prove one server-time call, persisted-before-parse ordering, forward cursor progress, repeated cursor rejection, terminal incomplete page behavior, short non-terminal page continuation, empty non-terminal page failure, transient retry, `Retry-After`, exhaustion failure manifest, malformed raw preservation, gap failure, zero-completed failure, and no canonical writes before complete validation.
- [ ] Run focused tests and observe import failure.
- [ ] Implement `RetryPolicy` validation and `delay_for`: exponential `base * 2 ** (attempt - 1)`, raised to `retry_after_seconds` when larger.
- [ ] Retry only `ProviderConnectionError`, `ProviderRateLimitError`, and `ProviderResponseError(retryable=True)`.
- [ ] Implement the normative retrieval termination rules above. Do not terminate solely because a page has fewer than `limit` rows.
- [ ] Create and persist `RawPage` before calling the normalizer.
- [ ] On any failure after run creation, write one failed `RetrievalManifest` with safe type/message and no canonical output, then re-raise.
- [ ] On success, classify completed candles, validate sequence, serialize canonical bytes, write deterministic manifest, hash retrieval manifest, then write provenance.
- [ ] Run checkpoint 1:

```powershell
uv run pytest tests/unit/data/ingestion tests/unit/data tests/property tests/regression tests/unit/safety -q
uv run pre-commit run --all-files
uv run pyright
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
$env:GEMINI_TRADING_MODE='live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $code=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($code -eq 0) { throw 'live mode accepted' } else { Write-Host 'PASS: live mode rejected' }
git diff --check
git status --short
```

- [ ] Append task and checkpoint evidence, commit `feat: orchestrate fail closed market data ingestion`, push, and require GitHub `quality` and `gitleaks` on that SHA before Task 9.

---

### Task 9: Offline Replay and Independent Verification

**Files:**
- Create: `src/gemini_trading/data/ingestion/replay.py`
- Create: `src/gemini_trading/data/verification/__init__.py`
- Create: `src/gemini_trading/data/verification/service.py`
- Create: `tests/unit/data/ingestion/test_replay.py`
- Create: `tests/unit/data/verification/test_service.py`
- Create: `tests/integration/test_replay_without_network.py`

**Produces:**

```python
class ReplayService:
    def replay(self, run_id: str) -> IngestionResult: ...

@dataclass(frozen=True, slots=True)
class VerificationResult:
    dataset_id: str
    run_id: str
    candle_count: int
    checks: tuple[str, ...]

class VerificationService:
    def verify(self, dataset_id: str, run_id: str) -> VerificationResult: ...
```

- [ ] Write failing tests proving `ReplayService` has no provider field or parameter, no network is called, identical canonical bytes/manifest/ID are reproduced, equivalent runs produce separate receipts, and every raw/canonical/provenance tampering case fails.
- [ ] Run focused tests and observe import failure.
- [ ] Replay must read and recompute the retrieval manifest hash and every listed page hash before normalization.
- [ ] Replay must reuse the exact Task 4, Task 3, and Task 7 functions; it must not duplicate canonical logic.
- [ ] Verification must recompute rather than trust raw page hashes, retrieval manifest hash, canonical hash, dataset ID, deterministic manifest bytes, provenance linkage, parsed continuity, and completed state.
- [ ] Run:

```powershell
uv run pytest tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py tests/unit/data tests/property tests/regression tests/unit/safety -q
uv run ruff format --check src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py
uv run ruff check src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification tests/unit/data/ingestion/test_replay.py tests/unit/data/verification tests/integration/test_replay_without_network.py
uv run pyright
git diff --check
```

- [ ] Append evidence and commit `feat: replay and verify canonical market data`.

---

### Task 10: Safe CLI

**Files:**
- Create: `src/gemini_trading/cli/__init__.py`
- Create: `src/gemini_trading/cli/main.py`
- Create: `src/gemini_trading/cli/market_data.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/unit/cli/test_market_data.py`
- Create: `tests/acceptance/test_market_data_cli.py`

**Produces:** `gemini-trading market-data ingest|replay|verify`.

- [ ] Write failing tests for required explicit instrument/window arguments, interval rejection before network, safe compact JSON success output, safe compact JSON failure output, exit code 2 for `MarketDataError`, no traceback/raw body/environment dump, and runtime policy checked before ingestion.
- [ ] Run focused tests and observe entry-point failure.
- [ ] Add `[project.scripts] gemini-trading = "gemini_trading.cli.main:main"`.
- [ ] Implement `main(argv: Sequence[str] | None = None) -> int` with `argparse`; parse ISO `Z` timestamps into UTC datetimes; require `--symbol`, `--base-asset`, `--quote-asset`, `--interval`, `--start`, `--end`, and `--output-root` for ingest.
- [ ] Call `load_runtime_policy()` before constructing a network provider.
- [ ] Print only run ID, status, counts, dataset ID, safe paths, or safe error class/message.
- [ ] Run:

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

- [ ] Append evidence and commit `feat: expose safe market data CLI`.

---

### Task 11: Deterministic Acceptance Matrix and Optional Live Smoke Test

**Files:**
- Create: `tests/fixtures/binance_spot/ethusdt_4h_acceptance_page_1.json`
- Create: `tests/fixtures/binance_spot/ethusdt_4h_acceptance_page_2.json`
- Create: `tests/acceptance/test_market_data_ingestion.py`
- Create: `tests/integration/test_storage_adapter_equivalence.py`
- Create: `tests/live/test_binance_spot_smoke.py`
- Modify: `pyproject.toml`

**Produces:** fixed ETHUSDT 4h end-to-end evidence while proving implementation remains generic.

- [ ] Write the acceptance test before fixtures. Assert raw byte equality, completed retrieval manifest, completed/order/gap rules, exact decimal scale, fixed expected dataset hash, replay byte equality, verification checks, equivalent-run identity, separate provenance, and storage-adapter canonical equivalence.
- [ ] Add a source scan assertion that production modules contain no `ETHUSDT`, `BTCUSDT`, or `SOLUSDT` literals.
- [ ] Run acceptance tests and observe fixture/identity failure.
- [ ] Add only bounded sanitized public fixture bytes.
- [ ] Independently calculate the expected identity with PowerShell 5.1-compatible code:

```powershell
$bytes = [System.IO.File]::ReadAllBytes($canonicalPath)
$prefix = [System.Text.Encoding]::UTF8.GetBytes("market-candle-v1`n")
$combined = New-Object byte[] ($prefix.Length + $bytes.Length)
[Array]::Copy($prefix, 0, $combined, 0, $prefix.Length)
[Array]::Copy($bytes, 0, $combined, $prefix.Length, $bytes.Length)
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $hash = $sha.ComputeHash($combined) } finally { $sha.Dispose() }
[Convert]::ToHexString($hash).ToLowerInvariant()
```

- [ ] Register `live_api` in pytest markers. The smoke test skips unless `GEMINI_TRADING_RUN_LIVE_API_TESTS=1`, uses no credentials, requests a small old completed window, asserts response shape, and writes only under pytest `tmp_path`.
- [ ] Run checkpoint 2:

```powershell
uv run pytest -m "not live_api"
uv run pre-commit run --all-files
uv run pyright
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines()); print('PASS: tracked-file policy')"
uv run pre-commit run detect-secrets --all-files
$env:GEMINI_TRADING_MODE='live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $code=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($code -eq 0) { throw 'live mode accepted' } else { Write-Host 'PASS: live mode rejected' }
git diff --check
git status --short
```

- [ ] Append evidence, commit `test: prove reproducible Binance candle ingestion`, push, and require `quality` and `gitleaks` on that SHA.

---

### Task 12: Operations Documentation, Exact-Head Verification, and PR

**Files:**
- Create: `docs/architecture/adr/0002-market-data-core.md`
- Create: `docs/operations/binance-market-data.md`
- Modify: `README.md`
- Create: `tests/acceptance/test_market_data_documentation.py`
- Create: `reports/verification/market-data-core-final.md`
- Modify: `reports/verification/market-data-core-progress.md`

**Produces:** operator documentation, architecture rationale, exact-head evidence, and a PR ready for protected merge.

- [ ] Write a failing documentation test requiring exact CLI commands, intervals, `[start,end)`, completion rule, storage paths, replay, verify, paper-only warning, issue #7 deferral, issue #8 protocol, and no profitability claim.
- [ ] Run the test and observe failure.
- [ ] Write ADR 0002, operator guide, and README updates satisfying every assertion.
- [ ] Run documentation tests, append evidence, and commit `docs: document verified market data core`.
- [ ] Capture the exact SHA and run:

```powershell
$head = git rev-parse HEAD
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
uv run pre-commit run detect-secrets --all-files
$env:GEMINI_TRADING_MODE='live'; uv run python -c "from gemini_trading.safety.execution_mode import load_runtime_policy; load_runtime_policy()"; $unsafe=$LASTEXITCODE; Remove-Item Env:GEMINI_TRADING_MODE; if ($unsafe -eq 0) { throw 'live mode accepted' } else { Write-Host "PASS: live mode rejected with exit code $unsafe" }
git diff --check
git status --short
if ((git rev-parse HEAD) -ne $head) { throw 'HEAD changed during verification' }
```

- [ ] Create `market-data-core-final.md` using only observed facts: SHA, date, OS, Python, commands, outcomes, test count, coverage, fixed dataset ID, limitations, and live smoke-test status. State that this establishes data integrity, not profitability.
- [ ] Commit `docs: publish market data core verification evidence`, then rerun pre-commit, all non-live tests, Pyright, status, and exact SHA because the report commit changed HEAD.
- [ ] Push and require GitHub `quality` and `gitleaks` on the exact report SHA.
- [ ] Open PR `feat: add verified Binance market data core` from `feature/market-data-core` to `main`. Include issue #7, issue #8, architecture, exact-head evidence, limitations, and no profitability claim.
- [ ] After squash merge, pull protected `main`, rerun focused acceptance plus full deterministic tests, Pyright, pre-commit, and clean-tree checks. Close issue #8 only after merged-main evidence passes.

## Self-Review Results

- **Spec coverage:** provider, raw storage, canonical content, content identity, provenance isolation, retries, incomplete-candle handling, bounded windows, replay, verification, CLI, deterministic CI tests, optional smoke test, issue #7, and issue #8 are all assigned to explicit tasks.
- **Placeholder scan:** no `TBD`, `TODO`, unspecified error handling, or deferred implementation instruction exists in this plan.
- **Type consistency:** the normative contracts at the top define every cross-task public type and signature.
- **Corrections from the first draft:** slotted dataclass tests use `dataclasses.replace`; UTC validation is shared; immutable writes cannot expose partial final files; short pages cannot silently terminate ingestion; incomplete terminal pages end retrieval safely; the independent hash command works in Windows PowerShell 5.1 and PowerShell 7.
