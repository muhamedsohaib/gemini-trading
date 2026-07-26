# Verified Partial-Closure Candle Exclusion Design

## Status

- Design gate: GitHub Issue #22
- Operator authorization: `APPROVE VERIFIED PARTIAL-CLOSURE CANDLE EXCLUSION`
- Architecture authorization: `APPROVE UNIFIED PARTIAL-CLOSURE DESIGN`
- Repository: `muhamedsohaib/gemini-trading`
- Base commit: `5f31875109fd6e2b2b535a682da433a548047855`
- Design branch: `design/verified-partial-closure-candle-exclusion`
- Safety level: `RESEARCH_ONLY`
- Execution authority: none
- Stage 2 status: prohibited until a new Stage 1 artifact is independently verified and explicitly approved

## Objective

Extend the approved exchange-closure design so the sealed BTCUSDT pipeline can represent one authentic Binance Spot `4h` candle that was truncated by the February 2018 system outage.

The provider row must remain immutable raw evidence. The row may be excluded from the canonical completed-4h dataset only when every approved identity field and its canonical provider-row digest match exactly. The effective closure then covers the unavailable canonical interval from the truncated candle open through the first resumed full candle.

## Confirmed provider evidence

The authentic Binance Spot row is fixed as:

- symbol: `BTCUSDT`;
- interval: `4h`;
- open time: `2018-02-08T00:00:00Z` (`1518048000000` ms);
- actual close time: `2018-02-08T00:28:14.788Z` (`1518049694788` ms);
- expected full close time: `2018-02-08T03:59:59.999Z` (`1518062399999` ms);
- canonical provider-row SHA-256: `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775`.

The digest is computed over the canonical compact JSON encoding of the exact Binance row values:

```json
[1518048000000,"7599.00000000","7844.00000000","7572.09000000","7784.02000000","1521.53731800",1518049694788,"11770168.04386595",12417,"844.25881300","6532638.63751892","0"]
```

The row contains real trades and remains in immutable raw retrieval evidence. It is not a valid completed 4-hour observation and must not enter canonical features, labels, returns, folds, or simulation.

## Fixed scope retained

The following identities remain unchanged:

- provider: public Binance Spot market data;
- instrument: `BTCUSDT`;
- interval: `4h`;
- request window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`;
- strategy, features, labels, costs, thresholds, folds, and final-test dates;
- long-or-cash research state;
- final-test access protections;
- `GEMINI_TRADING_MODE=research`;
- no trading, credential, order, leverage, futures, shorting, portfolio, demo, live, or capital authority.

## Alternatives considered

### Accept the truncated candle as a normal 4-hour candle

Rejected. It would falsely represent 28 minutes of trading as a complete four-hour observation and could contaminate prices, volume-derived features, labels, returns, and simulated decisions.

### Rewrite the candle close time to the expected boundary

Rejected. It would alter provider evidence and manufacture a completed interval that never traded.

### Separate partial-candle and closure manifests

Rejected. A second operator-authored policy file would split one outage across two identities and create unnecessary configuration and handoff complexity.

### Unified closure declaration

Approved. One closure entry describes the partial candle, the following seven fully missing opens, and the resumed full candle. Derived exclusion evidence records exactly how the raw row was matched and removed from canonical data.

## Architecture

### 1. Exchange-closure manifest version 2

Upgrade the fixed manifest to `exchange-closure-manifest-v2`. The fixed loader continues to accept no operator path, environment override, dispatch input, or remote source.

The single closure entry retains the stable ID:

`binance-spot-system-upgrade-2018-02-08`

It contains:

- `canonical_gap_start`: `2018-02-08T00:00:00Z`;
- `resumed_open`: `2018-02-09T08:00:00Z`;
- `unavailable_candle_count`: `8`;
- `fully_missing_start`: `2018-02-08T04:00:00Z`;
- `fully_missing_candle_count`: `7`;
- `reason_code`: `exchange_system_upgrade`;
- `governance_reference`: `github-issue-22`;
- one immutable `partial_candle` object with open time, actual close time, expected close time, provider-row SHA-256, and exclusion reason.

The unavailable count is eight canonical slots: one excluded partial slot at `00:00`, followed by seven absent opens from `04:00` through `2018-02-09T04:00:00Z`.

### 2. Exact raw-row matching

After raw pages are stored and normalized, closure-aware validation must locate exactly one row matching the approved partial-candle declaration.

Validation must verify:

1. provider, instrument, timeframe, and request-window identity;
2. open time, actual close time, expected close time, and millisecond alignment;
3. that the actual close is strictly after the open and strictly before the expected close;
4. the exact canonical provider-row SHA-256;
5. that the row is present exactly once in immutable raw evidence;
6. that the normalized OHLCV values correspond to that same raw row;
7. that no other partial, overlong, misaligned, or malformed candle exists;
8. that all fully missing opens and the resumed open match the same closure entry exactly.

A missing, duplicate, shifted, altered, additional, or hash-mismatched partial candle is fatal.

### 3. Canonical exclusion evidence

Derive and persist `candle-exclusions.json` with schema `candle-exclusion-manifest-v1`. It is generated from raw evidence and the fixed closure declaration; it is never operator-authored.

Each exclusion entry contains:

- closure ID;
- raw page sequence and raw page SHA-256;
- zero-based row index within the decoded provider page;
- canonical provider-row SHA-256;
- normalized candle open and actual close timestamps;
- expected full close timestamp;
- exclusion reason;
- canonical index position before removal.

The raw page and row remain unchanged. Only the canonical candidate sequence excludes the matched partial candle.

### 4. Effective closure and segments

After exact exclusion, the canonical sequence must jump from the last full candle before the outage to the first full resumed candle:

- last first-segment open: `2018-02-07T20:00:00Z`;
- expected next canonical open: `2018-02-08T00:00:00Z`;
- actual next canonical open: `2018-02-09T08:00:00Z`.

This one discontinuity must match the unified closure declaration exactly and produce two maximal continuous segments. The second segment retains the same preceding closure ID.

Features, labels, schedules, simulator state, returns, folds, and final-test dependencies remain segment-local. State restarts in cash after the closure and normal feature warm-up restarts from the resumed segment.

### 5. Dataset identity version 3

Introduce `candle-dataset-v3` rather than changing the meaning of v2.

The v3 dataset identity binds:

- canonical candle bytes after the exact exclusion;
- canonical exchange-closure manifest v2 bytes;
- derived candle-exclusion manifest bytes;
- derived candle-segment manifest bytes;
- provider, instrument, timeframe, and fixed request window.

The dataset manifest exposes SHA-256 values and counts for all four byte streams. A v1 or v2 dataset cannot be interpreted as v3. Stage 2 must require v3 and the exact closure and exclusion identities.

### 6. Storage, replay, and independent verification

Stage 1 must preserve:

- original raw response pages;
- retrieval manifest and provenance;
- canonical candles;
- closure manifest v2;
- candle-exclusion manifest;
- candle-segment manifest;
- dataset manifest v3;
- Stage 1 handoff.

Provider-free replay must re-extract the exact raw row, recompute its canonical row digest, reproduce the exclusion, rederive the eight-slot closure and two segments, and reproduce byte-identical v3 dataset identity.

Independent verification must separately recompute all hashes, counts, row locations, timestamps, exclusion semantics, segment boundaries, and dataset identity from immutable evidence.

### 7. Stage 1 handoff and Stage 2 gate

Upgrade the handoff schema to bind:

- dataset schema `candle-dataset-v3`;
- closure manifest path and SHA-256;
- exclusion manifest path and SHA-256;
- segment manifest path and SHA-256;
- closure count `1`;
- exclusion count `1`;
- segment count `2`;
- exact closure ID;
- excluded provider-row SHA-256;
- canonical segment boundary indices.

Stage 2 rejects v1/v2 datasets, missing or additional exclusions, any hash mismatch, path traversal, identity mismatch, failed replay, or failed independent verification.

## Data flow

```text
Public Binance Spot response pages
        |
        v
Immutable raw pages and hashes
        |
        +---- fixed closure manifest v2
        |
        v
Exact partial-row match and digest verification
        |
        v
Derived exclusion evidence + unchanged raw row
        |
        v
Canonical completed-4h candles with one partial row excluded
        |
        v
Exact eight-slot closure validation and two segments
        |
        v
Dataset v3 identity
        |
        v
Provider-free replay and independent verification
        |
        v
Identity-bound Stage 1 handoff
        |
        v
Segment-local sealed study after explicit artifact approval
```

## Failure handling

The pipeline fails closed when:

- the approved partial row is absent or appears more than once;
- any raw value or the row digest differs;
- open, actual close, or expected close differs;
- the partial row is not linked to the approved closure;
- another partial or malformed candle exists;
- the seven fully missing opens or resumed open differ;
- the exclusion manifest cannot be reproduced byte-for-byte;
- the canonical sequence contains any undeclared gap;
- closure, exclusion, segment, dataset, replay, verification, inventory, or handoff identity differs;
- any segment-sensitive strategy dependency crosses the boundary.

Failure creates no approved artifact and grants no Stage 2 access.

## Testing strategy

### Unit tests

- parse and serialize closure manifest v2 canonically;
- reject v1 where v2 is required;
- exact partial-row hash matching;
- reject altered price, volume, timestamp, trade count, or row order;
- reject missing, duplicate, additional, overlong, or misaligned partial candles;
- verify one-row exclusion without modifying raw bytes;
- verify eight unavailable canonical slots and two segments;
- verify v3 identity changes when any closure, exclusion, segment, or candle byte changes.

### Integration tests

- ingest synthetic raw pages containing the approved-shaped partial row and seven missing opens;
- replay and independently verify byte-identical evidence;
- load a verified v3 dataset;
- build the v3 handoff;
- verify segment-local features, labels, folds, simulator state, final access, replay, and study verification;
- reject all tampered raw, exclusion, manifest, inventory, and handoff variants.

### Workflow acceptance

- Stage 1 uses only fixed sealed commands and uploads exclusion evidence;
- Stage 2 requires v3, one closure, one exclusion, two segments, the exact closure ID, and the exact provider-row digest;
- no workflow exposes an override for closure or exclusion policy.

## Migration and operation

Existing failed Stage 1 runs and all v1/v2 artifacts remain invalid for this design. No prior artifact may be upgraded in place.

After implementation is reviewed, merged, and exact-main CI passes, operators must launch a completely new Stage 1 workflow from the new merged commit. The resulting artifact must be downloaded, independently verified, and explicitly approved in Issue #22 before Stage 2 can run.

## Non-goals

This design does not:

- generalize arbitrary partial-candle acceptance;
- accept operator-supplied exclusion files;
- repair, pad, interpolate, or synthesize candles;
- change strategy configuration, feature definitions, labels, costs, thresholds, folds, or final-test dates;
- authorize Stage 2, exchange execution, or real capital.

## Success criteria

The design is complete when:

1. the exact approved raw partial row is retained in immutable evidence and excluded once from canonical data;
2. all other partial or malformed candles remain fatal;
3. the unified closure represents eight unavailable canonical slots and produces two continuous segments;
4. replay and independent verification reproduce the exclusion and `candle-dataset-v3` identity exactly;
5. Stage 2 cannot consume any artifact until the new Stage 1 v3 artifact is independently approved;
6. the repository remains `RESEARCH_ONLY` with no execution authority.
