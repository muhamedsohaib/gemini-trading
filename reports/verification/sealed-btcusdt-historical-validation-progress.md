# Sealed BTCUSDT Historical Validation Progress

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Existing failed Stage 1 runs: invalid and not reusable
- New Stage 1 v3 dataset workflow: blocked until the partial-closure implementation is merged and exact-main CI passes
- Real sealed Stage 2 study: prohibited until a new Stage 1 v3 artifact is independently verified and explicitly approved in Issue #22
- Profitability and capital readiness: not established

## Approved scope

- Public Binance Spot `BTCUSDT`
- Fixed `4h` window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`
- Canonical dataset contains completed full-timeframe candles only
- Candidate identity: `candidate.multi_model.v0_1`
- Final untouched test: last 18 calendar months, single access

## Verified February 2018 evidence

- Partial candle open: `2018-02-08T00:00:00Z`
- Actual provider close: `2018-02-08T00:28:14.788Z`
- Expected full close: `2018-02-08T03:59:59.999Z`
- Exact provider-row SHA-256: `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775`
- Fully absent opens: seven, from `2018-02-08T04:00:00Z` through `2018-02-09T04:00:00Z`
- First resumed full candle: `2018-02-09T08:00:00Z`
- Effective canonical closure: eight unavailable `4h` slots
- Expected fixed-window canonical candle count: `18,617`
- Expected segment boundary index: `228`
- Expected continuous segment count: `2`

## Current implementation checkpoint

- Design and implementation-plan gate: Issue #22 and draft PR #33
- Exchange-closure manifest upgraded to `exchange-closure-manifest-v2`
- Exact partial-row digest matching and immutable exclusion evidence: implemented
- Raw response bytes and the truncated provider row remain unchanged
- Derived `candle-exclusion-manifest-v1`: implemented
- Unified eight-slot closure and deterministic two-segment derivation: implemented
- Canonical dataset identity upgraded to `candle-dataset-v3`
- Immutable storage, provider-free replay, and independent verification of exclusion evidence: implemented
- Verified dataset reader and Stage 1 handoff v3: implemented
- Exclusion identity propagated through pre-final, final-access, replay, and sealed-study verification: implemented
- Stage 1 and Stage 2 fixed workflow identity checks upgraded to v3: implemented
- Tamper rejection for exclusion hashes, closure linkage, excluded-row identity, and segment boundaries: implemented
- Operator documentation and acceptance tests: updated
- Temporary diagnostic and workspace-export workflows: removed from the intended final tree

## Verification checkpoint

- Repository-wide Ruff format check: passed locally
- Repository-wide Ruff lint: passed locally
- Changed-source strict Pyright: passed locally
- Consolidated data, reader, handoff, strategy-identity, workflow, and documentation tests: `254 passed`
- Handoff tamper-focused tests: `19 passed`
- Complete sealed end-to-end integration is too slow for the exported local runner and exceeded the local execution ceiling; exact-head GitHub CI is required as the authoritative complete-suite result
- Build, dependency audit, repository policy, detect-secrets, and full pytest remain required on the final exact PR head

Generated raw data, canonical datasets, exclusion manifests, repository-seal receipts, stable local seals, final-access receipts, pre-final evidence, and full strategy studies remain excluded from tracked repository files.
