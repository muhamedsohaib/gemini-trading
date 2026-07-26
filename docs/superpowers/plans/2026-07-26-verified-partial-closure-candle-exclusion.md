# Verified Partial-Closure Candle Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the authentic truncated Binance BTCUSDT 4-hour row in immutable raw evidence, exclude it exactly once from canonical completed-candle data, and bind the resulting exclusion into a new `candle-dataset-v3` identity.

**Architecture:** Upgrade the fixed closure declaration to version 2, add a focused exclusion-evidence module that matches exact raw rows and emits deterministic exclusion evidence, then thread that evidence through ingestion, storage, replay, verification, handoff, workflows, and sealed-study identity checks. All ordinary candles retain strict full-timeframe validation, and every undeclared or mismatched partial candle remains fatal.

**Tech Stack:** Python 3.12, dataclasses, canonical JSON, SHA-256 content identities, frozen `uv`, pytest, Ruff, Pyright, GitHub Actions.

## Global Constraints

- Safety remains `RESEARCH_ONLY`; execution authority remains none.
- Provider remains public Binance Spot market data only.
- Instrument remains `BTCUSDT`; timeframe remains `4h`.
- Window remains `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
- The exact provider row with SHA-256 `6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775` is the only approved partial candle.
- Raw response bytes and the raw row must never be modified.
- The approved partial candle is excluded once from canonical completed-4h data; no candle is repaired, padded, interpolated, forward-filled, or synthesized.
- The unified closure contains eight unavailable canonical slots and produces exactly two segments.
- Dataset schema becomes `candle-dataset-v3`; Stage 2 must reject v1 and v2 artifacts.
- Strategy configuration, features, labels, costs, thresholds, folds, final-test dates, and final-access policy remain unchanged.
- Stage 2 remains prohibited until a new merged-main Stage 1 v3 artifact is independently verified and explicitly approved in Issue #22.

---

## File Structure

### New focused files

- `src/gemini_trading/data/exclusions.py` — canonical provider-row encoding, exact partial-row matching, exclusion manifest contracts, serialization, and validation.
- `tests/unit/data/test_candle_exclusions.py` — unit tests for exact matching, rejection, canonical encoding, and exclusion evidence.
- `tests/fixtures/market_data/partial_closure_btcusdt_4h.py` — deterministic synthetic raw pages with the approved-shaped partial row and seven missing opens.

### Existing files to modify

- `config/market-data/sealed-btcusdt-4h-exchange-closures.json`
- `src/gemini_trading/data/exchange_closures.py`
- `src/gemini_trading/data/segments.py`
- `src/gemini_trading/domain/dataset.py`
- `src/gemini_trading/data/datasets/canonical_writer.py`
- `src/gemini_trading/data/storage/base.py`
- `src/gemini_trading/data/storage/local_immutable.py`
- `src/gemini_trading/data/ingestion/service.py`
- `src/gemini_trading/data/ingestion/replay.py`
- `src/gemini_trading/data/verification/service.py`
- `src/gemini_trading/research/dataset_reader.py`
- `src/gemini_trading/strategy/handoff.py`
- `src/gemini_trading/cli/historical_validation.py`
- `.github/workflows/sealed-btcusdt-dataset.yml`
- `.github/workflows/sealed-btcusdt-study.yml`
- `docs/operations/sealed-btcusdt-historical-validation.md`
- `README.md`
- relevant unit, integration, acceptance, tamper, replay, and workflow tests.

---

### Task 1: Upgrade the fixed closure contract to version 2

**Files:**
- Modify: `config/market-data/sealed-btcusdt-4h-exchange-closures.json`
- Modify: `src/gemini_trading/data/exchange_closures.py`
- Modify: `tests/unit/data/test_exchange_closures.py`

**Interfaces:**
- Produces: `PartialCandleDeclaration` and the upgraded `ExchangeClosure` / `ExchangeClosureManifest` contracts.
- Produces: `load_exchange_closure_manifest(raw: bytes) -> ExchangeClosureManifest` and `serialize_exchange_closure_manifest(manifest: ExchangeClosureManifest) -> bytes` for `exchange-closure-manifest-v2` only.

- [ ] **Step 1: Replace the fixed manifest fixture with canonical v2 JSON**

Use one compact newline-terminated JSON document containing the approved closure ID, canonical gap start, resumed open, eight unavailable slots, seven fully missing slots, and exact partial-row identity from the written specification.

- [ ] **Step 2: Write failing parser tests**

Require v2 fields and reject v1, unknown fields, missing partial-candle fields, invalid SHA-256, non-UTC values, misaligned expected close, incorrect counts, and a partial open different from `canonical_gap_start`.

- [ ] **Step 3: Run the focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -q
```

- [ ] **Step 4: Implement the minimal immutable v2 contracts**

Add `PartialCandleDeclaration` and update `ExchangeClosure` with the v2 fields. Validate exact timeframe arithmetic and canonical serialization.

- [ ] **Step 5: Run focused tests and commit**

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -q
uv run ruff format --check src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
uv run ruff check src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
git add config/market-data/sealed-btcusdt-4h-exchange-closures.json src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
git commit -m "feat: upgrade sealed closure contract to v2"
```

---

### Task 2: Add exact raw-row encoding and exclusion evidence

**Files:**
- Create: `src/gemini_trading/data/exclusions.py`
- Create: `tests/unit/data/test_candle_exclusions.py`
- Create: `tests/fixtures/market_data/partial_closure_btcusdt_4h.py`

**Interfaces:**
- Produces: `CandleExclusion`, `CandleExclusionManifest`, and `PartialCandleExclusionResult`.
- Produces: `canonical_binance_kline_row_bytes(row: object) -> bytes`.
- Produces: `match_and_exclude_partial_candles(*, pages: Sequence[RawPage], candidates: Sequence[Candle], closure_manifest: ExchangeClosureManifest) -> PartialCandleExclusionResult`.
- Produces canonical exclusion serialization and parsing.

- [ ] **Step 1: Write canonical-row digest tests**

Require the approved row to hash to the exact approved SHA-256 and add mutations for price, volume, close time, trade count, row length, row order, and numeric type.

- [ ] **Step 2: Write exclusion matching tests**

Require one exact exclusion, unchanged raw bytes, correct page sequence, row index, candidate index, and filtered canonical candidates.

- [ ] **Step 3: Add fatal-path tests**

Reject missing, duplicate, extra, overlong, misaligned, timestamp-shifted, OHLCV-mismatched, and hash-mismatched partial candles.

- [ ] **Step 4: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_candle_exclusions.py -q
```

- [ ] **Step 5: Implement exact matching and canonical exclusion serialization**

Flatten decoded raw rows in page/row order, verify one-to-one order against normalized candidates, locate exactly one approved partial row, emit deterministic evidence, remove only that candidate, and reject every other non-full-timeframe candidate.

- [ ] **Step 6: Run focused tests and commit**

```bash
uv run pytest tests/unit/data/test_candle_exclusions.py -q
uv run pyright src/gemini_trading/data/exclusions.py tests/unit/data/test_candle_exclusions.py
git add src/gemini_trading/data/exclusions.py tests/unit/data/test_candle_exclusions.py tests/fixtures/market_data/partial_closure_btcusdt_4h.py
git commit -m "feat: add exact partial-candle exclusion evidence"
```

---

### Task 3: Validate the unified eight-slot closure and derive segments

**Files:**
- Modify: `src/gemini_trading/data/segments.py`
- Modify: `tests/unit/data/test_candle_segments.py`

- [ ] Write tests requiring the post-exclusion jump from `2018-02-07T20:00:00Z` to `2018-02-09T08:00:00Z`, one closure, and two segments.
- [ ] Add rejection tests for wrong counts, shifted bounds, unused declarations, extra gaps, and an unexcluded partial candle.
- [ ] Run the focused tests and confirm RED.
- [ ] Match observed discontinuities with `(canonical_gap_start, resumed_open)` and verify count arithmetic.
- [ ] Run tests and commit as `feat: validate unified partial closure segments`.

---

### Task 4: Introduce dataset identity version 3

**Files:**
- Modify: `src/gemini_trading/domain/dataset.py`
- Modify: `src/gemini_trading/data/datasets/canonical_writer.py`
- Modify: related dataset tests.

- [ ] Write tests requiring `candle-dataset-v3`, exclusion hash/count fields, and identity changes for any candle, closure, exclusion, or segment mutation.
- [ ] Run focused tests and confirm RED.
- [ ] Extend immutable domain contracts and the canonical identity payload without changing v1/v2 meaning.
- [ ] Run dataset/domain tests and commit as `feat: bind exclusions into candle dataset v3`.

---

### Task 5: Persist exclusion evidence and produce v3 during ingestion

**Files:**
- Modify: storage protocols and local immutable storage.
- Modify: `src/gemini_trading/data/ingestion/service.py`.
- Modify: ingestion and storage tests.

- [ ] Write immutable storage tests for run-level and dataset-level `candle-exclusions.json`.
- [ ] Write ingestion success/failure tests covering unchanged raw bytes, one exclusion, two segments, and v3 publication.
- [ ] Run focused tests and confirm RED.
- [ ] Implement the order: store raw pages → normalize → complete-filter → exact partial match/exclusion → segment → write v3 dataset.
- [ ] Run tests and commit as `feat: persist partial-candle exclusions during ingestion`.

---

### Task 6: Reproduce exclusions in replay and independent verification

**Files:**
- Modify: replay and verification services and tests.

- [ ] Add provider-free replay tests requiring byte equality for all v3 evidence.
- [ ] Add tamper tests for raw row, page hash, row/candidate indices, exclusion fields, all manifest hashes, candle bytes, and dataset ID.
- [ ] Run focused tests and confirm RED.
- [ ] Rebuild exclusion evidence from raw pages rather than trusting persisted exclusion fields.
- [ ] Run tests and commit as `feat: replay and verify candle exclusions`.

---

### Task 7: Upgrade verified loading and Stage 1 handoff to v3

**Files:**
- Modify: `src/gemini_trading/research/dataset_reader.py`.
- Modify: `src/gemini_trading/strategy/handoff.py`.
- Modify: reader and handoff tests.

- [ ] Add tests rejecting v1/v2, missing/extra exclusions, hash mismatch, path traversal, and irreproducible exclusions.
- [ ] Require exact paths, hashes, counts, row digest, closure ID, and segment boundaries.
- [ ] Run focused tests and confirm RED.
- [ ] Implement v3-only sealed loading and handoff fields.
- [ ] Run tests and commit as `feat: upgrade sealed dataset handoff to v3`.

---

### Task 8: Propagate v3 identity through sealed study evidence

**Files:**
- Modify only strategy modules and tests that currently bind v2 closure/segment identity.

- [ ] Locate propagation points with `git grep`.
- [ ] Add pre-final, final, replay, and independent-verification tests for exclusion identity mismatch.
- [ ] Implement minimal identity propagation without changing features, labels, models, costs, thresholds, splits, or final-access logic.
- [ ] Run strategy tests and commit as `feat: bind exclusion identity through sealed studies`.

---

### Task 9: Update CLI commands and protected workflows

**Files:**
- Modify historical-validation CLI.
- Modify both sealed workflows.
- Modify CLI/workflow acceptance tests.

- [ ] Require Stage 1 artifact inventory to contain exclusion evidence.
- [ ] Require Stage 2 v3, counts `1/1/2`, exact closure ID, and exact excluded-row SHA-256.
- [ ] Prove no operator closure/exclusion path or environment override exists.
- [ ] Run acceptance tests and commit as `feat: require v3 exclusion evidence in sealed workflows`.

---

### Task 10: Complete integration, tamper, and documentation coverage

- [ ] Add end-to-end synthetic Stage 1 tests covering ingest, replay, verify, load, and handoff.
- [ ] Add the complete raw/declaration/exclusion/segment/dataset/inventory/handoff tamper matrix.
- [ ] Update operator documentation and README with the v3 artifact inventory and approval evidence.
- [ ] Run integration/acceptance tests and commit as `test: cover sealed partial-candle exclusion end to end`.

---

### Task 11: Run the complete repository gate

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

Review the diff to confirm no credentials, execution, model, threshold, cost, final-test, or unrelated refactor changes.

---

### Task 12: Protected merge and new Stage 1 execution

- [ ] Require exact-head GitHub CI for the complete gate and Gitleaks.
- [ ] Resolve all review threads and squash-merge with expected-head locking.
- [ ] Verify the exact merged-main commit.
- [ ] Launch a completely new Stage 1 run from that exact `main` commit.
- [ ] Independently inspect and record v3 source commit, workflow/artifact IDs, retrieval/dataset IDs, closure/exclusion/segment hashes, counts, closure ID, excluded-row SHA-256, boundary indices, candle bounds, inventory hash, replay success, and verification success.
- [ ] Keep Stage 2 blocked until the exact dataset approval marker is posted in Issue #22 after artifact review.

---

## Plan Self-Review

- Spec coverage: all architecture, identity, failure, testing, workflow, and migration requirements map to Tasks 1–12.
- Placeholder scan: no deferred requirement remains.
- Type consistency: closure v2 feeds exclusion matching; exclusion evidence feeds dataset v3; v3 feeds storage, replay, verification, reader, handoff, CLI, workflows, and sealed-study identity.
- Scope check: no strategy behavior, execution capability, final-test rule, model configuration, or unrelated refactor is included.
