# Candidate v0.4 Task 2 Hourly Closure Amendment

- Date: 2026-08-15
- Parent design: `docs/superpowers/specs/2026-08-15-candidate-multi-model-strategy-v0-4-design.md`
- Parent plan: `docs/superpowers/plans/2026-08-15-candidate-multi-model-strategy-v0-4.md`
- Boundary: `RESEARCH_ONLY`
- Financial specification changed: **NO**

## Discovery

The approved source-controlled exchange-closure evidence is intentionally a 4h manifest. Its v3 schema requires every closure to contain exactly one partial 4h candle whose open time equals the 4h gap start, followed by zero or more fully missing 4h slots.

That representation cannot be mechanically reused at 1h resolution. A historical interruption may occur:

1. inside an hourly candle, in which case the containing 1h candle is partial and must be excluded; or
2. exactly at the normal close of an hourly candle, in which case that 1h candle is complete and the outage begins with the next fully missing hour.

Forcing case (2) into the existing v3 `partial_candle` shape would fabricate an exclusion and corrupt the Candidate v0.4 canonical dataset.

## Corrected infrastructure contract

Candidate v0.4 will preserve the exact approved v3 4h closure manifest as immutable **source evidence** and deterministically derive a v4 hourly closure manifest from its interruption metadata.

For each source closure:

- `actual_close_time` and `resumed_open` are inherited from the frozen source declaration;
- let `hour_open` be the UTC hour containing `actual_close_time`;
- let `hour_expected_close = hour_open + 1h - 1ms`;
- if `actual_close_time < hour_expected_close`, the hourly closure starts at `hour_open`, contains one declared partial hourly slot, and fully missing hourly slots begin at `hour_open + 1h`;
- if `actual_close_time == hour_expected_close`, that hourly candle is complete, the hourly closure starts at `hour_open + 1h`, and the closure contains **no partial hourly slot**;
- the closure ends at the unchanged `resumed_open` timestamp;
- hourly unavailable/full-missing counts are derived only from those timestamps and the exact 1h duration;
- any impossible alignment, negative interval, overlapping derived closure, or resumed time before/equal to the derived gap start fails closed.

The derived hourly manifest is linked to the exact source v3 manifest SHA-256. No price, return, feature, model, or qualification outcome participates in this derivation.

## Partial-row identity

The frozen source manifest contains hashes of the original **4h provider rows**. Those hashes cannot truthfully be reused as hashes of 1h provider rows.

For a derived partial hourly slot:

- its open time, actual close time, expected hourly close time, closure ID, and exclusion reason are preregistered before retrieval;
- its 1h provider-row SHA-256 is intentionally unset in the derived closure declaration;
- Stage 1 must find exactly one raw 1h row matching the declared open/actual-close timing;
- the immutable raw page and exact 1h provider row are hashed during ingestion;
- that derived row hash is persisted in `CandleExclusionManifest` and the v0.4 handoff;
- provider-free replay must reproduce the same row location/hash from bundled raw pages.

Unexpected partial rows, undeclared missing hours, missing declared partials, a declared fully-missing hour appearing in raw evidence, or a missing resumed candle remain hard failures.

## Shared-code compatibility requirement

The reusable market-data closure/exclusion primitives may be extended to support the v4 optional-partial semantics only if all of the following remain true:

- exact v3 manifest bytes are unchanged;
- `load_fixed_btcusdt_closure_manifest()` retains its exact source-file SHA check;
- all existing v3 closure, exclusion, segment, ingestion, replay, verification, and Candidate v0.3 tests remain unchanged and green;
- v4 serialization is schema-distinct and fail-closed;
- an absent partial declaration does not create an exclusion row;
- closure count and exclusion count are allowed to differ for v4 evidence;
- segment boundaries are derived from actual canonical gaps, not from copied 4h indexes.

## Scope amendment to Task 2

Task 2 may therefore modify, under backward-compatible TDD only:

- `src/gemini_trading/data/exchange_closures.py`
- `src/gemini_trading/data/exclusions.py`
- their focused tests
- and, only if RED evidence proves necessary, ingestion replay/verification call sites whose existing generic algorithms need no semantic change beyond accepting the v4 closure contract.

The Candidate v0.4 financial hypothesis, model families, features, labels, thresholds, costs, risk settings, qualification gates, and prospective policy are unchanged.
