# Verified Partial-Closure Candle Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the authentic truncated Binance BTCUSDT 4-hour row in immutable raw evidence, exclude it exactly once from canonical completed-candle data, and bind the resulting exclusion into a new `candle-dataset-v3` identity.

**Architecture:** Upgrade the fixed closure declaration to version 2, add focused exclusion evidence that exact-matches raw rows, and bind that evidence through ingestion, storage, replay, verification, handoff, workflows, and sealed-study identity checks. Strict full-timeframe validation remains the default for every other candle.

**Tech Stack:** Python 3.12, dataclasses, canonical JSON, SHA-256 identities, frozen `uv`, pytest, Ruff, Pyright, GitHub Actions.

## Global Constraints

- `RESEARCH_ONLY`; no execution authority.
- Public Binance Spot, `BTCUSDT`, `4h`, `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` only.
- Only provider-row SHA-256 `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775` may be excluded.
- Raw bytes remain unchanged; no repair, interpolation, filling, or synthesis.
- One eight-slot closure, one exclusion, two continuous segments.
- Dataset schema becomes `candle-dataset-v3`; Stage 2 rejects v1/v2.
- Strategy, features, labels, costs, thresholds, folds, final dates, and final-access policy remain unchanged.
- Stage 2 remains blocked until a new merged-main Stage 1 v3 artifact is independently approved in Issue #22.

## Planned Tasks

### Task 1: Upgrade the fixed closure contract to v2

**Files:** fixed closure JSON, `data/exchange_closures.py`, closure tests.

- [ ] Write failing tests for `PartialCandleDeclaration`, v2 fields, canonical encoding, UTC/timeframe arithmetic, exact counts, and SHA validation.
- [ ] Run `uv run pytest tests/unit/data/test_exchange_closures.py -q` and confirm RED.
- [ ] Implement `exchange-closure-manifest-v2` with canonical gap start, resumed open, eight unavailable slots, seven fully missing slots, and the exact partial-candle declaration.
- [ ] Run tests, Ruff, Pyright, and commit `feat: upgrade sealed closure contract to v2`.

### Task 2: Add exact raw-row matching and exclusion evidence

**Files:** create `data/exclusions.py`, exclusion tests, partial-closure fixture.

**Interfaces:** `CandleExclusion`, `CandleExclusionManifest`, `PartialCandleExclusionResult`, `canonical_binance_kline_row_bytes()`, and `match_and_exclude_partial_candles()`.

- [ ] Write digest tests for the exact approved row and mutations of every field/type/order.
- [ ] Write tests proving one exact exclusion, unchanged raw bytes, correct page/row/candidate indices, and filtered canonical candidates.
- [ ] Reject missing, duplicate, extra, overlong, misaligned, timestamp-shifted, OHLCV-mismatched, and hash-mismatched rows.
- [ ] Confirm RED, implement deterministic matching/serialization, run focused tests and strict typing, then commit `feat: add exact partial-candle exclusion evidence`.

### Task 3: Validate the unified eight-slot closure and segments

**Files:** `data/segments.py`, segment tests.

- [ ] Require the post-exclusion jump from `2018-02-07T20:00:00Z` to `2018-02-09T08:00:00Z`, one closure, and two segments.
- [ ] Reject wrong bounds/counts, unused declarations, extra gaps, and unexcluded partial candles.
- [ ] Match `(canonical_gap_start, resumed_open)`, verify timeframe arithmetic, run tests, and commit `feat: validate unified partial closure segments`.

### Task 4: Introduce `candle-dataset-v3`

**Files:** dataset domain, canonical writer, dataset tests.

- [ ] Require exclusion hash/count fields and dataset-ID sensitivity to candle, closure, exclusion, and segment bytes.
- [ ] Confirm RED, extend immutable contracts and canonical identity without changing v1/v2 meaning.
- [ ] Run domain/data tests and commit `feat: bind exclusions into candle dataset v3`.

### Task 5: Persist exclusion evidence during ingestion

**Files:** storage protocols/local storage, ingestion service/tests.

- [ ] Test immutable run-level and dataset-level `candle-exclusions.json` storage.
- [ ] Test unchanged raw bytes, one exclusion, two segments, v3 publication, and fail-closed no-publication variants.
- [ ] Implement: store raw → normalize → complete-filter → exact exclusion → segment → v3 publication.
- [ ] Run focused tests and commit `feat: persist partial-candle exclusions during ingestion`.

### Task 6: Replay and independently verify exclusions

**Files:** replay service, verification service, tests.

- [ ] Require provider-free byte-identical v3 replay.
- [ ] Tamper raw row, page hash, row/candidate indices, exclusion fields/hashes, closure/segment hashes, candles, and dataset ID.
- [ ] Rebuild exclusion evidence from raw pages rather than trusting persisted fields.
- [ ] Run tests and commit `feat: replay and verify candle exclusions`.

### Task 7: Upgrade verified loading and Stage 1 handoff

**Files:** dataset reader, handoff, tests.

- [ ] Reject v1/v2, missing/extra exclusions, path traversal, hash mismatch, and irreproducible exclusions.
- [ ] Bind exact paths/hashes, counts `1/1/2`, closure ID, excluded-row SHA-256, and segment boundaries.
- [ ] Run tests and commit `feat: upgrade sealed dataset handoff to v3`.

### Task 8: Propagate v3 identity through sealed studies

**Files:** only strategy modules/tests currently binding v2 closure/segment identity.

- [ ] Add pre-final, final, replay, and independent-verification mismatch tests for exclusion identity.
- [ ] Propagate v3 fields without changing features, labels, models, costs, thresholds, splits, simulator rules, or final access.
- [ ] Run strategy tests and commit `feat: bind exclusion identity through sealed studies`.

### Task 9: Update CLI and protected workflows

**Files:** historical-validation CLI, both sealed workflows, acceptance tests.

- [ ] Stage 1 inventory includes exclusion evidence.
- [ ] Stage 2 requires v3, counts `1/1/2`, exact closure ID, and exact row SHA-256.
- [ ] Prove no operator closure/exclusion path or environment override exists.
- [ ] Run acceptance tests and commit `feat: require v3 exclusion evidence in sealed workflows`.

### Task 10: Complete integration, tamper, and documentation coverage

- [ ] End-to-end synthetic Stage 1: ingest, replay, verify, load, handoff.
- [ ] Complete raw/declaration/exclusion/segment/dataset/inventory/handoff tamper matrix.
- [ ] Update operator docs and README with v3 inventory and approval evidence.
- [ ] Run integration/acceptance tests and commit `test: cover sealed partial-candle exclusion end to end`.

### Task 11: Run the full repository gate

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
python scripts/validate_tracked_files.py
uv run detect-secrets scan --all-files --baseline .secrets.baseline
```

Review the diff for credentials, execution, model, threshold, cost, final-test, or unrelated changes.

### Task 12: Protected merge and new Stage 1 run

- [ ] Require exact-head CI and Gitleaks.
- [ ] Resolve all review threads and squash-merge with expected-head locking.
- [ ] Verify exact merged-main CI.
- [ ] Launch a completely new Stage 1 run from that exact `main` commit.
- [ ] Independently record source/workflow/artifact/retrieval/dataset IDs; v3 closure/exclusion/segment hashes; counts; closure ID; excluded-row SHA; boundaries; candle bounds; inventory hash; replay and verification success.
- [ ] Keep Stage 2 blocked until the exact dataset approval marker is posted after artifact review.

## Plan Self-Review

- All written-spec architecture, identity, failure, testing, workflow, and migration requirements map to Tasks 1–12.
- No deferred requirement or placeholder remains.
- Closure v2 → exclusion evidence → dataset v3 → storage/replay/verification → reader/handoff → CLI/workflows/study identity is type-consistent.
- No execution, strategy behavior, final-test rule, model configuration, or unrelated refactor is included.
