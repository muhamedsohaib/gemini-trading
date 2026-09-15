# Economic Data Fabric v1 Design

Status: APPROVED PROGRAM SUBSYSTEM DESIGN
Date: 2026-09-15
Parent: `docs/architecture/economic-forecasting-source-of-truth.md`
Boundary: RESEARCH_ONLY

## Objective

Build the first provider-neutral point-in-time economic data contract for Gemini Trading so every later forecast can prove exactly what information was available at its forecast origin.

This milestone does not add a forecasting model, provider integration, trading signal, or execution authority. It establishes chronology, content identity, immutable evidence, as-of visibility, replay, and independent verification.

## Why This Comes First

A sophisticated forecaster trained on revised or temporally leaked economic data is scientifically invalid. The Economic Data Fabric therefore treats time-of-availability and vintage identity as first-class data rather than metadata added after modeling.

The milestone is intentionally independent of Candidate v0.4. v0.4 remains frozen and may not consume this data.

## Package Boundary

Create a new namespace beside the existing candle-oriented data stack:

```text
src/gemini_trading/economics/
  __init__.py
  data/
    __init__.py
    observation.py
    series.py
    serialization.py
    dataset.py
    asof.py
    storage.py
    replay.py
    verification.py
```

The existing `gemini_trading.data` package remains unchanged unless a version-neutral utility is demonstrably reusable without altering historical candle identities.

This isolation prevents the new program from destabilizing Candidate v0.1-v0.4 evidence contracts.

## Core Observation Contract

`EconomicObservation` is immutable and provider-neutral.

Required fields:

- `schema_version`: exactly `economic-observation-v1`;
- `series_id`: stable canonical identifier, for example `macro.us.cpi.all_items.index`;
- `observation_time`: timestamp/period anchor the value describes;
- `available_time`: earliest instant this exact value could have been known to a contemporaneous observer;
- `vintage_time`: optional source-declared vintage/release timestamp; it is descriptive and never overrides `available_time`;
- `retrieved_time`: instant the system captured the raw evidence;
- `source_id`: provider/source contract identifier;
- `value`: finite `Decimal`;
- `unit`: stable unit identifier;
- `scale`: finite nonzero `Decimal` representing the canonical scaling factor;
- `frequency`: stable frequency identifier;
- `release_id`: optional source release identifier;
- `raw_sha256`: SHA-256 of exact raw evidence bytes that support the observation.

Chronology rules:

- all datetimes are timezone-aware and canonicalized to UTC;
- `available_time >= observation_time` is required for v1;
- `retrieved_time >= available_time` is required;
- when present, `vintage_time <= retrieved_time` is required;
- the same `(series_id, observation_time, available_time, source_id, release_id)` identity may not map to two different values within one canonical dataset;
- a later revision is a new observation row with a later `available_time`, never an overwrite.

The `available_time` field is the sole visibility authority for as-of queries.

## Series Registry

`EconomicSeriesDefinition` freezes semantic meaning independently of providers.

Required fields:

- `schema_version`: `economic-series-v1`;
- `series_id`;
- `title`;
- `domain`: one of `MARKET`, `MACRO`, `EVENT`, `ALTERNATIVE`;
- `unit`;
- `scale`;
- `frequency`;
- `observation_semantics`;
- `availability_semantics`;
- `revision_policy`: `NONE`, `REVISIONED`, or `SOURCE_DEPENDENT`.

Series definitions serialize canonically and are content-addressed. A dataset binds the exact registry bytes it used.

## Canonical Serialization

Serialization must be deterministic across machines and executions.

Rules:

- UTF-8;
- compact JSON Lines for observations;
- canonical key order supplied by explicit payload construction, not incidental dataclass order;
- datetimes encoded as UTC ISO-8601 with millisecond precision and `Z`;
- `Decimal` values encoded as non-scientific strings;
- rows sorted by `(series_id, observation_time, available_time, source_id, release_id-or-empty, raw_sha256)`;
- duplicate canonical row identities fail closed;
- non-finite values fail closed.

`canonical_json_bytes()` may be reused from the existing research serialization module if its byte contract is already stable and tests prove no change to existing behavior.

## Dataset Identity

`EconomicDatasetManifest` schema is exactly `economic-dataset-v1`.

The dataset ID is SHA-256 over canonical JSON binding:

- schema version;
- canonical observations SHA-256;
- series-registry SHA-256;
- raw-evidence inventory-root SHA-256;
- observation count;
- unique series count;
- minimum and maximum observation times;
- minimum and maximum available times.

The manifest also records these fields explicitly for inspection.

No retrieval timestamp is allowed to alter the identity of an already captured immutable bundle. Retrieval time belongs inside the observation rows/raw receipts that were actually captured.

## Raw Evidence Inventory

v1 uses a provider-neutral immutable inventory instead of implementing provider clients.

Each raw evidence item contains:

- `source_id`;
- caller-supplied stable `receipt_id`;
- byte length;
- SHA-256;
- relative immutable storage path.

Inventory entries sort deterministically. The inventory root is SHA-256 of canonical inventory bytes.

Two writes to the same immutable path with different bytes fail closed. Idempotent same-byte writes succeed.

## As-Of Visibility

The critical API is conceptually:

```python
visible = dataset.as_of(cutoff)
```

It returns only observations with `available_time <= cutoff`.

For a single series/reference period with multiple revisions, consumers may additionally request the latest visible vintage as of the cutoff. "Latest" means greatest `available_time` not exceeding the cutoff, with deterministic tie rejection rather than arbitrary selection.

No API in v1 may fall back to the chronologically latest row in the full dataset when an as-of cutoff is supplied.

## Replay

Replay is provider-free.

Given an immutable bundle containing raw evidence, series registry, canonical observations, and manifest, replay must:

1. validate every raw-evidence digest;
2. load and validate the exact registry;
3. load observations and validate row chronology/types;
4. reproduce canonical observation bytes;
5. recompute the raw inventory root;
6. recompute the dataset manifest and dataset ID;
7. compare all required canonical bytes/identities.

v1 does not attempt to reparse arbitrary provider payloads because no provider adapter is part of this milestone. Provider-specific semantic replay begins with the first provider integration and must extend, not weaken, this contract.

## Independent Verification

Verification must be callable without network/provider access and must fail on:

- raw byte tamper;
- observation value tamper;
- `available_time` tamper;
- series-definition tamper;
- missing raw receipt;
- inventory-root mismatch;
- dataset-ID mismatch;
- duplicate conflicting row identity;
- non-UTC/naive chronology input;
- an observation referencing a `raw_sha256` not present in the inventory.

## Storage Layout

A bundle root has exactly the following logical layout:

```text
raw/
  <source_id>/<receipt_id>.bin
registry/
  series.jsonl
canonical/
  observations.jsonl
inventory/
  raw-evidence.jsonl
manifest.json
```

Paths are relative to a caller-provided root. Path traversal outside the root is rejected.

## Initial Scope

v1 proves the contract with deterministic fixtures representing:

- a non-revisioned market series;
- a revisioned monthly macro series with at least two vintages for one reference period;
- multiple series in one dataset;
- an as-of cutoff before and after a revision.

These fixtures are synthetic. No economic provider or live network call is introduced.

## Explicit Non-Goals

This milestone does not include:

- FRED/ALFRED or any other provider client;
- real market-data provider expansion;
- economic calendar ingestion;
- text/news ingestion;
- feature engineering;
- target construction;
- forecast models;
- Economic State Vector construction;
- model leaderboard logic;
- trading integration;
- paper/live execution.

Each is a later governed subsystem.

## Testing Requirements

Every production behavior is introduced test-first.

Required test groups:

- observation validation and chronology;
- series-definition serialization;
- deterministic canonical observation ordering;
- dataset identity repeatability;
- immutable raw storage conflicts/idempotency;
- as-of no-leakage behavior;
- latest-visible-vintage behavior;
- replay exactness;
- tamper rejection;
- path traversal rejection;
- prior candle dataset regression suite remains unchanged.

## Security and Governance

`RESEARCH_ONLY` remains mandatory.

The subsystem stores public/research evidence only. It introduces no credentials, private endpoints, execution capability, strategy parameter changes, or capital authority.

## Acceptance Criteria

Economic Data Fabric v1 is complete only when:

1. its full focused tests pass;
2. strict Pyright and Ruff pass;
3. the full repository test/build/security gate passes;
4. a synthetic revisioned series proves that a pre-revision as-of query cannot see the revised value;
5. replay reproduces the exact dataset ID without network access;
6. independent verification rejects every defined tamper class;
7. existing candle dataset identities and Candidate v0.1-v0.4 behavior are unchanged.

After this milestone, the next separate design is the first real provider adapter plus vintage-aware acquisition workflow.
