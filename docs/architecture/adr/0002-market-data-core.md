# ADR 0002 — Verified Market Data Core

## Status

Accepted for the Market Data Core milestone.

## Context

Gemini Trading requires market-data evidence that can be replayed and independently verified without trusting mutable provider responses, local implementation details, or an active network connection. The system remains research and paper only. Live mode is rejected, exchange submission is disabled, and this work establishes data integrity and reproducibility; it does not establish strategy profitability.

The first provider adapter is Binance Spot public REST. Retrievals are explicit bounded windows using `[start, end)`, one instrument, and one supported interval per run. Supported intervals are defined by the domain model rather than hard-coded acceptance markets.

## Decision

The Market Data Core uses the following architecture:

1. Fetch public Binance Spot server time once per retrieval.
2. Retrieve raw kline response bytes in deterministic forward pages.
3. Persist every raw response and its request metadata before normalization.
4. Normalize with exact integer-millisecond timestamp conversion and `Decimal` values.
5. Retain only candles satisfying `close_time < server_time`.
6. Validate identity, window containment, completion, duplicates, order, and exact continuity.
7. Serialize canonical candles as compact deterministic UTF-8 JSONL.
8. Derive dataset identity as:

```text
sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)
```

The implemented schema version is `candle-dataset-v1`.

Raw retrieval evidence is stored beneath:

```text
data/raw/binance_spot/<run_id>/
```

Canonical content and deterministic manifests are stored beneath:

```text
data/canonical/<dataset_id>/
```

Run-specific provenance is separate from canonical identity. Equivalent valid retrievals therefore produce the same canonical bytes and dataset ID while retaining distinct provenance receipts.

Offline replay uses only persisted evidence and shared normalization, completion, validation, and canonical-writing code. Replay performs no network access. Independent verification recomputes raw page hashes, retrieval-manifest bytes and hash, canonical bytes and hash, dataset identity, deterministic manifest bytes, provenance linkage, continuity, and completed state.

The safe command surface is:

```text
gemini-trading market-data ingest
gemini-trading market-data replay
gemini-trading market-data verify
```

Operational output is compact safe JSON. Raw provider bodies, environment dumps, credentials, tracebacks, and absolute operator paths are not emitted.

## Safety and scope

The runtime is research and paper only. Live mode is rejected before a network provider is constructed. No private Binance endpoints, API credentials, strategy logic, signal generation, order construction, or exchange submission are included.

Database-backed ingestion is deferred under issue #7. The current milestone uses the immutable local filesystem adapter so the evidence model, deterministic identity, replay, and verification contracts can be proven before introducing a database implementation.

The mandatory task-by-task and exact-head verification protocol is tracked under issue #8.

## Consequences

### Positive

- Raw provider evidence remains available for audit and reconstruction.
- Canonical content identity is independent of run IDs, timestamps, and storage adapter details.
- Equivalent runs can be compared by deterministic dataset ID.
- Replay and verification operate without provider availability.
- Incomplete, malformed, duplicated, reversed, or gapped candle sequences fail closed.

### Limitations

- Separate raw and canonical stores do not provide shared cross-store rollback after publication has begun. Verification detects missing or inconsistent artifacts but cannot undo already-published files.
- Retrieval and provenance creation times are informational timestamps rather than externally signed timestamps.
- The local filesystem adapter is the only operational storage adapter in this milestone.
- Optional public live smoke testing is bounded and disabled unless `GEMINI_TRADING_RUN_LIVE_API_TESTS=1` is explicitly set.
- The evidence proves data integrity and reproducibility only; it does not establish strategy profitability.
