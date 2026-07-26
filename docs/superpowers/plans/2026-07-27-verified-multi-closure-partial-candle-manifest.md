# Verified Multi-Closure Partial-Candle Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the sealed BTCUSDT historical-validation pipeline from one exact partial-candle exclusion to the approved set of 20 Binance Spot interruptions, producing a fail-closed `candle-dataset-v4` and `sealed-dataset-handoff-v4` without changing strategy behavior or execution authority.

**Architecture:** Keep immutable raw Binance responses as the source of truth, declare all 20 interruptions in a fixed `exchange-closure-manifest-v3`, derive ordered exclusion and segment evidence, and bind every byte and count through ingestion, storage, replay, independent verification, verified loading, handoff, workflows, and sealed-study identities. Retain `candle-exclusion-manifest-v1`, `candle-segment-manifest-v1`, and `retrieval-manifest-v2`; introduce new versions rather than reinterpreting existing schemas.

**Tech Stack:** Python 3.12, frozen `uv`, dataclasses, canonical compact JSON/JSONL, SHA-256 content identities, pytest, Ruff, strict Pyright, GitHub Actions.

## Global Constraints

- Repository: `muhamedsohaib/gemini-trading`.
- Approved design: `docs/superpowers/specs/2026-07-27-verified-multi-closure-partial-candle-manifest-design.md`.
- Current implementation base: `cf8389f6b8964b5aee0563083f8bf362be33b1ab`; implementation starts only after PR #41 is merged and exact merged `main` is recorded.
- Implementation branch: `research/verified-multi-closure-partial-candle-manifest`, created from exact merged `main` in an isolated worktree.
- `RESEARCH_ONLY`; no paper, demo, live, production, credentials, private endpoints, order submission, leverage, futures, shorting, portfolio allocation, or capital authority.
- Public Binance Spot `BTCUSDT`, `4h`, window `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` only.
- Preserve raw response bytes and provider rows unchanged. Never repair timestamps, interpolate, fill, pad, or synthesize candles.
- Fixed identities: 18,602 returned rows; 20 partial rows; 16 fully missing opens; 36 unavailable slots; 18,582 canonical candles; 20 closures; 20 exclusions; 21 segments.
- Fixed segment boundaries: `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`.
- Fixed first and last canonical opens: `2018-01-01T00:00:00Z` and `2026-06-30T20:00:00Z`.
- New schemas: `exchange-closure-manifest-v3`, `candle-dataset-v4`, `sealed-dataset-handoff-v4`, `dataset-handoff-reference-v4`.
- Retained schemas: `retrieval-manifest-v2`, `candle-exclusion-manifest-v1`, `candle-segment-manifest-v1`.
- Existing v1-v3 sealed datasets and handoffs are invalid for the revised study.
- Strategy, features, labels, costs, thresholds, folds, final-test dates, long-or-cash policy, and single-final-access controls remain unchanged.
- Every production task follows RED → minimal GREEN → focused verification → commit.
- Never dispatch real Stage 1 or Stage 2 from a design or implementation branch.

## Approved Ordered Closure Identity

The source-controlled manifest must contain these ordered `(closure_id, provider_row_sha256)` pairs exactly:

```python
APPROVED_CLOSURE_ROWS = (
    ("binance-spot-infrastructure-maintenance-2018-01-04", "ce5df946e724e509699e24166fcd96bd566c48de7090b3a092aaa324bd73c426"),
    ("binance-spot-system-upgrade-2018-02-08", "6d0ed02c75960a3acf11073a2b7276e0bdc04f217fc99a488b15a5ff68e70775"),
    ("binance-spot-system-upgrade-2018-06-26", "31d7e347e1830772a39ab0bdf78e09af6ff3f3735cad745916fe32e6fe0fd557"),
    ("binance-spot-risk-control-suspension-2018-07-04", "1202a2e967f8907eab3917a36f9b5bb440e4ca6647779fdebefd50bcce61b5b8"),
    ("binance-spot-emergency-maintenance-2018-10-19", "3a06f4a8c191d42bebd2597f7c19932362f4d95f7fe7452f51c268209b629474"),
    ("binance-spot-system-upgrade-2018-11-14", "dd328080cdc59124c3a0467faf719f055dc208a03a229d89dbe0ec403ebf3ee8"),
    ("binance-spot-system-upgrade-2019-03-12", "455bc52eeca4bc7097498742c200d5ecc46019683ed37ea36ed2acb4f3d8478f"),
    ("binance-spot-security-upgrade-2019-05-15", "1021733a2305723bc1dad0dd8ebd8523fdc36839ef52353018d987429508efad"),
    ("binance-spot-system-upgrade-2019-08-15", "1f68a701351a2ae6917bf4a5d524885416dc7715a704af8e0db52d3938cff876"),
    ("binance-spot-system-upgrade-2019-11-13", "aee4ed92909f4b8e8c957370da2499c928d304374c7db303ffd591a370c2e609"),
    ("binance-spot-system-upgrade-2019-11-25", "2b11ed5d8fe5724c559ce91e5c922b0a98d3ae16a859eec895e128b5e1e9ac54"),
    ("binance-spot-market-data-maintenance-2020-02-19", "a756811ac8139d621c6fde28980d8019fef535d7f1e17b2d4310b10370d2ac53"),
    ("binance-spot-system-upgrade-2020-04-25", "7c11bd7bff7cd4815615ea6003cb3dbed08b214b78a2bbe722cfe22912592354"),
    ("binance-spot-system-upgrade-2020-06-28", "bbca0d86447c44964449be1ae5bf5968e391cffad1fb16aee136f07369553a01"),
    ("binance-spot-matching-engine-maintenance-2020-12-21", "b9208db0c003f68d77ffeeb7e9054c348f61ede5840db275f0d5baf84cfdd2c9"),
    ("binance-spot-matching-engine-maintenance-2021-02-11", "6336454bf83a67e99118f3405c3926c444668028f1c65518d509bdf19eab6cb4"),
    ("binance-spot-system-upgrade-2021-04-20", "bdf24e2e33ecdca4f2d6960f80dd62521e9588e72badd2497857fa4efc521393"),
    ("binance-spot-system-upgrade-2021-04-25", "d033c7c18ec2bc9b3b545a93b7d886e5e3f8c70331ffb07f2cf04fb631108d49"),
    ("binance-spot-system-upgrade-2021-08-13", "82ec6dfd6d5d034bd9dfa6c81a5fdcee87db14a998beb3d9dad6f3dbd860509d"),
    ("binance-spot-system-upgrade-2021-09-29", "ae05924001aab056ea72c61061f0b75db9aab01ca04ca6db69c7a01f09a99924"),
)
```

---

### Task 1: Merge the documentation gate and create an isolated implementation worktree

**Files:**
- Verify: `docs/superpowers/specs/2026-07-27-verified-multi-closure-partial-candle-manifest-design.md`
- Verify: `docs/superpowers/plans/2026-07-27-verified-multi-closure-partial-candle-manifest.md`

**Interfaces:**
- Consumes: approved draft PR #41 containing documentation only.
- Produces: exact merged-main SHA and a clean implementation branch/worktree.

- [ ] Verify PR #41 contains only the spec and plan:

```bash
gh pr view 41 --json files,headRefOid,mergeable,state
```

Expected: two documentation files and no source, workflow, configuration, fixture, or test change.

- [ ] Run documentation contract tests:

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_documentation.py tests/acceptance/test_sealed_historical_validation_workflows.py -q
```

Expected: PASS.

- [ ] Mark ready, wait for required checks, and squash-merge:

```bash
gh pr ready 41
gh pr checks 41 --watch
gh pr merge 41 --squash --delete-branch
```

- [ ] Resolve exact merged `main` and record it in Issue #22:

```bash
git fetch origin
git switch main
git reset --hard origin/main
test -z "$(git status --porcelain)"
git rev-parse HEAD
```

- [ ] Create the isolated worktree:

```bash
git worktree add ../gemini-trading-multiclosure -b research/verified-multi-closure-partial-candle-manifest "$(git rev-parse origin/main)"
cd ../gemini-trading-multiclosure
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

No source commit is created in this task.

---

### Task 2: Upgrade the fixed closure manifest to v3 and allow zero fully missing slots

**Files:**
- Modify: `config/market-data/sealed-btcusdt-4h-exchange-closures.json`
- Modify: `src/gemini_trading/data/exchange_closures.py`
- Modify: `tests/unit/data/test_exchange_closures.py`

**Interfaces:**
- Consumes: exact inventory in the approved spec.
- Produces: canonical `ExchangeClosureManifest` v3 with 20 ordered unique closures and valid zero-missing arithmetic.

- [ ] Add RED tests:

```python
def test_fixed_manifest_is_exact_v3_and_complete() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.schema_version == "exchange-closure-manifest-v3"
    assert len(manifest.closures) == 20
    assert sum(item.unavailable_candle_count for item in manifest.closures) == 36
    assert sum(item.fully_missing_candle_count for item in manifest.closures) == 16
    assert tuple((c.closure_id, c.partial_candle.provider_row_sha256) for c in manifest.closures) == APPROVED_CLOSURE_ROWS


def test_zero_fully_missing_closure_resumes_at_next_open() -> None:
    closure = next(c for c in load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)[0].closures if c.fully_missing_candle_count == 0)
    assert closure.unavailable_candle_count == 1
    assert closure.fully_missing_start == closure.resumed_open
```

Also add rejection tests for v2, negative count, inconsistent count arithmetic, shifted resumption, duplicate IDs, duplicate partial opens, duplicate provider-row digests, unordered entries, overlap, and touching entries.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -q
```

Expected: current v2 loader rejects v3 and zero missing.

- [ ] Implement minimal v3 rules in `exchange_closures.py`:
  - `_SCHEMA_VERSION = "exchange-closure-manifest-v3"`;
  - `fully_missing_candle_count >= 0`;
  - `fully_missing_start == canonical_gap_start + timeframe.duration`;
  - `unavailable_candle_count == fully_missing_candle_count + 1`;
  - `resumed_open == canonical_gap_start + unavailable_candle_count * timeframe.duration`;
  - unique closure IDs, partial opens, and provider-row digests;
  - strictly ordered, non-overlapping, non-touching closures.

- [ ] Replace the fixed JSON with the exact 20 entries and update `_FIXED_SHA256` from canonical bytes.

- [ ] Verify GREEN and quality:

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -q
uv run ruff check src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
uv run pyright src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
```

- [ ] Commit:

```bash
git add config/market-data/sealed-btcusdt-4h-exchange-closures.json src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
git commit -m "feat: declare verified Binance closure inventory v3"
```

---

### Task 3: Generalize exact partial-row exclusion across pages

**Files:**
- Modify: `src/gemini_trading/data/exclusions.py`
- Modify: `tests/unit/data/test_candle_exclusions.py`

**Interfaces:**
- Consumes: ordered v3 closure declarations and immutable `RawPage` sequences.
- Produces: canonical completed candles plus ordered `CandleExclusionManifest` v1 entries, exactly one per closure.

- [ ] Add RED tests for two declarations split across two raw pages, including one zero-missing and one nonzero-missing closure:

```python
def test_multiple_declared_partial_rows_across_pages_are_excluded_in_canonical_order() -> None:
    result = match_and_exclude_partial_candles(pages, normalized_pages, manifest, server_time=SERVER_TIME)
    assert tuple(item.closure_id for item in result.manifest.exclusions) == tuple(item.closure_id for item in manifest.closures)
    assert tuple(item.provider_row_sha256 for item in result.manifest.exclusions) == tuple(item.partial_candle.provider_row_sha256 for item in manifest.closures)
    assert all(candle.completed for candle in result.candles)
    assert b"partial-row-marker" in pages[0].response_bytes
```

Add failure tests for missing, duplicate, reordered, altered, additional early-close, late-close, overlong, misaligned, duplicate-open, row/page hash mismatch, a row inside a non-empty missing interval, and absent/duplicated resumed open.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/data/test_candle_exclusions.py -q
```

- [ ] Implement minimal changes:
  - index declarations by open time without losing manifest order;
  - scan every row once while retaining page and global positions;
  - exact-match actual close, expected close, row digest, normalized values, and server-close state;
  - reject every undeclared abnormal row;
  - require every declaration exactly once;
  - validate empty and non-empty absent-open sets;
  - sort derived exclusions by `canonical_index_before_removal` and assert their closure IDs/digests equal manifest order.

- [ ] Verify GREEN:

```bash
uv run pytest tests/unit/data/test_candle_exclusions.py -q
uv run ruff check src/gemini_trading/data/exclusions.py tests/unit/data/test_candle_exclusions.py
uv run pyright src/gemini_trading/data/exclusions.py tests/unit/data/test_candle_exclusions.py
```

- [ ] Commit:

```bash
git add src/gemini_trading/data/exclusions.py tests/unit/data/test_candle_exclusions.py
git commit -m "feat: exclude exact multi-page partial candles"
```

---

### Task 4: Derive 21 exact continuous segments

**Files:**
- Create: `tests/fixtures/market_data/multi_closure_btcusdt_4h.py`
- Modify: `src/gemini_trading/data/segments.py` only if the existing generic algorithm fails the new tests.
- Modify: `tests/unit/data/test_candle_segments.py`
- Rename: `tests/integration/test_market_data_exchange_closure_v2.py` → `tests/integration/test_market_data_exchange_closure_v3.py`

**Interfaces:**
- Consumes: canonical candles after all exclusions and closure manifest v3.
- Produces: canonical `CandleSegmentManifest` v1 with 21 maximal segments and exact boundary tuple.

- [ ] Add a compact synthetic fixture containing both zero-missing and nonzero-missing closures.

- [ ] Add RED tests:

```python
def test_declared_multi_closure_sequence_produces_all_segments() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)
    assert len(segments.segments) == len(MANIFEST.closures) + 1
    assert segments.boundary_indices == EXPECTED_BOUNDARIES
    assert tuple(s.preceding_closure_id for s in segments.segments[1:]) == tuple(c.closure_id for c in MANIFEST.closures)
```

Add rejection tests for unused declaration, repeated declaration, shifted resumption, undeclared extra gap, overlapping/touching declaration, and boundary-order mismatch.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/data/test_candle_segments.py tests/integration/test_market_data_exchange_closure_v3.py -q
```

- [ ] Make the smallest required production change. Do not change `candle-segment-manifest-v1` if the existing implementation is already generic.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/unit/data/test_candle_segments.py tests/integration/test_market_data_exchange_closure_v3.py -q
uv run ruff check src/gemini_trading/data/segments.py tests/fixtures/market_data/multi_closure_btcusdt_4h.py tests/unit/data/test_candle_segments.py tests/integration/test_market_data_exchange_closure_v3.py
git add src/gemini_trading/data/segments.py tests/fixtures/market_data/multi_closure_btcusdt_4h.py tests/unit/data/test_candle_segments.py tests/integration/test_market_data_exchange_closure_v3.py
git commit -m "test: verify deterministic multi-closure segments"
```

---

### Task 5: Introduce `candle-dataset-v4`

**Files:**
- Modify: `src/gemini_trading/domain/dataset.py`
- Modify: `src/gemini_trading/data/datasets/canonical_writer.py`
- Modify: `tests/unit/data/datasets/test_canonical_writer.py`

**Interfaces:**
- Produces:

```python
def dataset_id_v4(*, provider: str, instrument: Instrument, timeframe: Timeframe, start_time: datetime, end_time: datetime, canonical_bytes: bytes, closure_manifest_bytes: bytes, exclusion_manifest_bytes: bytes, segment_manifest_bytes: bytes) -> str: ...
```

- [ ] Add RED tests proving v4 binds all four byte streams and changes identity when any one byte stream changes.

- [ ] Add manifest tests requiring supporting hashes and exact count relation `closure_count == exclusion_count` and `segment_count == closure_count + 1`.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/data/datasets/test_canonical_writer.py -q
```

- [ ] Implement `dataset_id_v4`, v4 parsing/serialization rules, and v4 manifest construction. Keep v3 behavior unchanged.

- [ ] Verify GREEN:

```bash
uv run pytest tests/unit/data/datasets/test_canonical_writer.py -q
uv run ruff check src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py tests/unit/data/datasets/test_canonical_writer.py
uv run pyright src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py tests/unit/data/datasets/test_canonical_writer.py
```

- [ ] Commit:

```bash
git add src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py tests/unit/data/datasets/test_canonical_writer.py
git commit -m "feat: add sealed candle dataset v4 identity"
```

---

### Task 6: Publish v4 through ingestion and immutable storage

**Files:**
- Modify: `src/gemini_trading/data/ingestion/service.py`
- Modify: `tests/unit/data/ingestion/test_service.py`
- Modify: `tests/integration/test_storage_adapter_equivalence.py`

**Interfaces:**
- Consumes: closure v3, exclusions v1, segments v1.
- Produces: v4 canonical dataset, unchanged raw pages, supporting manifests, retrieval evidence, and provenance.

- [ ] Add RED ingestion tests asserting schema v4, counts 20/20/21 in complete fixtures, unchanged raw bytes, and supporting paths `exchange-closures.json`, `candle-exclusions.json`, `candle-segments.json`.

- [ ] Add failure tests proving no canonical dataset is published when one declaration is missing, an abnormal undeclared row appears, or a supporting write conflicts.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/data/ingestion/test_service.py tests/integration/test_storage_adapter_equivalence.py -q
```

- [ ] Change sealed ingestion from `_DATASET_SCHEMA_VERSION_V3` to v4 and preserve `retrieval-manifest-v2`.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/unit/data/ingestion/test_service.py tests/integration/test_storage_adapter_equivalence.py -q
uv run ruff check src/gemini_trading/data/ingestion/service.py tests/unit/data/ingestion/test_service.py tests/integration/test_storage_adapter_equivalence.py
git add src/gemini_trading/data/ingestion/service.py tests/unit/data/ingestion/test_service.py tests/integration/test_storage_adapter_equivalence.py
git commit -m "feat: publish multi-closure dataset v4"
```

---

### Task 7: Reproduce and independently verify v4 provider-free

**Files:**
- Modify: `src/gemini_trading/data/ingestion/replay.py`
- Modify: `src/gemini_trading/data/verification/service.py`
- Modify: `tests/integration/test_sealed_historical_validation.py`

**Interfaces:**
- Consumes: immutable raw pages, retrieval v2, closure v3, stored canonical/supporting evidence.
- Produces: byte-identical replay and independent v4 verification.

- [ ] Add RED integration assertions for 20 exclusions, 21 segments, exact boundary tuple, 18,582 candles in the complete-window contract fixture, and v4 dataset identity.

- [ ] Add tamper tests for closure ordering, exclusion ordering, row digest, page location, segment boundary, count, canonical byte, and dataset ID changes.

- [ ] Confirm RED:

```bash
uv run pytest tests/integration/test_sealed_historical_validation.py -q
```

- [ ] Update replay and verification to expect v4 when closure evidence exists. Independently recompute all matches, empty/non-empty missing sets, segment bytes, counts, and dataset identity.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/integration/test_sealed_historical_validation.py -q
uv run ruff check src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification/service.py tests/integration/test_sealed_historical_validation.py
git add src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification/service.py tests/integration/test_sealed_historical_validation.py
git commit -m "feat: replay and verify multi-closure dataset v4"
```

---

### Task 8: Load verified v4 datasets strictly

**Files:**
- Modify: `src/gemini_trading/research/dataset_reader.py`
- Modify: `tests/integration/test_research_dataset_reader.py`

**Interfaces:**
- Produces: `load_verified_dataset(..., require_v4=True) -> VerifiedDataset`.

- [ ] Add RED tests that accept exact v4 and reject v1-v3 when `require_v4=True`.

- [ ] Add tests requiring closure/exclusion/segment order equality, count equality, exact declaration-to-exclusion timestamp/digest equality, and v4 content identity.

- [ ] Confirm RED:

```bash
uv run pytest tests/integration/test_research_dataset_reader.py -q
```

- [ ] Add v4 manifest fields, use `dataset_id_v4`, and retain legacy loading only when no v4 requirement is requested.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/integration/test_research_dataset_reader.py -q
uv run ruff check src/gemini_trading/research/dataset_reader.py tests/integration/test_research_dataset_reader.py
git add src/gemini_trading/research/dataset_reader.py tests/integration/test_research_dataset_reader.py
git commit -m "feat: require verified dataset v4 for sealed research"
```

---

### Task 9: Introduce plural excluded-row identities in handoff v4

**Files:**
- Modify: `src/gemini_trading/strategy/handoff.py`
- Modify: `src/gemini_trading/cli/historical_validation.py`
- Modify: `tests/unit/strategy/test_handoff.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True, slots=True)
class ExcludedProviderRow:
    closure_id: str
    provider_row_sha256: str

@dataclass(frozen=True, slots=True)
class DatasetHandoffManifest:
    ...
    excluded_provider_rows: tuple[ExcludedProviderRow, ...]
```

- [ ] Add RED tests requiring schema `sealed-dataset-handoff-v4`, dataset `candle-dataset-v4`, counts `(20, 20, 21)`, exact ordered closure-row pairs, exact boundaries, and 18,582 candles.

- [ ] Add rejection tests for legacy scalar `excluded_provider_row_sha256`, reordered/missing/extra pairs, duplicate IDs/digests, count mismatch, path traversal, supporting hash mismatch, and inventory mismatch.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/strategy/test_handoff.py -q
```

- [ ] Implement canonical plural serialization/parsing and verification. In `verify_dataset_handoff`, compare the ordered closure manifest, exclusion manifest, and `excluded_provider_rows` element-for-element.

- [ ] Update CLI constants to the exact 20 pairs, boundaries, count 18,582; call `load_verified_dataset(..., require_v4=True)`; emit v4 handoff.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/unit/strategy/test_handoff.py -q
uv run ruff check src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py tests/unit/strategy/test_handoff.py
uv run pyright src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py tests/unit/strategy/test_handoff.py
git add src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py tests/unit/strategy/test_handoff.py
git commit -m "feat: add plural sealed dataset handoff v4 identity"
```

---

### Task 10: Propagate v4 through pre-final and sealed-study evidence

**Files:**
- Modify: `src/gemini_trading/strategy/pre_final.py`
- Modify: `src/gemini_trading/strategy/replay.py`
- Modify: `src/gemini_trading/strategy/sealed_evaluator.py`
- Modify: `src/gemini_trading/strategy/sealed_verification.py`
- Modify: `tests/unit/strategy/test_pre_final.py`
- Modify: `tests/unit/strategy/test_sealed_manifest_identity.py`
- Modify: `tests/integration/test_sealed_candidate_two_phase.py`

**Interfaces:**
- Consumes: handoff v4.
- Produces: `dataset-handoff-reference-v4`, pre-final identity, study manifest, replay, and independent verification bound to plural row identity and v4 inventory root.

- [ ] Add RED tests asserting pre-final reference and manifest contain `excluded_provider_rows` and no legacy scalar field.

- [ ] Add study-manifest tests requiring `candle-dataset-v4`, `(20,20,21)`, exact ordered row pairs and boundaries; reject legacy v3 sealed manifests and reordered/tampered identities.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/strategy/test_pre_final.py tests/unit/strategy/test_sealed_manifest_identity.py tests/integration/test_sealed_candidate_two_phase.py -q
```

- [ ] Update `_handoff_reference`, pre-final identity payload, evaluator emission, replay parser, and sealed-chain comparison. Do not modify `final_access.py`; its identity already binds the pre-final ID and therefore inherits the v4 chain.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/unit/strategy/test_pre_final.py tests/unit/strategy/test_sealed_manifest_identity.py tests/integration/test_sealed_candidate_two_phase.py -q
uv run ruff check src/gemini_trading/strategy/pre_final.py src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/sealed_evaluator.py src/gemini_trading/strategy/sealed_verification.py
git add src/gemini_trading/strategy/pre_final.py src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/sealed_evaluator.py src/gemini_trading/strategy/sealed_verification.py tests/unit/strategy/test_pre_final.py tests/unit/strategy/test_sealed_manifest_identity.py tests/integration/test_sealed_candidate_two_phase.py
git commit -m "feat: bind sealed study evidence to handoff v4"
```

---

### Task 11: Centralize fixed sealed identity and upgrade both workflows

**Files:**
- Create: `src/gemini_trading/strategy/sealed_dataset_identity.py`
- Create: `tests/unit/strategy/test_sealed_dataset_identity.py`
- Modify: `.github/workflows/sealed-btcusdt-dataset.yml`
- Modify: `.github/workflows/sealed-btcusdt-study.yml`
- Modify: `tests/acceptance/test_sealed_historical_validation_workflows.py`

**Interfaces:**
- Produces immutable constants and validator:

```python
EXPECTED_COUNTS = (20, 20, 21)
EXPECTED_BOUNDARIES = (18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)
EXPECTED_CANDLE_COUNT = 18_582

def assert_fixed_sealed_dataset_identity(handoff: DatasetHandoffManifest) -> None: ...
```

- [ ] Add RED unit tests for exact pass and every single-field mismatch.

- [ ] Add RED acceptance tests requiring workflows to import and call the validator, require v4, retain narrow dispatch inputs, least privilege, exact-main checks, no operator manifest override, no Binance network use in Stage 2, one-time final-access barriers, artifact retention, and clean-tree checks.

- [ ] Confirm RED:

```bash
uv run pytest tests/unit/strategy/test_sealed_dataset_identity.py tests/acceptance/test_sealed_historical_validation_workflows.py -q
```

- [ ] Implement the identity module using the exact pairs and values in this plan.

- [ ] Replace duplicated one-row workflow assertions with `assert_fixed_sealed_dataset_identity(handoff)` in Stage 1 and Stage 2.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/unit/strategy/test_sealed_dataset_identity.py tests/acceptance/test_sealed_historical_validation_workflows.py -q
uv run ruff check src/gemini_trading/strategy/sealed_dataset_identity.py tests/unit/strategy/test_sealed_dataset_identity.py tests/acceptance/test_sealed_historical_validation_workflows.py
git add src/gemini_trading/strategy/sealed_dataset_identity.py tests/unit/strategy/test_sealed_dataset_identity.py .github/workflows/sealed-btcusdt-dataset.yml .github/workflows/sealed-btcusdt-study.yml tests/acceptance/test_sealed_historical_validation_workflows.py
git commit -m "feat: enforce exact sealed dataset v4 workflow identity"
```

---

### Task 12: Update permanent documentation without claiming a real result

**Files:**
- Modify: `README.md`
- Modify: `docs/operations/sealed-btcusdt-historical-validation.md`
- Modify: `reports/verification/sealed-btcusdt-historical-validation-progress.md`
- Modify: `tests/acceptance/test_sealed_historical_validation_documentation.py`

**Interfaces:**
- Produces accurate permanent status and post-merge Stage 1 protocol.

- [ ] Add RED documentation assertions requiring:

```text
exchange-closure-manifest-v3
candle-dataset-v4
sealed-dataset-handoff-v4
20 closures
20 exclusions
21 continuous segments
36 unavailable canonical 4h slots
18,582 canonical candles
```

Also require: raw rows immutable; no synthetic candle; v3 artifacts invalid; Stage 1 must be newly run from exact verified merged main; Stage 2 blocked pending owner artifact approval; profitability and capital readiness unestablished.

- [ ] Confirm RED:

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_documentation.py -q
```

- [ ] Update README, operations guide, and progress report. The operations guide must list the exact Stage 1 evidence fields: source commit; workflow run/attempt; artifact name/ID; retrieval run ID; v4 dataset ID; supporting paths/hashes; counts; ordered closure-row identities; boundaries; candle count and first/last opens; inventory root; replay; independent verification.

- [ ] Verify GREEN and commit:

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_documentation.py -q
git add README.md docs/operations/sealed-btcusdt-historical-validation.md reports/verification/sealed-btcusdt-historical-validation-progress.md tests/acceptance/test_sealed_historical_validation_documentation.py
git commit -m "docs: document multi-closure sealed validation v4"
```

---

### Task 13: Run complete local verification and cumulative security review

**Files:** Modify only files needed to correct demonstrated failures. Do not add generated raw data, canonical data, workflow artifacts, or study outputs.

- [ ] Run focused cumulative tests:

```bash
uv run pytest tests/unit/data/test_exchange_closures.py tests/unit/data/test_candle_exclusions.py tests/unit/data/test_candle_segments.py tests/unit/data/datasets/test_canonical_writer.py tests/unit/data/ingestion/test_service.py tests/integration/test_market_data_exchange_closure_v3.py tests/integration/test_storage_adapter_equivalence.py tests/integration/test_research_dataset_reader.py tests/integration/test_sealed_historical_validation.py tests/unit/strategy/test_handoff.py tests/unit/strategy/test_pre_final.py tests/unit/strategy/test_sealed_manifest_identity.py tests/unit/strategy/test_sealed_dataset_identity.py tests/integration/test_sealed_candidate_two_phase.py tests/acceptance/test_sealed_historical_validation_workflows.py tests/acceptance/test_sealed_historical_validation_documentation.py -q
```

- [ ] Run all repository gates:

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
python scripts/validate_tracked_files.py
uv run detect-secrets scan --all-files --baseline .secrets.baseline
git diff --check
```

- [ ] Run the repository-standard pinned Gitleaks command and require no verified finding.

- [ ] Review fail-closed properties: no operator override; no generated evidence tracked; no revised v3 input; no scalar v4 row field; exact ordering/counts; no strategy/config/final-access change; no Stage 2 network access; failure grants no approval.

- [ ] Confirm clean unchanged head:

```bash
HEAD_BEFORE="$(git rev-parse HEAD)"
test -z "$(git status --porcelain)"
test "$(git rev-parse HEAD)" = "$HEAD_BEFORE"
```

- [ ] If a demonstrated defect required correction, commit only reviewed planned paths and rerun all checks. Do not create an empty verification commit.

---

### Task 14: Open the protected implementation PR and require exact-head CI

**Files:** GitHub metadata only.

- [ ] Push the implementation branch:

```bash
git push -u origin research/verified-multi-closure-partial-candle-manifest
```

- [ ] Create `/tmp/multiclosure-pr-body.md` containing Issue #22 authorization, PR #41 design, exact migrations/invariants, verification commands, unchanged safety boundary, and explicit Stage 1/Stage 2 blocking.

- [ ] Open draft PR:

```bash
gh pr create --base main --head research/verified-multi-closure-partial-candle-manifest --draft --title "feat: implement verified multi-closure dataset v4" --body-file /tmp/multiclosure-pr-body.md
```

- [ ] Watch exact-head checks:

```bash
PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr checks "$PR_NUMBER" --watch
```

Expected: required `quality` and `gitleaks` checks pass on the recorded head.

- [ ] Resolve every review thread, reject relaxed validation/version reinterpretation/ordering ambiguity/authority expansion, then mark ready:

```bash
gh pr ready "$PR_NUMBER"
```

- [ ] Record PR number, exact reviewed SHA, local gates, CI run IDs, and `RESEARCH_ONLY` in Issue #22. Do not authorize Stage 1 from the branch.

---

### Task 15: Protected merge, exact-main verification, and completely new Stage 1

**Files:** GitHub metadata and repository-standard temporary exact-main verification mechanism.

- [ ] Squash-merge after all checks and reviews:

```bash
PR_NUMBER="$(gh pr view --json number --jq .number)"
gh pr merge "$PR_NUMBER" --squash --delete-branch
```

- [ ] Resolve exact merged main:

```bash
git fetch origin
git switch main
git reset --hard origin/main
MERGED_SHA="$(git rev-parse HEAD)"
test -z "$(git status --porcelain)"
printf '%s\n' "$MERGED_SHA"
```

- [ ] Run authoritative exact-main frozen sync, Ruff format/lint, strict Pyright, full pytest, build, pip-audit, tracked-file policy, detect-secrets, Gitleaks, clean tree, and unchanged exact HEAD.

- [ ] Record exact merged SHA and verification run IDs in Issue #22. This authorizes only a new Stage 1 run, not dataset approval or Stage 2.

- [ ] Dispatch a completely new `Sealed BTCUSDT Dataset` run from `main`. Do not rerun or reuse a v3 failure/artifact.

- [ ] Download and independently verify v4 evidence: 20/20/21; 36 unavailable slots; 18,582 candles; exact ordered closure-row pairs; exact boundaries; fixed first/last opens; byte-identical replay; independent verification; sorted inventory and root hash.

- [ ] Keep Stage 2 blocked until the repository owner posts the exact marker after successful artifact verification:

```text
<!-- sealed-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

The approval comment must also contain artifact name/ID, retrieval run ID, inventory root, counts, boundaries, first/last opens, replay outcome, verification outcome, and `RESEARCH_ONLY`.

---

## Plan Self-Review

- **Spec coverage:** Tasks 2-12 cover every architecture, failure, test, workflow, rollout, and scope-exclusion requirement; Tasks 13-15 cover complete verification and protected rollout.
- **Placeholder scan:** No `TBD`, `TODO`, deferred implementation, invented path, or unspecified test obligation remains. Runtime identifiers are captured by exact commands.
- **Type consistency:** v4 uses `ExcludedProviderRow(closure_id, provider_row_sha256)` through handoff, CLI, pre-final, replay, evaluator, workflows, and verification.
- **Version consistency:** closure v3, dataset v4, handoff v4, and handoff-reference v4 are new identities; v3 semantics remain unchanged.
- **Scope consistency:** one implementation stream produces one internally consistent sealed-data contract.
- **Safety consistency:** no task changes strategy parameters, final-test policy, provider boundary, or execution authority.
