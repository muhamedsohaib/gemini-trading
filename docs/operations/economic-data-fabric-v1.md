# Economic Data Fabric v1 Operations Guide

## Status

Economic Data Fabric v1 is a `RESEARCH_ONLY`, provider-neutral evidence and dataset layer for Gemini Trading's Economic Forecasting v1 program.

This milestone proves that heterogeneous economic observations can be represented, sealed, replayed, verified, and queried historically without allowing revised or not-yet-public information to leak into earlier model states.

It does **not** introduce model training, forecast generation, broker/exchange execution, capital allocation, leverage, or autonomous trading authority.

## Proven scope

The v1 contract is exercised with deterministic synthetic fixtures covering:

- a non-revisioned market series;
- a revisioned monthly macroeconomic series;
- multiple raw source receipts;
- multiple vintages for one macro reference period;
- immutable content-addressed dataset identity;
- point-in-time visibility using `available_time`;
- provider-free replay;
- independent integrity verification.

The synthetic fixtures prove the platform contract. They are not claims about the quality or availability of any future real-world provider.

## Bundle layout

Each sealed economic dataset is a directory with this logical structure:

```text
economic-bundle/
├── raw/
│   └── <source_id>/
│       └── <receipt_id>.bin
├── registry/
│   └── series.jsonl
├── canonical/
│   └── observations.jsonl
├── inventory/
│   └── raw-evidence.jsonl
└── manifest.json
```

The bundle contains the bytes needed to reproduce and verify the dataset without contacting the original provider.

### `raw/`

Exact immutable provider-response or fixture bytes. Each file is identified by a receipt containing its source identity, relative path, byte length, and SHA-256 digest.

### `registry/series.jsonl`

Canonical semantic definitions for every series represented in the dataset, including domain, unit, scale, frequency, observation semantics, availability semantics, and revision policy.

### `canonical/observations.jsonl`

Deterministically serialized observations. Decimal values remain exact decimal strings and timestamps are normalized to millisecond-resolution UTC `Z` text.

### `inventory/raw-evidence.jsonl`

Canonical inventory of raw evidence receipts. Its own byte representation is content-addressed and participates in dataset identity.

### `manifest.json`

The immutable dataset identity and high-level bounds: component digests, counts, and observation/availability time ranges.

## Time semantics

Every canonical economic observation has distinct time concepts.

- `observation_time`: the economic or market period the value describes.
- `available_time`: the first timestamp at which the value is allowed to enter a historical information set.
- `vintage_time`: the source vintage/revision timestamp when applicable.
- `retrieved_time`: when the system captured the evidence.

The historical visibility rule is deliberately simple and strict:

```text
visible_at(cutoff) ⇔ available_time <= cutoff
```

`retrieved_time`, `vintage_time`, file modification time, and present-day knowledge may not substitute for `available_time`.

A naive/timezone-free cutoff is rejected.

## Revision example

Assume a monthly activity index describes January 2026.

```text
January reference period
  initial value: 100.0
  available:     2026-02-05 12:00 UTC

January revision
  revised value: 101.0
  available:     2026-03-05 12:00 UTC
```

A historical query with cutoff `2026-02-20` must return `100.0`.

A historical query with cutoff `2026-03-10` may return `101.0` as the latest visible vintage.

At `2026-03-05 11:59:59.999999 UTC`, the revised value remains invisible. The system does not backfill revised data into earlier states.

If two competing vintages for the same series/reference period share the same latest `available_time`, the latest-vintage query fails closed rather than choosing arbitrarily.

## Dataset identity

The dataset ID is a SHA-256 digest over a canonical identity payload binding:

- canonical observation bytes SHA-256;
- series registry bytes SHA-256;
- raw evidence inventory root SHA-256;
- observation count;
- series count;
- minimum and maximum `observation_time`;
- minimum and maximum `available_time`;
- dataset schema version.

Therefore economically meaningful changes produce a different dataset identity. This includes changes to an observation value, an availability timestamp, registry semantics, or raw evidence inventory identity.

Input ordering does not change dataset identity because observations, series definitions, and raw receipts are canonicalized before hashing.

## Raw evidence rules

Raw evidence is immutable.

Writing the same bytes to the same receipt identity is idempotent. Attempting to write different bytes under the same immutable receipt path fails closed.

Every observation's `raw_sha256` must be present in the dataset's declared raw evidence inventory. A dataset containing an observation with no closing raw evidence is rejected.

Paths are constrained to safe provider/receipt path segments.

## Provider-free replay

`replay_economic_bundle(root)` reconstructs the dataset from sealed bundle bytes only.

Replay does not require the original provider client. It reloads registry definitions, canonical observations, raw inventory, and raw evidence, then recomputes dataset identity and requires the recomputed state to match the sealed manifest.

Tampering with raw bytes, observation values, `available_time`, registry semantics, inventory digests, manifest identity, or required files causes replay to fail.

## Independent verification

`verify_economic_bundle(root)` performs a second integrity walk after replay.

It independently checks:

- registry bytes against the manifest registry digest;
- canonical observation bytes against the manifest observation digest;
- raw inventory bytes against the manifest inventory root;
- actual raw files against the declared raw-file inventory;
- undeclared raw files;
- missing raw files;
- raw byte lengths;
- raw SHA-256 digests.

Verification returns the verified immutable dataset manifest only after these checks succeed.

## Operator sequence

For a future real provider adapter, the intended sequence is:

1. capture exact raw source bytes;
2. assign immutable source/receipt identity;
3. store raw evidence and receipt;
4. parse provider data into provider-neutral `EconomicObservation` rows;
5. assign truthful `observation_time`, `available_time`, vintage metadata, and retrieval time;
6. bind each observation to exact raw evidence through `raw_sha256`;
7. validate against the canonical series registry;
8. build the content-addressed dataset;
9. write the immutable bundle;
10. replay provider-free;
11. independently verify;
12. only then expose the dataset to downstream research code through as-of queries.

## Failure policy

Economic Data Fabric v1 fails closed when chronology, semantics, evidence, canonical bytes, content identity, or verification cannot be established exactly.

Missing or ambiguous evidence is not converted into a guessed value. Revision conflicts are not silently resolved. A failed replay or verification invalidates that bundle for downstream research use.

## Research boundary

Economic Data Fabric v1 remains `RESEARCH_ONLY`.

It does not authorize:

- live, demo, or paper order submission;
- exchange credentials or private endpoints;
- autonomous capital movement;
- leverage, shorting, futures, or options;
- portfolio allocation;
- production trading decisions.

## Next milestone

The next data milestone is a **separately specified, vintage-aware real provider adapter** that satisfies this exact contract and preserves historical availability semantics from authoritative source evidence.

That adapter must be preregistered and tested against provider-specific release/revision behavior before real data is admitted.

**Model training is not the next step.** Forecast-model work begins only after at least one real economic source can produce independently replayable, point-in-time-correct datasets under this contract.
