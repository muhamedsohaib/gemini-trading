# Verified Exchange-Closure Gap Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the fixed Binance Spot BTCUSDT 4-hour research window while accepting only the approved February 2018 exchange closure, binding that closure and deterministic candle segments into a version-2 dataset and preventing every research dependency from crossing a segment boundary.

**Architecture:** Keep generic market-data ingestion strictly continuous by default. Add a sealed-only, source-controlled closure contract that exact-matches observed gaps, derives immutable continuous segments, and becomes part of raw evidence, canonical dataset identity, Stage 1 handoff identity, replay, verification, features, labels, splits, and strategy-study evidence. No candle is inserted, deleted, reordered, forward-filled, interpolated, or altered.

**Tech Stack:** Python 3.12, frozen `uv` environment, dataclasses, canonical JSON, SHA-256 content identities, pytest, Ruff, Pyright, GitHub Actions.

## Global Constraints

- Safety level remains `RESEARCH_ONLY`; execution authority remains none.
- Provider remains public Binance Spot market data only.
- Instrument remains `BTCUSDT`; timeframe remains `4h`.
- Window remains `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
- Completed authentic provider candles only; never synthesize or alter a candle.
- Approved missing interval is exactly `[2018-02-08T04:00:00Z, 2018-02-09T08:00:00Z)` with seven missing 4-hour opens.
- Every undeclared, shifted, partial, expanded, contracted, overlapping, touching, unused, or misaligned declaration fails closed.
- Dataset schema becomes `candle-dataset-v2`; Stage 2 rejects v1 artifacts.
- Features, labels, strategy schedules, simulator state, folds, and final-test access must not cross a segment boundary.
- A noncash or active-order simulator state at a segment boundary fails closed; do not create a synthetic liquidation or transfer a position across unavailable data.
- A closure intersecting the final 18-month test requires a new design gate and must be rejected by this implementation.
- No model, feature definition, threshold, cost, comparator, split date, or final-test rule changes.
- Stage 2 remains prohibited until a new Stage 1 artifact is independently verified and approved in Issue #22.

---

## File Structure

### New focused files

- `config/market-data/sealed-btcusdt-4h-exchange-closures.json` — the only approved operator-authored closure declaration.
- `src/gemini_trading/data/exchange_closures.py` — exact schema, canonical parsing/serialization, scope validation, and approved-manifest loading.
- `src/gemini_trading/data/segments.py` — observed-gap matching, deterministic segment derivation, segment lookup, and canonical segment serialization.
- `tests/unit/data/test_exchange_closures.py` — closure schema and exact-gap contract tests.
- `tests/unit/data/test_candle_segments.py` — deterministic segment derivation and tamper tests.
- `tests/fixtures/market_data/gapped_btcusdt_4h.py` — small authentic-shaped synthetic candles around one declared closure.

### Existing files to modify

- `src/gemini_trading/domain/dataset.py` — v2 manifest fields and raw-run closure hash.
- `src/gemini_trading/data/validation/candles.py` — strict default plus explicit closure-aware validation entry point.
- `src/gemini_trading/data/datasets/canonical_writer.py` — v2 identity payload and supporting manifests.
- `src/gemini_trading/data/storage/base.py` — closure/segment evidence read-write protocols.
- `src/gemini_trading/data/storage/local_immutable.py` — immutable local paths and canonical bytes.
- `src/gemini_trading/data/ingestion/service.py` — sealed ingestion with exact closure matching.
- `src/gemini_trading/data/ingestion/replay.py` — provider-free v2 reconstruction.
- `src/gemini_trading/data/verification/service.py` — independent closure, segment, and v2 identity recomputation.
- `src/gemini_trading/research/dataset_reader.py` — strict v2 loading into `VerifiedDataset`.
- `src/gemini_trading/cli/historical_validation.py` — fixed-path sealed dataset commands.
- `src/gemini_trading/cli/main.py` — parser registration for fixed sealed commands.
- `src/gemini_trading/strategy/handoff.py` — Stage 1-to-Stage 2 schema v2.
- `src/gemini_trading/strategy/features.py` — segment-local feature computation.
- `src/gemini_trading/strategy/labels.py` — segment-safe label outcomes.
- `src/gemini_trading/strategy/splits.py` — segment boundaries as protected split boundaries.
- `src/gemini_trading/strategy/study.py` — segment-boundary identity in split payloads.
- `src/gemini_trading/strategy/study_plans.py` — segment-safe schedules and case plans.
- `src/gemini_trading/research/engine.py` — fail-closed state boundary guard.
- `src/gemini_trading/strategy/evaluator.py` — pass segment evidence through complete local studies.
- `src/gemini_trading/strategy/sealed_evaluator.py` — bind segment identity into pre-final/final evidence.
- `src/gemini_trading/strategy/replay.py` and `src/gemini_trading/strategy/sealed_verification.py` — reproduce and verify segment-safe study evidence.
- `.github/workflows/sealed-btcusdt-dataset.yml` — invoke only fixed sealed dataset commands.
- `.github/workflows/sealed-btcusdt-study.yml` — require v2 handoff fields without changing final-access policy.
- `docs/operations/sealed-btcusdt-historical-validation.md` and `README.md` — operator boundaries and new artifact inventory.

---

### Task 1: Add the fixed exchange-closure contract

**Files:**
- Create: `config/market-data/sealed-btcusdt-4h-exchange-closures.json`
- Create: `src/gemini_trading/data/exchange_closures.py`
- Create: `tests/unit/data/test_exchange_closures.py`

**Interfaces:**
- Produces: `ExchangeClosure`, `ExchangeClosureManifest`, `load_exchange_closure_manifest(raw: bytes) -> ExchangeClosureManifest`, `serialize_exchange_closure_manifest(manifest: ExchangeClosureManifest) -> bytes`, and `load_fixed_btcusdt_closure_manifest(project_root: Path) -> tuple[ExchangeClosureManifest, bytes]`.
- The fixed loader must resolve exactly `config/market-data/sealed-btcusdt-4h-exchange-closures.json`; it accepts no caller-provided path.

- [ ] **Step 1: Write the canonical JSON fixture**

```json
{"schema_version":"exchange-closure-manifest-v1","provider":"binance_spot","instrument":{"symbol":"BTCUSDT","base_asset":"BTC","quote_asset":"USDT"},"timeframe":"4h","start_time":"2018-01-01T00:00:00Z","end_time":"2026-07-01T00:00:00Z","closures":[{"closure_id":"binance-spot-system-upgrade-2018-02-08","missing_start":"2018-02-08T04:00:00Z","resumed_open":"2018-02-09T08:00:00Z","missing_candle_count":7,"reason_code":"exchange_system_upgrade","governance_reference":"github-issue-22"}]}
```

- [ ] **Step 2: Write failing parser and canonical-encoding tests**

```python
def test_fixed_manifest_is_canonical_and_exact() -> None:
    manifest, raw = load_fixed_btcusdt_closure_manifest(PROJECT_ROOT)
    assert serialize_exchange_closure_manifest(manifest) == raw
    assert manifest.closures[0].missing_candle_count == 7
    assert manifest.closures[0].missing_start.isoformat() == "2018-02-08T04:00:00+00:00"
    assert manifest.closures[0].resumed_open.isoformat() == "2018-02-09T08:00:00+00:00"
```

Add separate tests rejecting extra fields, alternate whitespace/encoding, duplicate IDs, unsorted entries, overlap, touching entries, non-UTC timestamps, timeframe misalignment, wrong count, wrong market identity, and a closure outside the request window.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -v
```

Expected: import failure because `gemini_trading.data.exchange_closures` does not exist.

- [ ] **Step 4: Implement immutable domain contracts and canonical serialization**

Use frozen slot dataclasses. Recompute the count instead of trusting JSON:

```python
expected_count = (closure.resumed_open - closure.missing_start) // manifest.timeframe.duration
if expected_count != closure.missing_candle_count:
    raise CandleValidationError("exchange closure missing-candle count mismatch")
```

Require exact field sets and require `serialize_exchange_closure_manifest(parsed) == raw`.

- [ ] **Step 5: Run tests and static checks**

```bash
uv run pytest tests/unit/data/test_exchange_closures.py -v
uv run ruff format --check src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
uv run ruff check src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
uv run pyright src/gemini_trading/data/exchange_closures.py
```

- [ ] **Step 6: Commit**

```bash
git add config/market-data/sealed-btcusdt-4h-exchange-closures.json src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
git commit -m "feat: add sealed exchange-closure contract"
```

---

### Task 2: Exact-match gaps and derive deterministic segments

**Files:**
- Create: `src/gemini_trading/data/segments.py`
- Create: `tests/unit/data/test_candle_segments.py`
- Create: `tests/fixtures/market_data/gapped_btcusdt_4h.py`
- Modify: `src/gemini_trading/data/validation/candles.py`
- Modify: existing strict validation tests under `tests/unit/data/`

**Interfaces:**
- Preserve: `validate_candle_sequence(candles: Sequence[Candle], request: RetrievalRequest) -> None` with strict no-gap semantics.
- Produce: `validate_and_segment_candle_sequence(candles: Sequence[Candle], request: RetrievalRequest, closure_manifest: ExchangeClosureManifest) -> CandleSegmentManifest`.
- Produce: `CandleSegment`, `CandleSegmentManifest`, `serialize_candle_segment_manifest(...) -> bytes`, `load_candle_segment_manifest(...) -> CandleSegmentManifest`, and `segment_number_for_index(manifest, index) -> int`.

- [ ] **Step 1: Write the synthetic gapped fixture**

Create candles at `2018-02-08T00:00:00Z`, then resume at `2018-02-09T08:00:00Z`, with at least three candles on each side. Preserve authentic OHLCV geometry and global candle indices.

- [ ] **Step 2: Write failing exactness tests**

```python
def test_declared_exchange_closure_produces_two_segments() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, CLOSURE_MANIFEST)
    assert [(item.start_index, item.end_exclusive) for item in segments.segments] == [(0, 3), (3, 6)]
    assert segments.segments[1].preceding_closure_id == "binance-spot-system-upgrade-2018-02-08"
```

Add tests for strict validation still raising `CandleGapError`, undeclared gaps, shifted actual resumption, partial gaps, extra observed gaps, unused declarations, wrong count, touching/overlapping declarations, and byte-tampered segment manifests.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_candle_segments.py tests/unit/data/test_candle_validation.py -v
```

- [ ] **Step 4: Implement exact matching**

For each adjacent pair:

```python
expected = previous.open_time + request.timeframe.duration
if current.open_time != expected:
    observed = (expected, current.open_time)
    closure = closures_by_bounds.get(observed)
    if closure is None:
        raise CandleGapError(
            "candle sequence contains an undeclared timeframe gap: "
            f"previous_open_time={previous.open_time.isoformat()} "
            f"expected_open_time={expected.isoformat()} "
            f"actual_open_time={current.open_time.isoformat()}"
        )
    used_closure_ids.add(closure.closure_id)
```

After scanning, require `used_closure_ids == declared_closure_ids`. Derive maximal continuous index windows and canonical segment bytes.

- [ ] **Step 5: Run focused tests and static checks**

```bash
uv run pytest tests/unit/data/test_candle_segments.py tests/unit/data/test_candle_validation.py -v
uv run ruff format --check src/gemini_trading/data/segments.py src/gemini_trading/data/validation/candles.py
uv run ruff check src/gemini_trading/data/segments.py src/gemini_trading/data/validation/candles.py
uv run pyright src/gemini_trading/data/segments.py src/gemini_trading/data/validation/candles.py
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/data/segments.py src/gemini_trading/data/validation/candles.py tests/unit/data/test_candle_segments.py tests/fixtures/market_data/gapped_btcusdt_4h.py tests/unit/data/test_candle_validation.py
git commit -m "feat: validate declared gaps and derive candle segments"
```

---

### Task 3: Introduce dataset identity version 2

**Files:**
- Modify: `src/gemini_trading/domain/dataset.py`
- Modify: `src/gemini_trading/data/datasets/canonical_writer.py`
- Modify: `tests/unit/data/test_canonical_writer.py`
- Modify: `tests/unit/domain/test_dataset.py`

**Interfaces:**
- Extend `RetrievalManifest` with `closure_manifest_sha256: str | None` and require it only for `retrieval-manifest-v2`.
- Extend `DatasetManifest` with `closure_manifest_sha256`, `segment_manifest_sha256`, `closure_count`, and `segment_count`.
- Produce: `dataset_id_v2(*, provider: str, instrument: Instrument, timeframe: Timeframe, start_time: datetime, end_time: datetime, canonical_bytes: bytes, closure_manifest_bytes: bytes, segment_manifest_bytes: bytes) -> str`.
- Change sealed construction to schema `candle-dataset-v2`; retain v1 parsing only where existing generic tests require it, but do not permit v1 in sealed handoff paths.

- [ ] **Step 1: Write failing v2 identity tests**

```python
def test_v2_dataset_identity_binds_all_three_byte_streams() -> None:
    original = dataset_id_v2(...)
    assert dataset_id_v2(..., canonical_bytes=canonical_bytes + b"\n") != original
    assert dataset_id_v2(..., closure_manifest_bytes=closure_bytes + b" ") != original
    assert dataset_id_v2(..., segment_manifest_bytes=segment_bytes + b" ") != original
```

Add deterministic ordering, scope-field sensitivity, v1/v2 distinction, and invalid hash/count tests.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_canonical_writer.py tests/unit/domain/test_dataset.py -v
```

- [ ] **Step 3: Implement the canonical v2 identity payload**

```python
identity_payload = {
    "schema_version": "candle-dataset-v2",
    "provider": provider,
    "instrument": _instrument_payload(instrument),
    "timeframe": timeframe.value,
    "start_time": _format_datetime(start_time),
    "end_time": _format_datetime(end_time),
    "canonical_sha256": sha256(canonical_bytes).hexdigest(),
    "closure_manifest_sha256": sha256(closure_manifest_bytes).hexdigest(),
    "segment_manifest_sha256": sha256(segment_manifest_bytes).hexdigest(),
}
return sha256(canonical_json_bytes(identity_payload)).hexdigest()
```

Use the existing project canonical JSON serializer; do not use timestamp metadata in identity.

- [ ] **Step 4: Update manifest serialization and parsing contracts**

Require exact v2 field sets and stable order. Add closure and segment counts to persisted dataset manifest bytes.

- [ ] **Step 5: Run focused tests and static checks**

```bash
uv run pytest tests/unit/data/test_canonical_writer.py tests/unit/domain/test_dataset.py -v
uv run ruff format --check src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py
uv run ruff check src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py
uv run pyright src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/domain/dataset.py src/gemini_trading/data/datasets/canonical_writer.py tests/unit/data/test_canonical_writer.py tests/unit/domain/test_dataset.py
git commit -m "feat: bind closure segments into dataset v2 identity"
```

---

### Task 4: Persist closure and segment evidence immutably

**Files:**
- Modify: `src/gemini_trading/data/storage/base.py`
- Modify: `src/gemini_trading/data/storage/local_immutable.py`
- Modify: `tests/unit/data/test_local_immutable_store.py`

**Interfaces:**
- Add raw methods: `write_run_closure_manifest(run_id: str, raw: bytes) -> Path` and `read_run_closure_manifest_bytes(run_id: str) -> bytes`.
- Add canonical methods: `write_dataset_supporting_manifests(dataset_id: str, closure_raw: bytes, segment_raw: bytes) -> tuple[Path, Path]` and `read_dataset_supporting_manifests(dataset_id: str) -> tuple[bytes, bytes]`.
- Fixed paths:
  - `data/raw/binance_spot/<run_id>/exchange-closures.json`
  - `data/canonical/<dataset_id>/exchange-closures.json`
  - `data/canonical/<dataset_id>/candle-segments.json`

- [ ] **Step 1: Write failing immutable-store tests**

Test first write, byte-identical repeat, conflicting overwrite rejection, path traversal rejection, missing-file failure, and read-back equality.

- [ ] **Step 2: Run tests and confirm RED**

```bash
uv run pytest tests/unit/data/test_local_immutable_store.py -v
```

- [ ] **Step 3: Implement protocol and local-store methods**

All writes must use the existing `write_immutable` helper. Do not add mutable update behavior.

- [ ] **Step 4: Run tests and static checks**

```bash
uv run pytest tests/unit/data/test_local_immutable_store.py -v
uv run ruff format --check src/gemini_trading/data/storage/base.py src/gemini_trading/data/storage/local_immutable.py
uv run ruff check src/gemini_trading/data/storage/base.py src/gemini_trading/data/storage/local_immutable.py
uv run pyright src/gemini_trading/data/storage/base.py src/gemini_trading/data/storage/local_immutable.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/data/storage/base.py src/gemini_trading/data/storage/local_immutable.py tests/unit/data/test_local_immutable_store.py
git commit -m "feat: persist closure and segment evidence"
```

---

### Task 5: Integrate sealed ingestion, replay, and independent verification

**Files:**
- Modify: `src/gemini_trading/data/ingestion/service.py`
- Modify: `src/gemini_trading/data/ingestion/replay.py`
- Modify: `src/gemini_trading/data/verification/service.py`
- Modify: `tests/acceptance/test_market_data_ingestion.py`
- Modify: `tests/integration/test_market_data_replay.py`
- Modify: `tests/integration/test_market_data_verification.py`

**Interfaces:**
- Extend `IngestionService.__init__(..., closure_manifest: ExchangeClosureManifest | None = None, closure_manifest_bytes: bytes | None = None)`; require both or neither.
- Strict generic ingestion remains unchanged when neither is supplied.
- Extend `IngestionResult.paths` to include `run_closure_manifest`, `canonical_closure_manifest`, and `segment_manifest` for sealed v2 runs.
- Replay reads the run-bound closure bytes, revalidates exact gaps, rederives segments, and reproduces the same v2 dataset ID.
- Verification checks include `declared_gap_exactness` and `segment_continuity` and remove `parsed_continuity` for v2.

- [ ] **Step 1: Write failing sealed-ingestion test**

```python
def test_ingestion_accepts_only_exact_declared_gap_and_writes_v2_evidence(tmp_path: Path) -> None:
    result = IngestionService(
        provider=provider_with_known_gap,
        raw_store=store,
        canonical_store=store,
        closure_manifest=manifest,
        closure_manifest_bytes=manifest_bytes,
    ).ingest(request)
    assert dict(result.paths)["segment_manifest"].is_file()
    assert load_verified_dataset(store, result.dataset_id).manifest.schema_version == "candle-dataset-v2"
```

Add strict no-manifest rejection, unused declaration, additional provider gap, replay byte equality, closure hash tamper, segment hash tamper, and independent verification tests.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/acceptance/test_market_data_ingestion.py tests/integration/test_market_data_replay.py tests/integration/test_market_data_verification.py -v
```

- [ ] **Step 3: Implement v2 ingestion**

Order of operations:

1. persist raw pages;
2. persist exact closure bytes under the run;
3. exact-validate and derive segments;
4. serialize candles and segments;
5. build v2 manifest and dataset ID;
6. persist canonical candles, dataset manifest, closure manifest, segment manifest, and provenance;
7. bind the closure hash into retrieval manifest v2.

Any failure before the completed retrieval manifest must persist a failed terminal manifest and publish no canonical v2 dataset.

- [ ] **Step 4: Implement provider-free replay**

Replay must use only stored raw pages, stored retrieval manifest, and stored run closure bytes. It must not load the source-tree config file and must not construct a provider.

- [ ] **Step 5: Implement independent verification**

Verification independently parses the canonical closure and segment files, compares the run closure hash, rederives segments from raw reconstruction, recomputes all v2 bytes and identity, and rejects any mismatch.

- [ ] **Step 6: Run focused tests and static checks**

```bash
uv run pytest tests/acceptance/test_market_data_ingestion.py tests/integration/test_market_data_replay.py tests/integration/test_market_data_verification.py -v
uv run ruff format --check src/gemini_trading/data/ingestion src/gemini_trading/data/verification
uv run ruff check src/gemini_trading/data/ingestion src/gemini_trading/data/verification
uv run pyright src/gemini_trading/data/ingestion src/gemini_trading/data/verification
```

- [ ] **Step 7: Commit**

```bash
git add src/gemini_trading/data/ingestion/service.py src/gemini_trading/data/ingestion/replay.py src/gemini_trading/data/verification/service.py tests/acceptance/test_market_data_ingestion.py tests/integration/test_market_data_replay.py tests/integration/test_market_data_verification.py
git commit -m "feat: replay and verify declared exchange closures"
```

---

### Task 6: Load verified v2 datasets and seal the Stage 1 handoff

**Files:**
- Modify: `src/gemini_trading/research/dataset_reader.py`
- Modify: `src/gemini_trading/strategy/handoff.py`
- Modify: `src/gemini_trading/cli/historical_validation.py`
- Modify: `tests/unit/strategy/test_handoff.py`
- Modify: `tests/unit/cli/test_historical_validation.py`

**Interfaces:**
- Extend `VerifiedDataset` with `closure_manifest: ExchangeClosureManifest`, `segment_manifest: CandleSegmentManifest`, `closure_manifest_bytes: bytes`, and `segment_manifest_bytes: bytes`.
- Bump handoff schema to `sealed-dataset-handoff-v2`.
- Add handoff fields: `dataset_schema_version`, `closure_manifest_path`, `closure_manifest_sha256`, `segment_manifest_path`, `segment_manifest_sha256`, `closure_count`, `segment_count`, and `closure_ids`.
- `verify_dataset_handoff` must reject v1, missing files, unexpected fields, hash mismatch, count mismatch, closure-ID mismatch, and path traversal.

- [ ] **Step 1: Write failing v2 dataset-loader tests**

Verify exact field sets, canonical bytes, v2 identity recomputation, segment index coverage, and rejection of v1 under sealed loading.

- [ ] **Step 2: Write failing handoff tests**

```python
def test_sealed_handoff_requires_exact_v2_closure_and_segment_identity(tmp_path: Path) -> None:
    manifest = build_v2_handoff(tmp_path)
    verify_dataset_handoff(manifest, tmp_path)
    tampered = replace(manifest, closure_count=manifest.closure_count + 1)
    with pytest.raises(DatasetHandoffError, match="closure count"):
        verify_dataset_handoff(tampered, tmp_path)
```

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/strategy/test_handoff.py tests/unit/cli/test_historical_validation.py tests/unit/research/test_dataset_reader.py -v
```

- [ ] **Step 4: Implement strict v2 loading and handoff serialization**

The loader must obtain all four canonical files from `LocalImmutableStore`, verify bytes and hashes, rerun exact gap matching, and return a fully populated `VerifiedDataset`.

- [ ] **Step 5: Update `_strategy_handoff`**

Include the closure and segment paths in the artifact inventory and construct only `sealed-dataset-handoff-v2`.

- [ ] **Step 6: Run tests and static checks**

```bash
uv run pytest tests/unit/strategy/test_handoff.py tests/unit/cli/test_historical_validation.py tests/unit/research/test_dataset_reader.py -v
uv run ruff format --check src/gemini_trading/research/dataset_reader.py src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py
uv run ruff check src/gemini_trading/research/dataset_reader.py src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py
uv run pyright src/gemini_trading/research/dataset_reader.py src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py
```

- [ ] **Step 7: Commit**

```bash
git add src/gemini_trading/research/dataset_reader.py src/gemini_trading/strategy/handoff.py src/gemini_trading/cli/historical_validation.py tests/unit/strategy/test_handoff.py tests/unit/cli/test_historical_validation.py tests/unit/research/test_dataset_reader.py
git commit -m "feat: seal dataset v2 handoff identity"
```

---

### Task 7: Add fixed sealed dataset CLI commands and workflow wiring

**Files:**
- Modify: `src/gemini_trading/cli/historical_validation.py`
- Modify: `src/gemini_trading/cli/main.py`
- Modify: `.github/workflows/sealed-btcusdt-dataset.yml`
- Modify: `tests/unit/cli/test_historical_validation.py`
- Modify: `tests/acceptance/test_sealed_historical_validation_workflows.py`

**Interfaces:**
- Add fixed commands: `dataset-ingest`, `dataset-replay`, and `dataset-verify` under historical validation.
- `dataset-ingest` accepts `--project-root` and `--output-root` only for location; market identity, window, provider, timeframe, and closure-manifest path are internal constants.
- `dataset-replay` accepts only `--run-id` and `--output-root`.
- `dataset-verify` accepts only `--dataset-id`, `--run-id`, and `--output-root`.
- No workflow-dispatch input or environment variable may select a closure manifest.

- [ ] **Step 1: Write failing parser and fixed-path tests**

```python
def test_sealed_dataset_ingest_rejects_arbitrary_closure_path() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["historical-validation", "dataset-ingest", "--closure-manifest", "other.json"])
```

Also assert the workflow contains the fixed command and repository path but no `inputs.closure_manifest`, `CLOSURE_MANIFEST`, curl, or remote download.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/cli/test_historical_validation.py tests/acceptance/test_sealed_historical_validation_workflows.py -v
```

- [ ] **Step 3: Implement fixed command handlers**

`dataset-ingest` loads the fixed manifest with `load_fixed_btcusdt_closure_manifest(project_root)` and constructs `IngestionService` with it. Return only safe IDs, counts, hashes, and artifact-relative paths.

- [ ] **Step 4: Replace generic commands in Stage 1 workflow**

Use:

```yaml
uv run gemini-trading historical-validation dataset-ingest \
  --project-root "${GITHUB_WORKSPACE}" \
  --output-root "${OUTPUT_ROOT}"
```

Follow with fixed `dataset-replay`, fixed `dataset-verify`, and existing `strategy-handoff` commands.

- [ ] **Step 5: Run tests and YAML validation**

```bash
uv run pytest tests/unit/cli/test_historical_validation.py tests/acceptance/test_sealed_historical_validation_workflows.py -v
pre-commit run check-yaml --files .github/workflows/sealed-btcusdt-dataset.yml
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/cli/historical_validation.py src/gemini_trading/cli/main.py .github/workflows/sealed-btcusdt-dataset.yml tests/unit/cli/test_historical_validation.py tests/acceptance/test_sealed_historical_validation_workflows.py
git commit -m "feat: wire fixed sealed dataset commands"
```

---

### Task 8: Make features and labels segment-local

**Files:**
- Modify: `src/gemini_trading/strategy/features.py`
- Modify: `src/gemini_trading/strategy/labels.py`
- Modify: `tests/property/strategy/test_strategy_feature_point_in_time.py`
- Modify: `tests/unit/strategy/test_features.py`
- Modify: `tests/unit/strategy/test_labels.py`

**Interfaces:**
- Change `FeatureRegistry.compute(candles: tuple[Candle, ...], *, segments: CandleSegmentManifest | None = None) -> FeatureMatrix`.
- Change `LabelPolicy.build(candles: tuple[Candle, ...], *, eligible_indices: tuple[int, ...], segments: CandleSegmentManifest | None = None) -> LabelVector`.
- `None` retains existing single-segment behavior.

- [ ] **Step 1: Write failing segment-local feature tests**

```python
def test_feature_warmup_restarts_after_closure() -> None:
    matrix = FeatureRegistry.locked_v0_1().compute(candles, segments=segments)
    second_start = segments.segments[1].start_index
    assert all(row.candle_index >= second_start + 42 for row in matrix.rows if row.candle_index >= second_start)
```

Prove that changing a candle in segment 1 cannot change any feature row in segment 2.

- [ ] **Step 2: Write failing label-boundary tests**

Ensure decisions whose entry or exit crosses a segment boundary are omitted and all retained observations have decision, entry, and exit indexes in one segment.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/strategy/test_features.py tests/unit/strategy/test_labels.py tests/property/strategy/test_strategy_feature_point_in_time.py -v
```

- [ ] **Step 4: Implement segment-local feature loops**

Compute each segment independently using its local tuple, then map local row indexes back to global indexes. Do not slice across segment boundaries.

- [ ] **Step 5: Implement segment-safe labels**

Before constructing an observation:

```python
if segment_number_for_index(segments, decision_index) != segment_number_for_index(segments, exit_index):
    continue
```

Also require the entry index to share the same segment.

- [ ] **Step 6: Run tests and static checks**

```bash
uv run pytest tests/unit/strategy/test_features.py tests/unit/strategy/test_labels.py tests/property/strategy/test_strategy_feature_point_in_time.py -v
uv run ruff format --check src/gemini_trading/strategy/features.py src/gemini_trading/strategy/labels.py
uv run ruff check src/gemini_trading/strategy/features.py src/gemini_trading/strategy/labels.py
uv run pyright src/gemini_trading/strategy/features.py src/gemini_trading/strategy/labels.py
```

- [ ] **Step 7: Commit**

```bash
git add src/gemini_trading/strategy/features.py src/gemini_trading/strategy/labels.py tests/unit/strategy/test_features.py tests/unit/strategy/test_labels.py tests/property/strategy/test_strategy_feature_point_in_time.py
git commit -m "feat: isolate features and labels by candle segment"
```

---

### Task 9: Protect chronological splits and final-test identity

**Files:**
- Modify: `src/gemini_trading/strategy/splits.py`
- Modify: `src/gemini_trading/strategy/study.py`
- Modify: `src/gemini_trading/strategy/study_plans.py`
- Modify: `tests/unit/strategy/test_splits.py`
- Modify: `tests/unit/strategy/test_study.py`

**Interfaces:**
- Change `ChronologicalSplitPlan.build(..., segments: CandleSegmentManifest | None = None)`.
- Add `segment_boundary_indices: tuple[int, ...]` and include it in `split_plan_payload` and `split_plan_sha256`.
- `build_split_plan(dataset.candles, eligible, policy, segments=dataset.segment_manifest)` must reject any closure boundary at or after `final_test_boundary_index`.

- [ ] **Step 1: Write failing boundary-protection tests**

Test that label horizons, purge, and embargo protect every segment start; no used index crosses a segment boundary; and a final-test-intersecting closure raises `FinalTestSealError`.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/strategy/test_splits.py tests/unit/strategy/test_study.py -v
```

- [ ] **Step 3: Implement split-plan segment identity**

Use segment starts after the first segment as protected boundaries. Merge them with fold and final-test boundaries for `_safe_indices`, but preserve them separately in serialized identity.

- [ ] **Step 4: Remove the strict full-dataset continuity assumption**

Replace `_validate_candles` continuity checking with exact validation against the supplied segment manifest. Within every segment, continue requiring contiguous open and close boundaries.

- [ ] **Step 5: Run tests and static checks**

```bash
uv run pytest tests/unit/strategy/test_splits.py tests/unit/strategy/test_study.py -v
uv run ruff format --check src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/study.py src/gemini_trading/strategy/study_plans.py
uv run ruff check src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/study.py src/gemini_trading/strategy/study_plans.py
uv run pyright src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/study.py src/gemini_trading/strategy/study_plans.py
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/study.py src/gemini_trading/strategy/study_plans.py tests/unit/strategy/test_splits.py tests/unit/strategy/test_study.py
git commit -m "feat: protect study splits at closure boundaries"
```

---

### Task 10: Enforce cash-only simulator state at segment boundaries

**Files:**
- Modify: `src/gemini_trading/research/engine.py`
- Modify: `src/gemini_trading/strategy/study_strategy.py`
- Modify: `src/gemini_trading/strategy/study_execution.py`
- Modify: `tests/unit/research/test_engine.py`
- Modify: `tests/unit/strategy/test_study_execution.py`

**Interfaces:**
- BacktestEngine reads `dataset.segment_manifest` and detects segment starts automatically.
- At a segment start after index zero, require no active order and `account.position_quantity == 0`; otherwise raise `ChronologyViolationError("noncash state crosses candle segment boundary")` before evaluating the resumed candle.
- Clear only nonfinancial strategy-control state that is explicitly held by the study executor; do not create an order, fill, ledger row, fee, slippage, return, or synthetic account transfer.
- `ReplayableStudyStrategy` configuration includes `segment_boundary_indices` so replay verifies identical boundaries.

- [ ] **Step 1: Write failing engine boundary tests**

Create one test with cash/no orders that processes the resumed candle and one with an open position that fails before the resumed candle. Assert the failure produces no synthetic fill or ledger row.

- [ ] **Step 2: Write failing schedule tests**

Require every scheduled event and its next-candle execution to remain in the same segment. Reject a plan that enters before a boundary and could execute after it.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/unit/research/test_engine.py tests/unit/strategy/test_study_execution.py -v
```

- [ ] **Step 4: Implement boundary guard and canonical strategy configuration**

Add the segment boundaries to the immutable experiment strategy configuration and replay parser. Check boundary safety before `_evaluate_orders` in `process_candle`.

- [ ] **Step 5: Run focused tests and static checks**

```bash
uv run pytest tests/unit/research/test_engine.py tests/unit/strategy/test_study_execution.py -v
uv run ruff format --check src/gemini_trading/research/engine.py src/gemini_trading/strategy/study_strategy.py src/gemini_trading/strategy/study_execution.py
uv run ruff check src/gemini_trading/research/engine.py src/gemini_trading/strategy/study_strategy.py src/gemini_trading/strategy/study_execution.py
uv run pyright src/gemini_trading/research/engine.py src/gemini_trading/strategy/study_strategy.py src/gemini_trading/strategy/study_execution.py
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/research/engine.py src/gemini_trading/strategy/study_strategy.py src/gemini_trading/strategy/study_execution.py tests/unit/research/test_engine.py tests/unit/strategy/test_study_execution.py
git commit -m "feat: guard simulator state at closure boundaries"
```

---

### Task 11: Bind segments into sealed preparation, finalization, replay, and verification

**Files:**
- Modify: `src/gemini_trading/strategy/evaluator.py`
- Modify: `src/gemini_trading/strategy/sealed_evaluator.py`
- Modify: `src/gemini_trading/strategy/pre_final.py`
- Modify: `src/gemini_trading/strategy/replay.py`
- Modify: `src/gemini_trading/strategy/sealed_verification.py`
- Modify: `tests/integration/test_sealed_historical_validation.py`
- Modify: `tests/regression/test_durable_final_test_access.py`

**Interfaces:**
- All feature, label, split, schedule, and engine construction receives `dataset.segment_manifest`.
- Pre-final manifest records closure-manifest SHA-256, segment-manifest SHA-256, segment count, closure IDs, and segment-boundary indices.
- Final-access identity remains bound to `split_plan_sha256`; because segment boundaries are inside that hash, a changed closure or segment invalidates access.
- Strategy replay and independent verification rederive the same segment-safe evidence provider-free.

- [ ] **Step 1: Write failing integration tests**

Use a multi-segment synthetic `VerifiedDataset`. Assert preparation succeeds without cross-segment features or labels, pre-final evidence contains exact hashes, altered segment bytes fail verification, and existing second-access rejection remains unchanged.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
uv run pytest tests/integration/test_sealed_historical_validation.py tests/regression/test_durable_final_test_access.py -v
```

- [ ] **Step 3: Thread segment evidence through evaluator paths**

Update calls to:

```python
matrix = registry.compute(dataset.candles, segments=dataset.segment_manifest)
labels = label_policy.build(dataset.candles, eligible_indices=..., segments=dataset.segment_manifest)
split_plan, history_requirement_met = build_split_plan(
    dataset.candles,
    eligible,
    policy,
    segments=dataset.segment_manifest,
)
```

- [ ] **Step 4: Add immutable evidence fields**

Include closure and segment identity in pre-final and final study manifests, artifact inventories, replay comparisons, verification reports, and limitations. Do not add generated raw data to Git.

- [ ] **Step 5: Run focused tests and static checks**

```bash
uv run pytest tests/integration/test_sealed_historical_validation.py tests/regression/test_durable_final_test_access.py -v
uv run ruff format --check src/gemini_trading/strategy
uv run ruff check src/gemini_trading/strategy
uv run pyright src/gemini_trading/strategy
```

- [ ] **Step 6: Commit**

```bash
git add src/gemini_trading/strategy/evaluator.py src/gemini_trading/strategy/sealed_evaluator.py src/gemini_trading/strategy/pre_final.py src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/sealed_verification.py tests/integration/test_sealed_historical_validation.py tests/regression/test_durable_final_test_access.py
git commit -m "feat: seal segment identity through final verification"
```

---

### Task 12: Complete acceptance, tamper, documentation, and workflow contracts

**Files:**
- Modify: `tests/acceptance/test_sealed_historical_validation_end_to_end.py`
- Modify: `tests/acceptance/test_candidate_strategy_end_to_end.py`
- Modify: `tests/acceptance/test_sealed_historical_validation_documentation.py`
- Modify: `tests/acceptance/test_sealed_historical_validation_workflows.py`
- Modify: `docs/operations/sealed-btcusdt-historical-validation.md`
- Modify: `README.md`
- Modify: `.github/workflows/sealed-btcusdt-study.yml`

**Interfaces:**
- Stage 2 accepts only `sealed-dataset-handoff-v2` and `candle-dataset-v2`.
- Documentation must state the exact closure, seven missing opens, no synthetic data, segment-local warm-up, cash-only boundary rule, and Stage 2 approval gate.

- [ ] **Step 1: Add complete synthetic acceptance coverage**

The end-to-end test must ingest gapped raw pages, produce v2 evidence, replay and independently verify it, prepare a sealed study, preserve final-access isolation, complete provider-free, and reject tampered closure/segment files.

- [ ] **Step 2: Add workflow-contract assertions**

Assert fixed manifest path, no arbitrary manifest inputs, v2 handoff checks in Stage 2, artifact inclusion, manual dispatch only, least privilege, and unchanged one-time final-access controls.

- [ ] **Step 3: Update operator documentation**

Document exact commands, files, hashes, expected Stage 1 outputs, artifact review procedure, and explicit instruction not to run Stage 2 until Issue #22 contains the exact dataset approval marker.

- [ ] **Step 4: Run acceptance and documentation tests**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_end_to_end.py tests/acceptance/test_candidate_strategy_end_to_end.py tests/acceptance/test_sealed_historical_validation_documentation.py tests/acceptance/test_sealed_historical_validation_workflows.py -v
pre-commit run check-yaml --files .github/workflows/sealed-btcusdt-dataset.yml .github/workflows/sealed-btcusdt-study.yml
```

- [ ] **Step 5: Commit**

```bash
git add tests/acceptance/test_sealed_historical_validation_end_to_end.py tests/acceptance/test_candidate_strategy_end_to_end.py tests/acceptance/test_sealed_historical_validation_documentation.py tests/acceptance/test_sealed_historical_validation_workflows.py docs/operations/sealed-btcusdt-historical-validation.md README.md .github/workflows/sealed-btcusdt-study.yml
git commit -m "test: verify sealed closure-aware historical validation"
```

---

### Task 13: Run complete repository verification and protected merge preparation

**Files:**
- Modify only files required by failures directly caused by this implementation.
- Do not dispatch either sealed workflow from the implementation branch.

- [ ] **Step 1: Run the exact repository gate locally**

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
pre-commit run --all-files
```

Expected: all commands pass; the live Binance smoke test remains skipped unless explicitly enabled.

- [ ] **Step 2: Confirm safety invariants by search**

```bash
git grep -n -E "forward.?fill|interpolat|synthetic candle|zero-volume candle" -- src tests .github docs

git grep -n -E "closure.manifest.*(input|env)|inputs:.*closure|CLOSURE_MANIFEST" -- .github src

git grep -n -E "api\.binance\.com" -- src .github
```

Expected:
- no implementation path fabricates candles;
- no dispatch input or environment override selects a closure manifest;
- public-only provider remains `data-api.binance.vision`.

- [ ] **Step 3: Review the branch diff**

```bash
git diff --check main...HEAD
git diff --stat main...HEAD
git status --short
```

Expected: no whitespace errors and a clean working tree.

- [ ] **Step 4: Push and open one protected implementation PR**

The PR body must list the design commit, plan path, exact approved closure, v2 identity changes, segment-safe controls, test results, and `RESEARCH_ONLY` boundary.

- [ ] **Step 5: Wait for exact-head CI**

Require `quality` and `gitleaks` success against the final PR head. Do not merge stale green checks after any commit movement.

- [ ] **Step 6: Squash-merge with expected head SHA**

Use the repository’s established squash-merge pattern. Record the new merged `main` SHA in Issue #22. Stage 1 is not yet authorized until exact merged-main verification passes.

---

### Task 14: Verify merged main and run Stage 1 only

**Files:**
- No source change unless exact merged-main verification discovers a defect.
- Update Issue #22 with verification and artifact review comments.

- [ ] **Step 1: Verify the exact merged-main commit**

Run the complete frozen CI gate against the exact merged SHA and record workflow IDs and conclusions in Issue #22.

- [ ] **Step 2: Dispatch a new Stage 1 workflow**

From **Actions → Sealed BTCUSDT Dataset**, select `main` and confirm the displayed commit is the exact approved merged-main SHA. Do not use “Re-run jobs” on an older run.

- [ ] **Step 3: Require exact Stage 1 evidence**

The run must report:

- one approved closure ID;
- seven missing 4-hour candle opens;
- two continuous segments;
- no additional undeclared gaps;
- successful provider-free replay;
- successful independent verification;
- a `candle-dataset-v2` ID;
- one uploaded Stage 1 artifact.

- [ ] **Step 4: Download and independently inspect the artifact**

Verify the inventory root, canonical candles, closure manifest, segment manifest, retrieval manifest, provenance, handoff, hashes, counts, paths, source commit, run ID, and run attempt.

- [ ] **Step 5: Record the exact approval marker only after successful review**

Add the repository-required `sealed-dataset-approved:<dataset_id>` marker to Issue #22 with source commit, workflow run ID, attempt, artifact name, inventory root, and verification outcomes.

- [ ] **Step 6: Keep Stage 2 blocked until the marker exists**

Do not dispatch **Sealed BTCUSDT Study** before the exact marker is present and independently checked by the workflow.

---

## Plan Self-Review

- **Spec coverage:** Every design component is assigned: fixed manifest (Task 1), exact matching and segments (Task 2), v2 identity (Task 3), storage (Task 4), ingestion/replay/verification (Task 5), loader/handoff (Task 6), fixed workflow commands (Task 7), features/labels (Task 8), splits/final seal (Task 9), simulator boundary safety (Task 10), sealed evidence/replay (Task 11), acceptance/docs/workflows (Task 12), protected verification (Tasks 13–14).
- **No candle fabrication:** No task inserts, fills, interpolates, or edits a candle.
- **Boundary accounting:** A noncash state at a segment boundary fails closed; no synthetic liquidation, fill, fee, return, or cash transfer is introduced.
- **Type consistency:** `ExchangeClosureManifest`, `CandleSegmentManifest`, `VerifiedDataset.segment_manifest`, and v2 handoff field names are consistent throughout the plan.
- **Final-test isolation:** Segment boundaries enter `split_plan_sha256`; closures touching the final partition are rejected before access.
- **Authority:** Stage 1 only after protected merge and exact-main verification; Stage 2 remains separately gated.
