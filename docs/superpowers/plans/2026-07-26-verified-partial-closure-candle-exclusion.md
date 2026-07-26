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

Use one compact newline-terminated JSON document containing:

```json
{"schema_version":"exchange-closure-manifest-v2","provider":"binance_spot","instrument":{"symbol":"BTCUSDT","base_asset":"BTC","quote_asset":"USDT"},"timeframe":"4h","start_time":"2018-01-01T00:00:00Z","end_time":"2026-07-01T00:00:00Z","closures":[{"closure_id":"binance-spot-system-upgrade-2018-02-08","canonical_gap_start":"2018-02-08T00:00:00Z","resumed_open":"2018-02-09T08:00:00Z","unavailable_candle_count":8,"fully_missing_start":"2018-02-08T04:00:00Z","fully_missing_candle_count":7,"reason_code":"exchange_system_upgrade","governance_reference":"github-issue-22","partial_candle":{"open_time":"2018-02-08T00:00:00Z","actual_close_time":"2018-02-08T00:28:14.788Z","expected_close_time":"2018-02-08T03:59:59.999Z","provider_row_sha256":"6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775","exclusion_reason":"exchange_closed_mid_candle"}}]}
```

- [ ] **Step 2: Write failing parser tests**

Add tests requiring:

```python
manifest.schema_version == "exchange-closure-manifest-v2"
closure.canonical_gap_start == utc("2018-02-08T00:00:00Z")
closure.unavailable_candle_count == 8
closure.partial_candle.provider_row_sha256 == EXPECTED_ROW_SHA256
```

Also require rejection of v1, unknown fields, missing partial-candle fields, invalid SHA-256, non-UTC values, misaligned expected close, incorrect unavailable counts, and a partial open different from `canonical_gap_start`.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -q
```

Expected: failures because v2 fields and `PartialCandleDeclaration` do not exist.

- [ ] **Step 4: Implement the minimal immutable v2 contracts**

Add:

```python
@dataclass(frozen=True, slots=True)
class PartialCandleDeclaration:
    open_time: datetime
    actual_close_time: datetime
    expected_close_time: datetime
    provider_row_sha256: str
    exclusion_reason: str
```

Update `ExchangeClosure` with `canonical_gap_start`, `unavailable_candle_count`, `fully_missing_start`, `fully_missing_candle_count`, and `partial_candle`. Validate exact timeframe arithmetic and canonical serialization.

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
- Produces: `serialize_candle_exclusion_manifest(...)` and `load_candle_exclusion_manifest(...)`.

- [ ] **Step 1: Write canonical-row digest tests**

Require the approved row to encode exactly as compact JSON and hash to:

```text
6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775
```

Add mutation tests for price, volume, close time, trade count, row length, row order, and numeric type changes.

- [ ] **Step 2: Write exclusion matching tests**

Use synthetic `RawPage` objects and normalized candidates to require:

```python
result.canonical_candidates == candidates_without_partial
result.manifest.schema_version == "candle-exclusion-manifest-v1"
result.manifest.exclusions[0].raw_page_sequence == 1
result.manifest.exclusions[0].row_index == APPROVED_ROW_INDEX
result.manifest.exclusions[0].canonical_candidate_index == APPROVED_CANDIDATE_INDEX
```

Require raw page bytes to remain byte-identical before and after matching.

- [ ] **Step 3: Add fatal-path tests**

Reject missing, duplicate, extra, overlong, misaligned, timestamp-shifted, OHLCV-mismatched, and hash-mismatched partial candles. Reject an exclusion declaration that matches a raw row but not the corresponding normalized candidate.

- [ ] **Step 4: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_candle_exclusions.py -q
```

Expected: import failure for `gemini_trading.data.exclusions`.

- [ ] **Step 5: Implement exact matching and canonical exclusion serialization**

The implementation must flatten decoded raw rows in page/row order, verify one-to-one order against normalized candidates, locate exactly one approved partial row, emit deterministic evidence, remove only that candidate, and reject every other non-full-timeframe candidate.

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

**Interfaces:**
- Consumes: canonical candidates after exclusion and `ExchangeClosureManifest` v2.
- Produces: the existing `CandleSegmentManifest`, now matching `(canonical_gap_start, resumed_open)`.

- [ ] **Step 1: Write failing segment tests**

Require the post-exclusion sequence to jump from `2018-02-07T20:00:00Z` to `2018-02-09T08:00:00Z`, match one closure, and produce exactly two segments.

- [ ] **Step 2: Add rejection tests**

Reject a seven-slot declaration, a resumed open shifted by one timeframe, incorrect unavailable count, unused declaration, extra gap, and any partial candle that reaches segmentation without prior exclusion.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_candle_segments.py -q
```

- [ ] **Step 4: Update exact closure matching**

Match observed canonical discontinuities with `(closure.canonical_gap_start, closure.resumed_open)` and verify `unavailable_candle_count` from timeframe arithmetic.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/data/test_candle_segments.py -q
git add src/gemini_trading/data/segments.py tests/unit/data/test_candle_segments.py
git commit -m "feat: validate unified partial closure segments"
```

---

### Task 4: Introduce dataset identity version 3

**Files:**
- Modify: `src/gemini_trading/domain/dataset.py`
- Modify: `src/gemini_trading/data/datasets/canonical_writer.py`
- Modify: related dataset manifest tests.

**Interfaces:**
- Consumes: canonical candles, closure-manifest bytes, exclusion-manifest bytes, and segment-manifest bytes.
- Produces: `candle-dataset-v3` manifests and identities binding all four byte streams.

- [ ] **Step 1: Write failing v3 identity tests**

Require fields:

```python
manifest.schema_version == "candle-dataset-v3"
manifest.candle_exclusion_manifest_sha256 == sha256(exclusion_bytes)
manifest.exclusion_count == 1
```

Require dataset ID changes when any candle, closure, exclusion, or segment byte changes.

- [ ] **Step 2: Run focused tests and confirm RED**

Run the exact dataset-domain and canonical-writer test files identified by `git grep "candle-dataset-v2" tests`.

- [ ] **Step 3: Extend immutable domain contracts and identity payload**

Add exclusion hash/count fields without changing v1/v2 interpretation. Construct v3 identity from stable scope fields plus the four SHA-256 values.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/data tests/unit/domain -q
git add src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py tests
git commit -m "feat: bind exclusions into candle dataset v3"
```

---

### Task 5: Persist exclusion evidence and produce v3 during ingestion

**Files:**
- Modify: `src/gemini_trading/data/storage/base.py`
- Modify: `src/gemini_trading/data/storage/local_immutable.py`
- Modify: `src/gemini_trading/data/ingestion/service.py`
- Modify: ingestion and storage tests.

**Interfaces:**
- Adds raw/canonical storage methods for `candle-exclusions.json`.
- Ingestion order becomes: store raw pages → normalize → complete-filter → exact partial match/exclusion → segment → write v3 dataset.

- [ ] **Step 1: Write failing storage tests**

Require immutable write/read paths for run-level and dataset-level exclusion evidence, canonical bytes, collision rejection, and traversal protection.

- [ ] **Step 2: Write failing ingestion success and failure tests**

Success must preserve the raw page, exclude one candidate, persist one exclusion, produce two segments, and return a v3 dataset. Failure variants must write only a failed retrieval manifest and no canonical dataset.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/storage tests/unit/data/ingestion -q
```

- [ ] **Step 4: Implement storage protocols and ingestion orchestration**

Ensure the exact raw row is never rewritten. Append exclusion evidence to `IngestionResult.paths` and bind it into the v3 manifest before canonical publication.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/data/storage tests/unit/data/ingestion -q
git add src/gemini_trading/data/storage src/gemini_trading/data/ingestion tests
git commit -m "feat: persist partial-candle exclusions during ingestion"
```

---

### Task 6: Reproduce exclusions in replay and independent verification

**Files:**
- Modify: `src/gemini_trading/data/ingestion/replay.py`
- Modify: `src/gemini_trading/data/verification/service.py`
- Modify: replay and verification tests.

**Interfaces:**
- Replay must reconstruct the exact exclusion from raw pages and reproduce byte-identical closure, exclusion, segment, candle, and dataset manifests.
- Verification must independently recompute the provider-row digest, row location, candidate index, all manifest hashes, and v3 identity.

- [ ] **Step 1: Add failing provider-free replay tests**

Require replay success without network access and byte equality for every v3 evidence file.

- [ ] **Step 2: Add failing tamper tests**

Tamper each of: raw row, page hash, row index, candidate index, exclusion reason, exclusion hash, closure hash, segment hash, canonical candle bytes, and dataset ID. Every mutation must fail closed.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/ingestion/test_replay.py tests/unit/data/verification -q
```

- [ ] **Step 4: Implement deterministic replay and independent recomputation**

Do not trust persisted exclusion fields without rebuilding them from raw evidence.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/data/ingestion/test_replay.py tests/unit/data/verification -q
git add src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification/service.py tests
git commit -m "feat: replay and verify candle exclusions"
```

---

### Task 7: Upgrade verified loading and Stage 1 handoff to v3

**Files:**
- Modify: `src/gemini_trading/research/dataset_reader.py`
- Modify: `src/gemini_trading/strategy/handoff.py`
- Modify: related reader and handoff tests.

**Interfaces:**
- `VerifiedDataset` must expose exclusion evidence and retain two segment boundaries.
- Handoff must bind schema v3, one closure, one exclusion, two segments, exact closure ID, exact excluded-row SHA-256, and boundary indices.

- [ ] **Step 1: Write failing reader tests**

Require rejection of v1/v2, missing exclusion files, hash mismatch, extra exclusions, and a v3 dataset whose exclusion cannot be independently reproduced.

- [ ] **Step 2: Write failing handoff tests**

Require exact relative paths, SHA-256 values, counts, row digest, closure ID, and segment boundaries. Retain all current path-traversal and inventory protections.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/research/test_dataset_reader.py tests/unit/strategy/test_handoff.py -q
```

- [ ] **Step 4: Implement v3 reader and handoff fields**

Keep old schemas explicitly unsupported at the sealed boundary rather than upgrading them in memory.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/research/test_dataset_reader.py tests/unit/strategy/test_handoff.py -q
git add src/gemini_trading/research/dataset_reader.py src/gemini_trading/strategy/handoff.py tests
git commit -m "feat: upgrade sealed dataset handoff to v3"
```

---

### Task 8: Propagate v3 identity through sealed study evidence

**Files:**
- Modify only the strategy modules and tests that currently assert `candle-dataset-v2`, closure count, segment count, or closure identity.

**Interfaces:**
- Existing segment-local features, labels, schedules, folds, simulator boundary guards, final-test seal, replay, and verification behavior remain unchanged.
- Every sealed evidence object must bind the v3 dataset and exclusion identity.

- [ ] **Step 1: Locate exact propagation points**

```bash
git grep -n "candle-dataset-v2\|closure_count\|segment_count\|closure_ids" src/gemini_trading/strategy tests
```

- [ ] **Step 2: Add failing identity-propagation tests**

Require pre-final, final, replay, and independent study verification to reject exclusion hash/count or excluded-row-digest mismatch.

- [ ] **Step 3: Implement minimal identity propagation**

Do not change feature calculations, labels, models, costs, thresholds, splits, or final-access logic.

- [ ] **Step 4: Run strategy tests and commit**

```bash
uv run pytest tests/unit/strategy tests/integration -q
git add src/gemini_trading/strategy tests
git commit -m "feat: bind exclusion identity through sealed studies"
```

---

### Task 9: Update CLI commands and protected workflows

**Files:**
- Modify: `src/gemini_trading/cli/historical_validation.py`
- Modify: `.github/workflows/sealed-btcusdt-dataset.yml`
- Modify: `.github/workflows/sealed-btcusdt-study.yml`
- Modify: workflow and CLI acceptance tests.

**Interfaces:**
- Stage 1 artifact inventory must include `candle-exclusions.json`.
- Stage 2 must require `candle-dataset-v3`, closure count `1`, exclusion count `1`, segment count `2`, exact closure ID, and exact excluded provider-row SHA-256.

- [ ] **Step 1: Add failing CLI and workflow acceptance tests**

Require no operator-supplied closure or exclusion path, no environment override, and fixed sealed commands only.

- [ ] **Step 2: Update CLI output and handoff construction**

Expose safe identifiers and evidence paths only; do not print raw page contents.

- [ ] **Step 3: Update workflows**

Keep exact-`main`, clean-worktree, research-mode, timeout, replay, verification, handoff, and upload gates. Add v3 exclusion assertions and artifact inventory.

- [ ] **Step 4: Run acceptance tests and commit**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_workflows.py tests/acceptance/test_historical_validation_cli.py -q
git add src/gemini_trading/cli .github/workflows tests/acceptance
git commit -m "feat: require v3 exclusion evidence in sealed workflows"
```

---

### Task 10: Complete tamper, integration, and documentation coverage

**Files:**
- Modify: sealed integration and tamper tests.
- Modify: `docs/operations/sealed-btcusdt-historical-validation.md`
- Modify: `README.md`

**Interfaces:**
- Produces a complete Stage 1 v3 artifact contract and operator checklist.

- [ ] **Step 1: Add end-to-end synthetic Stage 1 tests**

Use the approved-shaped partial fixture to ingest, replay, verify, load, and build the v3 handoff. Assert unchanged raw bytes, one exclusion, eight unavailable canonical slots, and two segments.

- [ ] **Step 2: Add complete tamper matrix**

Cover every raw, declaration, exclusion, segment, dataset, inventory, handoff, replay, and verification identity field.

- [ ] **Step 3: Update operator documentation**

Document the exact artifact inventory, hashes, counts, row digest, boundary indices, Stage 1 approval evidence, and continued Stage 2 prohibition.

- [ ] **Step 4: Run focused integration/acceptance tests and commit**

```bash
uv run pytest tests/integration tests/acceptance -q
git add tests docs README.md
git commit -m "test: cover sealed partial-candle exclusion end to end"
```

---

### Task 11: Run the complete repository gate

**Files:**
- No intentional production changes unless a gate exposes a defect caused by Tasks 1–10.

- [ ] **Step 1: Run formatting and linting**

```bash
uv run ruff format --check .
uv run ruff check .
```

- [ ] **Step 2: Run strict typing**

```bash
uv run pyright
```

- [ ] **Step 3: Run the complete test suite**

```bash
uv run pytest
```

Expected: all tests pass; the bounded public API smoke test may remain skipped under its existing environment guard.

- [ ] **Step 4: Run build and repository gates**

```bash
uv run python -m build
uv run pip-audit
python scripts/validate_tracked_files.py
uv run detect-secrets scan --all-files --baseline .secrets.baseline
```

- [ ] **Step 5: Review diff scope**

Confirm no credentials, order submission, broker/exchange execution, model changes, threshold changes, cost changes, final-test changes, or unrelated refactoring entered the branch.

- [ ] **Step 6: Commit any gate-only corrections**

Use narrowly scoped commit messages that identify the exact defect. Do not squash until protected PR verification is complete.

---

### Task 12: Protected merge and new Stage 1 execution

**Files:**
- No code changes expected.

- [ ] **Step 1: Require exact-head GitHub CI**

The exact PR head must pass frozen dependency sync, Ruff format/lint, Pyright, complete pytest, build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks.

- [ ] **Step 2: Mark the PR ready and review all threads**

No unresolved review thread, requested change, stale check, or moving head may remain.

- [ ] **Step 3: Squash-merge with expected-head locking**

Record the resulting full `main` SHA in Issue #22.

- [ ] **Step 4: Verify exact merged-main CI**

Do not authorize Stage 1 until the exact merged commit passes the complete repository gate.

- [ ] **Step 5: Launch a completely new Stage 1 run**

Use **Actions → Sealed BTCUSDT Dataset → Run workflow → main**. Do not rerun an old workflow attempt.

- [ ] **Step 6: Independently review the Stage 1 v3 artifact**

Record in Issue #22:

- source commit and workflow run ID;
- artifact name and artifact ID;
- retrieval run ID and dataset ID;
- `candle-dataset-v3` schema;
- closure, exclusion, and segment manifest paths and SHA-256 values;
- closure count `1`, exclusion count `1`, segment count `2`;
- exact closure ID;
- excluded provider-row SHA-256;
- canonical boundary indices;
- candle count, first/last opens, inventory root hash;
- replay and independent-verification success.

- [ ] **Step 7: Keep Stage 2 blocked**

Stage 2 remains prohibited until the user posts the exact required dataset approval marker defined by the operator documentation after artifact review.

---

## Plan Self-Review

- Spec coverage: every architecture, identity, failure, testing, workflow, and migration requirement is assigned to Tasks 1–12.
- Placeholder scan: no `TBD`, `TODO`, deferred implementation, or unspecified validation step remains.
- Type consistency: closure v2 feeds exclusion matching; exclusion evidence feeds dataset v3; dataset v3 feeds storage, replay, verification, reader, handoff, CLI, workflows, and sealed-study identity.
- Scope check: no strategy behavior, execution capability, final-test rule, model configuration, or unrelated refactor is included.
