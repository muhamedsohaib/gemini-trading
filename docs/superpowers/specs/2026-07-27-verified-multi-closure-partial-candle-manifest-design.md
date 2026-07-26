# Verified Multi-Closure Partial-Candle Manifest Design

## Status

- Design gate: GitHub Issue #22
- Operator authorization: `APPROVE VERIFIED MULTI-CLOSURE PARTIAL-CANDLE MANIFEST`
- Approval comment: Issue #22 comment `5085766649`
- Diagnostic inventory comment: Issue #22 comment `5085746081`
- Repository: `muhamedsohaib/gemini-trading`
- Base commit: `cf8389f6b8964b5aee0563083f8bf362be33b1ab`
- Design branch: `design/verified-multi-closure-partial-candle-manifest`
- Safety level: `RESEARCH_ONLY`
- Execution authority: none
- Stage 1: blocked until this revision is implemented, merged, and exact-main verified
- Stage 2: prohibited until a new Stage 1 v4 artifact is independently verified and explicitly approved

## Objective

Extend the sealed BTCUSDT historical-validation pipeline from one exact truncated Binance row to the complete, independently inventoried set of 20 authentic short-close rows in the fixed historical window.

Every raw provider row remains immutable evidence. A row may be excluded from canonical completed-`4h` data only when its source-controlled declaration, timestamp boundaries, canonical row digest, page identity, row location, and normalized values match exactly. Each exclusion creates a mandatory continuous-segment boundary, including interruptions with zero fully missing rows.

This changes data-governance identity only. It does not change the Candidate strategy, features, labels, costs, thresholds, folds, final-test dates, position policy, or execution authority.

## Fixed scope

The following remain unchanged:

- public Binance Spot market data;
- `BTCUSDT`, completed `4h` candles;
- request window `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`;
- Candidate `candidate.multi_model.v0_1` and its locked configuration;
- long-or-cash research state;
- final untouched test: last 18 calendar months, single access;
- `GEMINI_TRADING_MODE=research`;
- no paper, demo, live, production, credentials, orders, leverage, futures, shorting, portfolio, or capital authority.

## Evidence and fixed invariants

The preserved diagnostic artifact from workflow run `30220838420` contains 19 immutable raw pages and 18,602 returned Binance rows. Deterministic analysis found exactly 20 structurally valid short-close rows, 16 fully absent aligned opens, and no late-close, duplicate-open, reversed-order, or structurally malformed row.

The revised fixed-window invariants are:

- returned provider rows: `18,602`;
- declared partial rows: `20`;
- fully missing aligned opens: `16`;
- unavailable canonical slots: `36`;
- canonical completed candles: `18,582`;
- closure count: `20`;
- exclusion count: `20`;
- continuous segment count: `21`;
- segment boundary indices: `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`;
- first canonical open: `2018-01-01T00:00:00Z`;
- last canonical open: `2026-06-30T20:00:00Z`.

Any different value fails closed.

## Exact approved inventory

| # | Closure ID | Partial open | Actual close | Resumed open | Missing | Unavailable | Boundary | Provider-row SHA-256 |
|---:|---|---|---|---|---:|---:|---:|---|
| 1 | `binance-spot-infrastructure-maintenance-2018-01-04` | `2018-01-04T00:00:00.000Z` | `2018-01-04T03:00:14.838Z` | `2018-01-04T04:00:00.000Z` | 0 | 1 | 18 | `ce5df946e724e509699e24166fcd96bd566c48de7090b3a092aaa324bd73c426` |
| 2 | `binance-spot-system-upgrade-2018-02-08` | `2018-02-08T00:00:00.000Z` | `2018-02-08T00:28:14.788Z` | `2018-02-09T08:00:00.000Z` | 7 | 8 | 227 | `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775` |
| 3 | `binance-spot-system-upgrade-2018-06-26` | `2018-06-26T00:00:00.000Z` | `2018-06-26T01:59:59.999Z` | `2018-06-26T12:00:00.000Z` | 2 | 3 | 1047 | `31d7e347e1830772a39ab0bdf78e09af6ff3f3735cad745916fe32e6fe0fd557` |
| 4 | `binance-spot-risk-control-suspension-2018-07-04` | `2018-07-04T00:00:00.000Z` | `2018-07-04T00:22:25.551Z` | `2018-07-04T08:00:00.000Z` | 1 | 2 | 1092 | `1202a2e967f8907eab3917a36f9b5bb440e4ca6647779fdebefd50bcce61b5b8` |
| 5 | `binance-spot-emergency-maintenance-2018-10-19` | `2018-10-19T04:00:00.000Z` | `2018-10-19T05:59:59.999Z` | `2018-10-19T08:00:00.000Z` | 0 | 1 | 1733 | `3a06f4a8c191d42bebd2597f7c19932362f4d95f7fe7452f51c268209b629474` |
| 6 | `binance-spot-system-upgrade-2018-11-14` | `2018-11-14T00:00:00.000Z` | `2018-11-14T01:59:59.999Z` | `2018-11-14T08:00:00.000Z` | 1 | 2 | 1887 | `dd328080cdc59124c3a0467faf719f055dc208a03a229d89dbe0ec403ebf3ee8` |
| 7 | `binance-spot-system-upgrade-2019-03-12` | `2019-03-12T00:00:00.000Z` | `2019-03-12T01:59:59.999Z` | `2019-03-12T08:00:00.000Z` | 1 | 2 | 2593 | `455bc52eeca4bc7097498742c200d5ecc46019683ed37ea36ed2acb4f3d8478f` |
| 8 | `binance-spot-security-upgrade-2019-05-15` | `2019-05-15T00:00:00.000Z` | `2019-05-15T02:59:59.999Z` | `2019-05-15T12:00:00.000Z` | 2 | 3 | 2975 | `1021733a2305723bc1dad0dd8ebd8523fdc36839ef52353018d987429508efad` |
| 9 | `binance-spot-system-upgrade-2019-08-15` | `2019-08-15T00:00:00.000Z` | `2019-08-15T01:59:59.999Z` | `2019-08-15T08:00:00.000Z` | 1 | 2 | 3524 | `1f68a701351a2ae6917bf4a5d524885416dc7715a704af8e0db52d3938cff876` |
| 10 | `binance-spot-system-upgrade-2019-11-13` | `2019-11-13T00:00:00.000Z` | `2019-11-13T01:59:59.999Z` | `2019-11-13T04:00:00.000Z` | 0 | 1 | 4062 | `aee4ed92909f4b8e8c957370da2499c928d304374c7db303ffd591a370c2e609` |
| 11 | `binance-spot-system-upgrade-2019-11-25` | `2019-11-25T00:00:00.000Z` | `2019-11-25T01:59:59.999Z` | `2019-11-25T04:00:00.000Z` | 0 | 1 | 4133 | `2b11ed5d8fe5724c559ce91e5c922b0a98d3ae16a859eec895e128b5e1e9ac54` |
| 12 | `binance-spot-market-data-maintenance-2020-02-19` | `2020-02-19T08:00:00.000Z` | `2020-02-19T11:35:32.286Z` | `2020-02-19T16:00:00.000Z` | 1 | 2 | 4650 | `a756811ac8139d621c6fde28980d8019fef535d7f1e17b2d4310b10370d2ac53` |
| 13 | `binance-spot-system-upgrade-2020-04-25` | `2020-04-25T00:00:00.000Z` | `2020-04-25T01:59:59.999Z` | `2020-04-25T04:00:00.000Z` | 0 | 1 | 5042 | `7c11bd7bff7cd4815615ea6003cb3dbed08b214b78a2bbe722cfe22912592354` |
| 14 | `binance-spot-system-upgrade-2020-06-28` | `2020-06-28T00:00:00.000Z` | `2020-06-28T01:59:59.999Z` | `2020-06-28T04:00:00.000Z` | 0 | 1 | 5425 | `bbca0d86447c44964449be1ae5bf5968e391cffad1fb16aee136f07369553a01` |
| 15 | `binance-spot-matching-engine-maintenance-2020-12-21` | `2020-12-21T12:00:00.000Z` | `2020-12-21T13:47:20.521Z` | `2020-12-21T16:00:00.000Z` | 0 | 1 | 6483 | `b9208db0c003f68d77ffeeb7e9054c348f61ede5840db275f0d5baf84cfdd2c9` |
| 16 | `binance-spot-matching-engine-maintenance-2021-02-11` | `2021-02-11T00:00:00.000Z` | `2021-02-11T03:40:54.773Z` | `2021-02-11T04:00:00.000Z` | 0 | 1 | 6791 | `6336454bf83a67e99118f3405c3926c444668028f1c65518d509bdf19eab6cb4` |
| 17 | `binance-spot-system-upgrade-2021-04-20` | `2021-04-20T00:00:00.000Z` | `2021-04-20T01:59:59.999Z` | `2021-04-20T04:00:00.000Z` | 0 | 1 | 7198 | `bdf24e2e33ecdca4f2d6960f80dd62521e9588e72badd2497857fa4efc521393` |
| 18 | `binance-spot-system-upgrade-2021-04-25` | `2021-04-25T04:00:00.000Z` | `2021-04-25T04:00:58.146Z` | `2021-04-25T08:00:00.000Z` | 0 | 1 | 7228 | `d033c7c18ec2bc9b3b545a93b7d886e5e3f8c70331ffb07f2cf04fb631108d49` |
| 19 | `binance-spot-system-upgrade-2021-08-13` | `2021-08-13T00:00:00.000Z` | `2021-08-13T01:59:59.000Z` | `2021-08-13T04:00:00.000Z` | 0 | 1 | 7886 | `82ec6dfd6d5d034bd9dfa6c81a5fdcee87db14a998beb3d9dad6f3dbd860509d` |
| 20 | `binance-spot-system-upgrade-2021-09-29` | `2021-09-29T04:00:00.000Z` | `2021-09-29T06:59:59.999Z` | `2021-09-29T08:00:00.000Z` | 0 | 1 | 8168 | `ae05924001aab056ea72c61061f0b75db9aab01ca04ca6db69c7a01f09a99924` |

The February 2018 closure ID remains unchanged. New IDs are stable source-controlled identifiers. Reason codes classify evidence but never relax exact timestamp or digest matching.

## Alternatives

### Accept short rows as complete candles

Rejected. Partial intervals cannot be represented as full `4h` observations without contaminating prices, volumes, features, labels, returns, and simulation.

### Repair close times or exclude by shape

Rejected. Rewriting close times manufactures evidence. Excluding any early-close row by shape creates an open-ended policy that could silently accept corruption or future provider changes.

### Shift the study start

Rejected. This changes the approved window and sealed study rather than representing authentic exchange unavailability.

### Exact multi-closure declaration and exclusion

Approved. Declare all 20 rows by exact identity, preserve raw bytes, derive exclusion evidence, and reset all research state at every boundary.

## Architecture

### 1. Exchange-closure manifest v3

Introduce `exchange-closure-manifest-v3`; do not reinterpret v2. The fixed loader accepts no operator path, environment override, dispatch input, or remote policy source.

Each closure keeps the v2 field shape:

- `closure_id`;
- `canonical_gap_start`;
- `resumed_open`;
- `unavailable_candle_count`;
- `fully_missing_start`;
- `fully_missing_candle_count`;
- `reason_code`;
- `governance_reference`;
- exact `partial_candle` identity.

For every closure:

- `partial_candle.open_time == canonical_gap_start`;
- expected close equals open plus `4h` minus one millisecond;
- actual close is strictly inside that slot;
- `fully_missing_start == canonical_gap_start + 4h`;
- `unavailable_candle_count == fully_missing_candle_count + 1`;
- `resumed_open == canonical_gap_start + unavailable_candle_count * 4h`;
- `fully_missing_candle_count >= 0`;
- `unavailable_candle_count >= 1`.

Declarations must be strictly ordered and non-overlapping. Duplicate closure IDs, partial opens, or provider-row digests are fatal.

### 2. Exact exclusion evidence

Retain `candle-exclusion-manifest-v1`; it already supports multiple exclusions.

The matcher must scan every immutable raw row and:

1. reproduce normalized values from raw bytes;
2. enforce unique ordered opens and page identity;
3. match each declared partial row by open time;
4. verify actual close, expected close, canonical row digest, server-close state, and normalized values;
5. exclude each declaration exactly once;
6. reject every undeclared early, late, overlong, misaligned, malformed, duplicate, reordered, or altered row;
7. include only full-timeframe completed candles in canonical output;
8. preserve all raw bytes unchanged.

Derived exclusions remain ordered by `canonical_index_before_removal`. Their closure IDs and row digests must exactly match the ordered closure declarations.

### 3. Zero-fully-missing semantics

A short row followed by the next aligned open still represents one unavailable canonical slot. Validation therefore permits:

```text
fully_missing_candle_count = 0
fully_missing_start = resumed_open
unavailable_candle_count = 1
```

The absent-open set is empty. The resumed candle must still exist exactly once. A candle inside a non-empty fully missing interval is fatal.

### 4. Continuous segments

Retain `candle-segment-manifest-v1`. After exclusions, each declared interval must appear exactly once as a discontinuity from the previous full candle to the resumed candle. Derivation must produce exactly 21 maximal segments and the fixed boundary tuple.

Every declaration must be used and every observed discontinuity must be declared. Duplicate use, unused declarations, shifted resumption, additional gaps, overlaps, or boundary mismatches are fatal.

Features, labels, schedules, folds, simulator state, orders, positions, returns, bootstrap samples, controls, and final-test dependencies remain segment-local. Warm-up restarts after every boundary. No synthetic liquidation is allowed; noncash or active-order state crossing a boundary remains terminal.

All 20 interruptions precede the final test. Any future closure intersecting it requires another written design gate.

### 5. Dataset identity v4

Introduce `candle-dataset-v4`; do not change v3 semantics. V4 binds:

- canonical candle bytes after all 20 exclusions;
- closure manifest v3 bytes;
- exclusion manifest v1 bytes;
- segment manifest v1 bytes;
- provider, instrument, timeframe, and fixed request window.

The dataset manifest retains supporting-evidence fields with exact counts `20/20/21`. V1-v3 artifacts are invalid inputs for the revised sealed study.

### 6. Storage, replay, and verification

`retrieval-manifest-v2` remains valid because it binds the exact closure-manifest hash without assuming one closure. Storage paths remain unchanged.

Stage 1 persists all raw pages, retrieval evidence, canonical candles, closure v3, exclusion v1, segments v1, dataset v4, provenance, and handoff v4.

Provider-free replay and independent verification must reproduce all 20 row matches, exclusions, empty and non-empty absent-open sets, segment boundaries, canonical bytes, counts, and v4 identity. Any mismatch in page identity, row identity, ordering, counts, hashes, timestamps, boundaries, candle total, or dataset identity is fatal.

### 7. Stage 1 handoff v4

Introduce `sealed-dataset-handoff-v4`.

Replace scalar `excluded_provider_row_sha256` with ordered `excluded_provider_rows`, where each item contains exactly `closure_id` and `provider_row_sha256`. The array order must equal `closure_ids`, closure-manifest order, and exclusion-manifest order.

The handoff binds:

- dataset schema `candle-dataset-v4`;
- closure, exclusion, and segment paths and hashes;
- counts `20/20/21`;
- all closure IDs and excluded row digests;
- all 20 boundary indices;
- candle count `18,582`;
- fixed first and last opens;
- complete sorted artifact inventory and root hash;
- replay `completed` and verification `verified`.

Stage 2 rejects handoff v1-v3, dataset v1-v3, legacy scalar row identity, reordered identities, missing or extra rows, any hash mismatch, path traversal, inventory mismatch, or failed verification.

### 8. Strategy identity propagation

Pre-final evidence, final-access identity, sealed-study manifests, provider-free replay, and independent study verification bind the v4 handoff and its inventory root. Strategy logic does not change; computations operate on 21 independent continuous segments while all anti-leakage and single-final-access controls remain intact.

### 9. Workflow gates

Stage 1 and Stage 2 must assert:

- `candle-dataset-v4`;
- counts `(20, 20, 21)`;
- exact ordered closure IDs and excluded row identities;
- exact boundary tuple;
- candle count `18,582`.

No real workflow may run from a design or implementation branch. After protected merge, exact merged-main verification must pass before a new Stage 1 dispatch. Existing failed and v3 artifacts are invalid and non-reusable.

## Failure handling

The pipeline fails closed when:

- any approved row is absent, duplicated, shifted, reordered, altered, or hash-mismatched;
- an additional short, overlong, misaligned, or malformed row exists;
- a declaration is unused or used more than once;
- a closure overlaps, touches, falls outside the window, or has inconsistent arithmetic;
- a zero-missing closure does not resume at the next aligned open;
- a non-empty missing interval contains a row;
- a resumed candle is absent or duplicated;
- closure, exclusion, or segment order differs;
- a fixed count, boundary, candle total, or identity differs;
- replay or verification cannot reproduce byte-identical evidence;
- a research dependency crosses a segment boundary.

Failure produces no approved Stage 1 artifact and grants no Stage 2 access.

## Testing

### Unit

- canonical v3 closure parse and serialization;
- accept zero missing with exact arithmetic;
- reject negative or inconsistent counts, shifted resumption, duplicate starts or digests, overlaps, and touching entries;
- exact 20-row fixed manifest identity;
- matching across page boundaries and exact exclusion ordering;
- reject altered, missing, duplicate, extra, overlong, and reordered rows;
- reject rows inside non-empty missing intervals;
- derive 21 segments and exact boundaries;
- v4 dataset identity changes on any supporting-byte change;
- v4 handoff plural identity and ordering.

### Integration

- synthetic mixed closures with zero and nonzero missing counts;
- multi-page ingestion preserving raw bytes;
- provider-free replay reproducing 20 exclusions and 21 segments;
- independent v4 verification;
- verified v4 loading and handoff construction;
- segment-local strategy dependencies and final-access controls;
- supporting-manifest and handoff tamper rejection.

### Acceptance

- documentation states 20/20/21, 36 unavailable slots, and 18,582 candles;
- workflows require exact v4 identities;
- no operator manifest override exists;
- least privilege, one-time access, artifact, secret, and clean-tree controls remain enforced.

## Rollout

1. Commit this design on the dedicated branch.
2. Review and approve the written specification.
3. Write a detailed TDD implementation plan.
4. Implement through a protected pull request with focused RED/GREEN commits.
5. Run Ruff format, Ruff lint, strict Pyright, full pytest, build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks.
6. Require exact-head CI and protected squash merge.
7. Independently verify exact merged main.
8. Dispatch a completely new Stage 1 workflow from that commit.
9. Download and independently verify the v4 artifact.
10. Record exact identities and the owner-authored approval marker in Issue #22.
11. Keep Stage 2 prohibited until that approval is complete.

## Scope exclusions

This design does not change strategy logic or sealed-study parameters, approve a dataset or result, authorize a Stage 1 run from current or branch code, authorize Stage 2, or grant paper/demo/live/exchange/capital authority. Historical validation remains evidence, not proof of future profitability.
