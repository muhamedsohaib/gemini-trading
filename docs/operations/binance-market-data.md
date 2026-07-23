# Binance Market Data Operator Guide

## Scope and safety

This interface retrieves and verifies public Binance Spot candle data. It is research and paper only. Live mode is rejected before provider construction, and the package contains no private endpoint, credential, signal, order, or exchange-submission workflow.

The Market Data Core establishes deterministic data integrity and reproducibility. It does not establish strategy profitability.

## Supported intervals

The accepted intervals are:

- `1m`
- `5m`
- `15m`
- `1h`
- `4h`
- `1d`
- `1w`

Every retrieval uses an explicit bounded `[start, end)` window. Ingest timestamps must be UTC ISO-8601 values ending in `Z`.

A candle is accepted as completed only when:

```text
close_time < server_time
```

A candle ending exactly at the server-time snapshot is not complete.

## Install and inspect commands

```powershell
uv sync --all-groups --frozen
uv run gemini-trading --help
uv run gemini-trading market-data --help
```

Operational commands emit one compact JSON object. Successful output contains only safe identifiers, counts, verification checks, and paths relative to the configured output root. Failure output contains a safe error type and message with exit code 2. Tracebacks, raw response bodies, environment dumps, credentials, and absolute operator paths are not printed.

## Ingest a bounded window

```powershell
uv run gemini-trading market-data ingest `
  --symbol ETHUSDT `
  --base-asset ETH `
  --quote-asset USDT `
  --interval 4h `
  --start 2025-01-01T00:00:00Z `
  --end 2025-01-02T00:00:00Z `
  --output-root .
```

Required ingest arguments:

- `--symbol`
- `--base-asset`
- `--quote-asset`
- `--interval`
- `--start`
- `--end`
- `--output-root`

The CLI validates the arguments and runtime policy before constructing `BinanceSpotProvider`.

## Storage layout

Raw response bytes, page metadata, and the retrieval manifest are stored beneath:

```text
data/raw/binance_spot/<run_id>/
```

Canonical JSONL, the deterministic dataset manifest, and run-specific provenance receipts are stored beneath:

```text
data/canonical/<dataset_id>/
```

The canonical schema version is `candle-dataset-v1`. Dataset identity is:

```text
sha256(utf8(schema_version) + b"\n" + canonical_jsonl_bytes)
```

Run IDs, page hashes, retrieval hashes, linkage state, and receipt timestamps do not contaminate canonical identity.

## Replay stored evidence

```powershell
uv run gemini-trading market-data replay `
  --run-id <run_id> `
  --output-root .
```

Replay performs no network access. It verifies canonical retrieval-manifest bytes, recomputes every raw response SHA-256, validates the preserved Binance request metadata and page cursor chain, then reuses the production normalizer, completion filter, sequence validator, and deterministic writer.

Equivalent valid retrieval runs reproduce identical canonical JSONL, deterministic manifest bytes, and dataset ID while retaining separate provenance receipts.

## Independently verify a dataset

```powershell
uv run gemini-trading market-data verify `
  --dataset-id <dataset_id> `
  --run-id <run_id> `
  --output-root .
```

Verification recomputes:

- persisted raw response hashes;
- canonical retrieval-manifest encoding and hash;
- raw-to-canonical reconstruction;
- canonical JSONL encoding and SHA-256;
- deterministic dataset ID and manifest bytes;
- provenance linkage;
- candle continuity and completed state.

Missing, altered, partial, malformed, duplicated, reversed, or gapped evidence fails closed.

## Optional bounded public smoke test

The public Binance smoke test is disabled by default. It uses no credentials, requests only a small old completed window, and writes beneath pytest temporary storage.

PowerShell:

```powershell
$env:GEMINI_TRADING_RUN_LIVE_API_TESTS=1
uv run pytest tests/live/test_binance_spot_smoke.py -m live_api -q
Remove-Item Env:GEMINI_TRADING_RUN_LIVE_API_TESTS
```

The enabling variable is `GEMINI_TRADING_RUN_LIVE_API_TESTS=1`.

This smoke test checks public response compatibility only. It does not authorize live trading or exchange submission.

## Failure handling and known boundaries

The ingestion path validates all completed candles before canonical publication. Provider, parsing, retry, completion, sequence, immutable-conflict, replay, and verification failures stop safely.

The raw and canonical stores are separate immutable interfaces. They do not currently provide shared cross-store rollback after publication begins. A storage failure may therefore leave valid but incomplete artifacts. Verification detects missing or inconsistent publication files and refuses to trust them, but it cannot erase files already written.

`RawPage.retrieved_at` and `DatasetProvenance.created_at` are informational timestamps. Their format and ordering are validated, but they are not externally signed and cannot prove time authenticity against an independent authority. They do not affect canonical JSONL or dataset identity.

Database-backed ingestion is deferred under issue #7. The required per-task, checkpoint, and exact-head verification protocol is tracked under issue #8.
