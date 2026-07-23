# Market Data Core Design

## Status

Approved design for the first final-version development milestone on `feature/market-data-core`.

The milestone establishes trustworthy, reproducible Binance Spot candle ingestion for research and paper-execution workflows. It does not claim or attempt to establish trading profitability. Its purpose is to ensure that later strategy evidence is built on complete, canonical, independently verifiable market data.

## 1. Objectives

The Market Data Core must let a user:

1. request a bounded historical Binance Spot candle window;
2. preserve each external response as immutable raw evidence;
3. normalize and validate the response into canonical candles;
4. exclude incomplete candles from trusted datasets;
5. fail closed when retrieval or validation is incomplete;
6. produce deterministic JSON Lines datasets and manifests;
7. replay canonical generation without network access;
8. verify every raw and canonical content hash;
9. replace storage implementations later without changing research results.

The first deterministic acceptance case uses `ETHUSDT` at `4h`, but the implementation is generic across valid Binance Spot symbols and the approved interval set.

## 2. Approved Scope Decisions

- Provider: Binance Spot public REST market data.
- Credentials: no API credential is required or accepted for this public-data adapter.
- Ingestion unit: one symbol and one interval per retrieval run.
- Supported intervals: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, and `1w`.
- Numeric representation: `Decimal` throughout canonical price and volume fields.
- Retrieval contract: explicit bounded UTC window with `symbol`, `interval`, `start_time`, and `end_time`.
- Window semantics: `[start_time, end_time)`.
- Completion authority: one Binance server-time snapshot per retrieval run.
- Incomplete candles: preserved in raw evidence but excluded from canonical output.
- Failure policy: bounded retries for transient failures, then fail closed.
- Raw storage: one immutable JSON response file per page plus a retrieval manifest.
- Canonical storage: deterministic JSON Lines, a deterministic dataset manifest, and per-run provenance receipts.
- Dataset identity: content-addressed SHA-256 identity derived from schema version and canonical bytes.
- Current storage: immutable local filesystem store.
- Deferred storage: database-backed ingestion tracked by GitHub issue #7.

## 3. Non-Goals

This milestone does not include:

- multi-symbol batch scheduling;
- WebSocket streaming;
- order-book or trade-level ingestion;
- database-backed storage;
- Parquet output;
- feature generation;
- strategy signals;
- backtesting;
- portfolio construction;
- execution or order submission;
- production infrastructure.

Execution remains restricted to `research` and `paper` modes.

## 4. Architecture

The approved approach is a layered functional core with external adapters:

```text
Binance Spot REST adapter
        ↓
Immutable raw-page store
        ↓
Provider-specific normalization
        ↓
Canonical validation
        ↓
Deterministic JSONL dataset writer
        ↓
Content-addressed dataset manifest
        ↓
Immutable retrieval provenance receipt
```

Responsibilities are separated so each component is independently testable and replaceable.

### 4.1 Proposed package structure

```text
src/gemini_trading/
├── domain/
│   ├── instrument.py
│   ├── timeframe.py
│   ├── candle.py
│   └── dataset.py
├── data/
│   ├── providers/
│   │   ├── base.py
│   │   └── binance_spot.py
│   ├── storage/
│   │   ├── base.py
│   │   └── local_immutable.py
│   ├── validation/
│   │   ├── candles.py
│   │   └── windows.py
│   ├── normalization/
│   │   └── binance_klines.py
│   ├── datasets/
│   │   └── canonical_writer.py
│   └── ingestion/
│       └── service.py
└── cli/
    └── market_data.py
```

Tests mirror these boundaries under `tests/unit`, `tests/property`, `tests/integration`, and `tests/acceptance`.

### 4.2 Dependency direction

```text
domain
  ↑
validation and normalization
  ↑
provider and storage interfaces
  ↑
provider and storage implementations
  ↑
ingestion orchestration and CLI
```

Domain modules must not import HTTP, filesystem, CLI, or Binance-specific code.

## 5. Domain Contracts

### 5.1 Instrument

`Instrument` is an immutable canonical market identity containing:

- normalized uppercase symbol, such as `ETHUSDT`;
- base asset;
- quote asset.

It rejects empty or malformed values. The first implementation requires explicit base and quote assets rather than attempting ambiguous symbol parsing.

### 5.2 Timeframe

`Timeframe` is a restricted enum containing:

```text
1m, 5m, 15m, 1h, 4h, 1d, 1w
```

Each value exposes:

- its provider value;
- its nominal duration;
- deterministic cursor advancement behavior;
- continuity rules.

The adapter does not request a non-UTC kline timezone. For `1w`, the first accepted provider candle establishes the alignment and every subsequent open time must advance by exactly seven days.

### 5.3 RetrievalRequest

`RetrievalRequest` contains:

- instrument;
- timeframe;
- timezone-aware UTC `start_time`;
- timezone-aware UTC `end_time`.

Requirements:

- both timestamps must be UTC-aware;
- `end_time` must be later than `start_time`;
- the request uses `[start_time, end_time)` semantics;
- naive datetimes are rejected;
- unsupported intervals are rejected before network access.

### 5.4 Candle

`Candle` is an immutable canonical record containing:

- instrument identity;
- timeframe;
- UTC open time;
- UTC close time;
- open, high, low, and close as `Decimal`;
- volume as `Decimal`;
- completion state;
- source provider.

Trusted canonical datasets may contain only completed candles.

Retrieval-run IDs, page numbers, and page hashes are provenance, not canonical candle values. They must not alter canonical JSONL bytes or the dataset identity.

### 5.5 RawPage

`RawPage` represents one external response page and its retrieval metadata:

- retrieval-run identity;
- request parameters;
- page sequence;
- retrieval timestamp;
- Binance server-time snapshot;
- HTTP status;
- exact response bytes;
- SHA-256 response hash.

The stored response bytes are not reformatted before hashing or persistence.

### 5.6 RetrievalManifest

The retrieval manifest records:

- schema version;
- retrieval-run identity;
- provider;
- instrument and timeframe;
- requested window;
- server-time snapshot;
- page sequence and page hashes;
- retry and failure summary;
- final status: `completed` or `failed`;
- safe diagnostic reason when failed.

A failed retrieval manifest never authorizes canonical dataset creation.

### 5.7 DatasetManifest

The deterministic canonical dataset manifest records only content-derived or request-stable values:

- schema version;
- dataset ID;
- provider;
- instrument and timeframe;
- requested window;
- actual first and last candle times;
- candle count;
- canonical file SHA-256 hash.

It excludes retrieval-run IDs, page hashes, and wall-clock creation timestamps. Therefore the same canonical bytes cannot create conflicting dataset manifests.

The dataset ID is defined as:

```text
sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)
```

Identical canonical bytes under the same schema version produce the same identity.

### 5.8 DatasetProvenance

A separate immutable provenance receipt links one completed retrieval run to one canonical dataset. It records:

- provenance schema version;
- dataset ID;
- source retrieval-run ID;
- ordered raw-page hashes;
- retrieval-manifest hash;
- deterministic linkage status;
- receipt creation timestamp.

A dataset may have multiple provenance receipts when independent retrieval runs produce the same canonical content. An existing receipt identity cannot be overwritten with different content.

## 6. Interfaces

### 6.1 MarketDataProvider

The provider interface is responsible only for external retrieval. Its conceptual operations are:

```python
fetch_server_time()
fetch_klines(request, cursor)
```

It must:

- return exact raw response bytes and safe response metadata;
- use bounded start and end parameters;
- paginate chronologically;
- classify provider failures;
- avoid writing files;
- avoid constructing trusted canonical datasets.

### 6.2 RawStore

The raw-storage interface is responsible only for immutable persistence:

```python
write_page(raw_page)
write_retrieval_manifest(manifest)
read_run(run_id)
```

An existing identity may be reused only when the stored bytes are identical. Different bytes at an existing identity raise `RawStorageConflictError`.

### 6.3 CanonicalDatasetWriter

The writer:

- serializes one canonical candle per JSONL line;
- uses stable field ordering;
- serializes decimals as exact strings;
- serializes timestamps in canonical UTC form;
- computes canonical bytes before deriving the dataset identity;
- writes the deterministic dataset manifest;
- writes a separate provenance receipt;
- never overwrites conflicting content.

### 6.4 IngestionService

The service coordinates:

```text
capture server time
→ fetch page
→ persist raw page
→ advance cursor
→ normalize records
→ validate candles
→ validate continuity and window completeness
→ write canonical dataset and deterministic manifest
→ write retrieval provenance receipt
```

It contains no Binance parsing rules and no direct filesystem operations.

## 7. Retrieval and Completion Semantics

### 7.1 Server-time snapshot

The service captures one authoritative Binance server-time snapshot at the start of the retrieval run. Every candle in that run is evaluated against the same snapshot.

A candle is canonical only when its close time is strictly earlier than the captured server time. The newest incomplete candle may be preserved in raw evidence but is excluded from canonical output.

### 7.2 Pagination

Pagination advances monotonically from the requested start toward the exclusive end boundary.

The implementation must prevent:

- repeated cursors;
- page overlap that creates silent duplicates;
- backward movement;
- requests beyond the end boundary;
- infinite loops when a provider returns no progress.

### 7.3 Window completeness

A canonical dataset is emitted only when the completed-candle portion of the requested window is fully represented and continuous.

An intentional partial boundary is distinguishable from an internal missing candle. An internal gap always fails the run.

A request producing zero completed candles raises `IncompleteWindowError` and emits no canonical dataset.

### 7.4 Partial failures

Successfully fetched raw pages remain preserved after failure. The retrieval manifest records the failed status and safe reason. No canonical dataset, successful dataset manifest, or provenance receipt is written.

## 8. Validation Rules

Every canonical candle must satisfy:

```text
open > 0
high > 0
low > 0
close > 0
volume >= 0
low <= open <= high
low <= close <= high
open_time < close_time
```

A zero-volume candle is valid. Negative volume is invalid.

Dataset-level validation requires:

- timezone-aware UTC timestamps;
- matching instrument and timeframe throughout the dataset;
- strictly increasing open times;
- no duplicate open times;
- no candle outside the requested window;
- no incomplete canonical candle;
- no malformed provider record;
- no internal gap;
- at least one completed candle.

For fixed-duration intervals, continuity requires:

```text
next.open_time == current.open_time + interval_duration
```

For `1w`, `interval_duration` is exactly seven days and alignment is inherited from the first accepted provider candle.

## 9. Retry and Error Handling

### 9.1 Retry policy

Retry only transient failures:

- connection interruption;
- timeout;
- HTTP rate limiting;
- provider server errors.

Do not retry permanent failures:

- invalid symbol;
- unsupported interval;
- invalid request;
- malformed response schema;
- validation failure.

Retries use:

- a fixed maximum attempt count;
- exponential backoff;
- provider retry guidance when available;
- injectable sleep behavior for deterministic tests.

### 9.2 Error taxonomy

```text
MarketDataError
├── ProviderConnectionError
├── ProviderRateLimitError
├── ProviderResponseError
├── ProviderSchemaError
├── InvalidRetrievalWindowError
├── CandleValidationError
├── DuplicateCandleError
├── OutOfOrderCandleError
├── CandleGapError
├── IncompleteWindowError
├── RawStorageConflictError
└── CanonicalDatasetWriteError
```

Errors include safe diagnostic context but never credentials, authorization headers, or unrestricted response dumps.

## 10. Storage Design

### 10.1 Raw layout

```text
data/
└── raw/
    └── binance_spot/
        └── <run-id>/
            ├── page-000001.json
            ├── page-000002.json
            └── retrieval-manifest.json
```

Each page is immutable and independently hashable.

### 10.2 Canonical layout

```text
data/
└── canonical/
    └── <dataset-id>/
        ├── candles.jsonl
        ├── dataset-manifest.json
        └── provenance/
            └── <run-id>.json
```

The JSONL bytes and dataset manifest are deterministic for a dataset identity. Provenance receipts may accumulate without changing those canonical files.

`data/raw/` and `data/canonical/` are ignored by Git. Only small sanitized public-data fixtures needed for deterministic tests may be committed.

### 10.3 Deferred database adapter

Database-backed storage is deferred to issue #7. The future adapter must preserve provider and storage interfaces, immutable raw semantics, canonical byte equality, dataset identities, provenance receipts, migrations, rollback, and benchmark evidence.

The intended progression is local immutable files, then SQLite when justified, then PostgreSQL only when concurrent or deployed workloads require it.

## 11. CLI Workflow

The milestone exposes:

```text
gemini-trading market-data ingest
gemini-trading market-data replay
gemini-trading market-data verify
```

### 11.1 Ingest

Inputs:

- provider;
- symbol and explicit base/quote identity;
- interval;
- UTC start and end;
- configurable storage root.

Safe output includes:

- retrieval-run ID;
- run status;
- raw-page count;
- canonical candle count;
- dataset ID;
- manifest and provenance paths;
- safe failure reason.

The CLI never prints unrestricted raw responses or sensitive environment values.

### 11.2 Replay

`replay` rebuilds canonical output from preserved raw pages without external network access. Replaying the same valid raw evidence under the same schema version must reproduce identical canonical bytes, dataset manifest, and dataset ID. It also verifies or recreates the matching provenance receipt without changing canonical content.

### 11.3 Verify

`verify` checks:

- raw page hashes;
- retrieval-manifest linkage;
- canonical file hash;
- dataset identity;
- deterministic dataset-manifest content;
- provenance-receipt linkage;
- candle order and continuity;
- completed-candle guarantees.

Any failure returns a non-zero process exit code.

## 12. Testing Strategy

### 12.1 Unit tests

Unit tests cover:

- instrument and timeframe validation;
- UTC enforcement;
- decimal preservation;
- provider-record normalization;
- candle geometry;
- duplicate, order, and gap detection;
- immutable conflict handling;
- deterministic serialization and hashing;
- deterministic manifest generation;
- provenance receipt isolation;
- retry classification;
- pagination cursor behavior.

### 12.2 Property tests

Hypothesis verifies:

- valid candles survive serialization and deserialization unchanged;
- invalid OHLC geometry is rejected;
- reordered candles cannot silently pass;
- duplicate timestamps are rejected;
- changing one canonical value changes the dataset hash;
- identical candle sequences produce identical bytes and IDs;
- changing retrieval-run metadata does not change canonical bytes or dataset ID;
- naive or non-UTC timestamps never enter the canonical layer.

### 12.3 Provider-contract tests

The Binance adapter must satisfy the generic provider contract:

- exact raw response preservation;
- curated interval enforcement;
- bounded window behavior;
- forward-only pagination;
- provider error classification;
- one server-time snapshot per run;
- no storage or canonical-dataset responsibilities.

### 12.4 Recorded-response integration tests

Sanitized public Binance fixtures cover:

- one valid page;
- multiple pages;
- final incomplete candle;
- duplicate records across pages;
- internal gap;
- malformed record shape;
- invalid decimal value;
- rate limiting;
- transient failure followed by success;
- retry exhaustion;
- raw-storage conflict;
- two retrieval runs producing one canonical dataset with separate provenance receipts.

Ordinary CI does not depend on internet availability.

### 12.5 Live smoke test

A separate non-default smoke test may confirm public API accessibility and response shape for a small completed window. It is excluded from deterministic CI and never provides credentials.

### 12.6 Acceptance case

The first end-to-end acceptance case ingests a fixed historical `ETHUSDT` `4h` window in research mode and proves:

- immutable raw pages are written;
- the retrieval manifest is complete;
- canonical output contains only completed candles;
- output is ordered and gap free;
- decimals remain exact strings;
- the dataset ID is a valid SHA-256 content identity;
- replay reproduces identical canonical bytes, manifest, and identity;
- provenance remains linked without contaminating canonical identity;
- replay requires no network.

The implementation remains generic and must contain no ETH-specific validation, pagination, storage, or hashing logic.

### 12.7 Negative acceptance cases

No canonical dataset is emitted when:

- a required page is missing;
- retries are exhausted;
- an internal gap exists;
- timestamps are duplicated or out of order;
- an immutable raw identity conflicts;
- a provider response is malformed;
- the requested window is invalid;
- zero completed candles are available;
- completed-candle window requirements cannot be satisfied.

## 13. Milestone Trust Gates

The milestone is accepted only when:

1. all deterministic tests pass on Python 3.12;
2. Pyright strict mode reports zero errors;
3. Ruff and all pre-commit hooks pass;
4. CI `quality` and `gitleaks` pass;
5. canonical output is reproducible byte for byte;
6. no incomplete candle reaches canonical output;
7. preserved raw evidence reconstructs canonical output;
8. independent retrieval provenance does not change dataset identity;
9. storage implementation does not alter canonical results;
10. unsafe execution modes remain rejected;
11. no profitability claim is made from this milestone alone.

## 14. Completion Condition

The Market Data Core milestone is complete when a user can fetch, preserve, replay, and independently verify a bounded Binance Spot candle dataset, while malformed, incomplete, conflicting, or partially retrieved runs fail closed without emitting a trusted canonical dataset.
