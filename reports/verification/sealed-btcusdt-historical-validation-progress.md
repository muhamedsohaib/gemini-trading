# Sealed BTCUSDT Historical Validation Progress

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Existing Stage 1 v1-v3 runs and artifacts: invalid for the revised study and not reusable
- New Stage 1 v4 dataset workflow: blocked until the multi-closure implementation is merged and exact-main verification passes
- Real sealed Stage 2 study: prohibited until a completely new Stage 1 v4 artifact is independently verified and explicitly approved in Issue #22
- Profitability and capital readiness: not established

## Approved scope

- Public Binance Spot `BTCUSDT`
- Fixed `4h` window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`
- Canonical dataset contains completed full-timeframe candles only
- Candidate identity: `candidate.multi_model.v0_1`
- Final untouched test: last 18 calendar months, single access

## Verified multi-closure inventory

- Source-controlled schema: `exchange-closure-manifest-v3`
- Verified partial-candle rows: `20`
- Fully absent canonical opens: `16`
- Total unavailable canonical `4h` slots: `36`
- Exact exclusions: `20`
- Expected continuous segments: `21`
- Expected fixed-window canonical candle count: `18,582`
- Expected first canonical open: `2018-01-01T00:00:00Z`
- Expected last canonical open: `2026-06-30T20:00:00Z`
- Expected segment boundaries: `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`
- Raw provider pages and all excluded rows remain byte-for-byte immutable
- No candle is inserted, repaired, interpolated, forward-filled, zero-filled, padded, or synthesized

## Current implementation checkpoint

- Approved design and implementation plan: Issue #22 and PR #41
- Implementation pull request: PR #42
- Exchange-closure manifest: `exchange-closure-manifest-v3`
- Exact multi-page partial-row matching and immutable exclusion evidence: implemented
- Zero-fully-missing interruption arithmetic: implemented
- Derived `candle-exclusion-manifest-v1` with 20 ordered exclusions: implemented
- Derived `candle-segment-manifest-v1` with 21 deterministic segments: implemented
- Canonical dataset identity: `candle-dataset-v4`
- Immutable storage, provider-free replay, and independent v4 verification: implemented
- Strict verified dataset loading with `require_v4=True`: implemented
- Stage 1 handoff: `sealed-dataset-handoff-v4` with ordered plural excluded-row identities
- Handoff v4 identity propagated through pre-final, final-access, replay, sealed evaluation, and independent sealed-study verification
- Central fixed v4 identity validator added for Stage 1 and Stage 2 workflows
- Tamper rejection covers missing, duplicate, changed, reordered, shifted, extra, overlapping, and boundary-crossing evidence
- Strategy features, labels, models, costs, thresholds, folds, final-test dates, and long-or-cash policy remain unchanged

## Verification checkpoint

- Focused Ruff, strict Pyright, unit, workflow-contract, and integration checks are required on the exact final PR head
- Full repository pytest, build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks remain mandatory before merge
- Protected merge and exact-main verification remain mandatory before a completely new Stage 1 v4 run
- No Stage 1 v4 artifact has yet been approved
- No Stage 2 study has been authorized or run
- There is no real historical Candidate result

Generated raw data, canonical datasets, exclusion manifests, repository-seal receipts, stable local seals, final-access receipts, pre-final evidence, and full strategy studies remain excluded from tracked repository files.
