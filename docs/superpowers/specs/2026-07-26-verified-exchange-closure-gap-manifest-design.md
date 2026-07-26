# Verified Exchange-Closure Gap Manifest Design

## Status

- Design gate: GitHub Issue #22
- Operator authorization: `APPROVE VERIFIED EXCHANGE-CLOSURE GAP MANIFEST`
- Repository: `muhamedsohaib/gemini-trading`
- Design branch: `design/verified-exchange-closure-gap-manifest`
- Safety level: `RESEARCH_ONLY`
- Execution authority: none
- Stage 2 status: prohibited until a new Stage 1 artifact is verified and explicitly approved

## Objective

Revise the sealed BTCUSDT historical-validation pipeline so it can preserve the fixed Binance Spot `BTCUSDT` 4-hour window while representing verified exchange closures without inventing market data.

The pipeline must continue to fail closed. It may accept a discontinuity only when the discontinuity exactly matches a source-controlled, identity-bound closure declaration. Every undeclared, malformed, mismatched, overlapping, unused, or tampered declaration remains fatal.

## Fixed scope retained

The following approved identities do not change:

- provider: public Binance Spot market data;
- instrument: `BTCUSDT`;
- interval: `4h`;
- window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`;
- completed candles only;
- strategy: `candidate.multi_model.v0_1`;
- locked strategy configuration;
- final untouched test: last 18 calendar months;
- runtime mode: `GEMINI_TRADING_MODE=research`;
- long-or-cash position states;
- final-test access and second-access protections;
- all result semantics and safety limitations.

No change in this design authorizes paper, demo, live, production, order submission, exchange credentials, leverage, futures, shorting, portfolio allocation, or real capital.

## Confirmed closure

The first approved closure declaration is fixed as:

- prior returned candle open: `2018-02-08T00:00:00Z`;
- missing interval start, inclusive: `2018-02-08T04:00:00Z`;
- resumed candle open, exclusive end of missing interval: `2018-02-09T08:00:00Z`;
- missing 4-hour candle count: `7`;
- reason code: `exchange_system_upgrade`.

The declaration represents unavailable trading intervals. It does not create substitute candles and does not assert prices, volume, returns, fills, or position changes during the closure.

## Alternatives considered

### 1. Shorten the historical window

Starting the study after the 2018 closure would restore strict continuity but would change the approved historical scope and reduce early development history. This approach is rejected.

### 2. Insert synthetic zero-volume or filled candles

Creating candles would make the time grid continuous but would manufacture prices, volume, returns, indicators, labels, and potentially trading decisions. This approach is rejected.

### 3. Verified exchange-closure gap manifest

Retain the authentic returned candles, preserve the fixed request window, explicitly declare verified closures, segment calculations at each closure, and bind the declaration into dataset identity and verification. This is the approved approach.

## Architecture

### Component 1: Source-controlled closure manifest

Add one canonical JSON manifest at a fixed repository path. The Stage 1 workflow must use that exact path and must not accept a dispatch input, environment override, arbitrary file path, or remote manifest.

The manifest schema contains:

- schema version;
- provider identity;
- instrument identity;
- timeframe;
- fixed request start and end;
- ordered closure entries.

Each closure entry contains:

- stable closure ID;
- missing interval start, inclusive;
- resumed candle open, exclusive end;
- expected missing candle count;
- reason code;
- governance reference to Issue #22.

The manifest uses canonical JSON encoding, deterministic field order, UTC timestamps, and no informational timestamp that could alter identity between equivalent runs.

### Component 2: Exact gap validation

Strict continuity remains the default when no closure manifest is supplied.

When the fixed closure manifest is supplied, validation must:

1. validate provider, instrument, timeframe, and request-window identity;
2. require entries to be ordered, unique, internal to the request window, timeframe-aligned, non-overlapping, and non-touching;
3. derive every observed discontinuity from adjacent returned candle opens;
4. require each observed discontinuity to match exactly one declared interval;
5. recompute and verify the declared missing-candle count;
6. require every declared interval to be observed exactly once;
7. reject any additional, partial, shifted, expanded, contracted, or unused declaration;
8. continue all existing candle geometry, ordering, duplication, completion, instrument, timeframe, and window checks.

No validation path may synthesize, remove, reorder, or modify a provider candle.

### Component 3: Deterministic segment manifest

After gap validation, derive continuous candle segments. A segment is a maximal ordered candle sequence with exact 4-hour continuity.

Persist a deterministic segment manifest containing, for every segment:

- segment number;
- first global candle index;
- end global candle index, exclusive;
- first candle open;
- last candle open;
- candle count;
- preceding closure ID, or null for the first segment.

The segment manifest is derived from canonical candles plus the approved closure manifest. It is not operator-authored and cannot override the observed data.

### Component 4: Dataset identity version 2

Bump the canonical dataset schema to `candle-dataset-v2`.

The dataset identity must bind:

- canonical candle bytes;
- canonical closure-manifest bytes;
- canonical segment-manifest bytes;
- provider, instrument, timeframe, and fixed window.

Use a deterministic canonical identity payload containing the SHA-256 digest of each byte stream and the stable scope fields. The dataset ID is the SHA-256 digest of that canonical identity payload.

The dataset manifest must expose:

- canonical candle SHA-256;
- closure-manifest SHA-256;
- segment-manifest SHA-256;
- segment count;
- closure count;
- existing dataset scope and candle-count fields.

A v1 dataset cannot be treated as a v2 dataset, and Stage 2 must reject schema-version mismatch.

### Component 5: Storage, replay, and independent verification

Stage 1 stores the closure manifest and derived segment manifest alongside the canonical JSONL and existing evidence.

Provider-free replay must reconstruct the returned candles from raw pages, reapply the exact approved closure manifest, rederive segments, and reproduce byte-identical canonical data, manifests, and dataset ID.

Independent verification must separately:

- parse and validate both manifests;
- verify their inventory hashes;
- rerun exact gap matching;
- rederive every segment;
- recompute the v2 dataset identity;
- confirm replay and persisted evidence agree.

The verification report replaces the generic `parsed_continuity` claim with explicit checks for `declared_gap_exactness` and `segment_continuity`.

### Component 6: Stage 1 handoff contract

The deterministic handoff manifest must add:

- dataset schema version;
- closure-manifest relative path and SHA-256;
- segment-manifest relative path and SHA-256;
- closure count;
- segment count;
- closure IDs.

The artifact inventory includes both files. Stage 2 rejects missing files, extra unsupported identity fields, hash mismatch, path traversal, schema mismatch, closure mismatch, or a handoff that does not classify replay and independent verification as successful.

### Component 7: Segment-safe feature and label generation

Features and labels must never cross a closure boundary.

Feature generation operates independently within each segment while preserving global candle indices. For every segment:

- feature state starts empty;
- indicators and trailing statistics use only candles from that segment;
- no row is eligible until the locked feature registry's `maximum_lookback_candles` requirement is satisfied within the segment;
- a decision index is excluded when its label exit lies in another segment.

There is no new configurable warm-up parameter. The warm-up is derived only from the locked feature registry and the existing fixed label horizon.

### Component 8: Segment-safe strategy state

At every segment start:

- position state is reset to cash;
- pending entry or exit state is cleared;
- cooldown and holding-duration state are reset;
- no return, trade, fill, fee, slippage, stop, or label is attributed across the closure;
- the first eligible decision occurs only after the segment-local feature warm-up.

This creates independent continuous evaluation segments inside one fixed-window dataset. It does not assume an executable liquidation during the exchange closure and does not carry a marked position across unavailable market data.

### Component 9: Chronological splits and final-test seal

The chronological split plan must accept the derived segment boundaries as protected boundaries in addition to fold and final-test boundaries.

The split builder must:

- preserve the existing calendar-based fold and final-test dates;
- permit multiple continuous segments in the dataset;
- prevent labels from crossing segment boundaries;
- exclude post-gap warm-up rows through feature eligibility;
- include segment boundaries in the split-plan identity;
- reject any closure that intersects the final 18-month partition unless separately approved by a new design gate.

The known 2018 closure is entirely before the final-test partition, so it does not expose final-test values or modify the final-test date.

## Data flow

```text
Public Binance Spot responses
        |
        v
Immutable raw pages
        |
        v
Canonical normalization
        |
        +---- fixed source-controlled closure manifest
        |
        v
Exact gap validation
        |
        v
Derived continuous segments
        |
        v
Canonical candles + closure manifest + segment manifest
        |
        v
Version-2 dataset identity
        |
        v
Provider-free replay and independent verification
        |
        v
Identity-bound Stage 1 handoff artifact
        |
        v
Segment-local features, labels, and state
        |
        v
Protected chronological folds and sealed final test
```

## Failure handling

The pipeline fails closed when:

- a provider gap is undeclared;
- a declared gap is absent from returned data;
- observed or declared boundaries differ by any amount;
- missing-candle count is incorrect;
- entries overlap, touch, are unsorted, duplicate, misaligned, or outside the fixed window;
- a manifest path or hash differs;
- segment derivation differs during replay or verification;
- any feature, label, state, return, or split crosses a segment boundary;
- Stage 2 receives a v1 artifact or a mismatched v2 handoff;
- a future closure touches the final-test partition without a new explicit design gate.

A provider later backfilling the declared interval also fails closed because the declaration would become unused. That condition requires review and a new exact Stage 1 commit rather than silent acceptance.

## Repository changes

Implementation is limited to focused surfaces:

- one fixed canonical closure-manifest JSON file;
- closure and segment domain contracts and deterministic serialization;
- gap-aware validation while preserving strict default behavior;
- ingestion, replay, canonical storage, and independent verification;
- dataset-manifest schema v2 and identity computation;
- Stage 1 handoff fields and workflow packaging;
- segment-safe feature, label, state, and split handling;
- operator documentation;
- unit, integration, tamper, acceptance, and workflow-contract tests.

No model, feature definition, threshold, cost, gate, comparator, final-test date, or unrelated architecture is changed.

## Testing strategy

### Unit tests

Cover:

- canonical closure-manifest parsing and serialization;
- exact known-gap acceptance;
- strict rejection without a manifest;
- undeclared, shifted, partial, extra, overlapping, touching, unused, and misaligned gaps;
- deterministic segment derivation;
- v2 dataset identity and manifest bytes;
- manifest and segment hash tampering;
- segment-local feature warm-up;
- labels and state unable to cross a closure;
- position and cooldown reset at segment start;
- split-plan segment-boundary protection.

### Integration tests

Use synthetic multi-segment fixtures to prove:

- Stage 1-like ingestion persists authentic candles without inserted rows;
- replay reproduces byte-identical v2 evidence;
- independent verification recomputes gap and segment claims;
- handoff packaging and unpacking preserve all identities;
- Stage 2 accepts only an exact verified v2 artifact;
- feature, label, strategy, and split outputs contain no cross-segment dependency.

### Real bounded smoke test

After protected merge and complete CI, run the manual Stage 1 workflow from the exact merged `main` commit.

The run must:

- observe exactly the approved seven-candle closure;
- find no additional undeclared gaps;
- complete replay and independent verification;
- upload one v2 artifact.

The artifact must then be downloaded and independently reviewed before Issue #22 receives the exact dataset approval marker. Stage 2 remains prohibited until that marker exists.

## Security and authority

- public market-data endpoints only;
- no credentials or private exchange endpoints;
- no arbitrary manifest inputs;
- no generated candles;
- no change to strategy execution authority;
- no final-test access during implementation or Stage 1;
- complete existing Ruff, Pyright, pytest, build, pip-audit, tracked-file policy, detect-secrets, and Gitleaks gates;
- every implementation correction requires a new exact commit and complete Stage 1 repetition.

## Success criteria

The revision is successful only when all of the following are true:

1. the fixed historical window is retained;
2. no candle is fabricated or altered;
3. the known closure is matched exactly and identity-bound;
4. all other gaps remain fatal;
5. replay and independent verification reproduce the same v2 dataset ID;
6. features, labels, state, returns, folds, and final-test access cannot cross a segment boundary;
7. the Stage 1 artifact contains complete closure and segment evidence;
8. Stage 2 remains blocked until explicit artifact approval in Issue #22.
