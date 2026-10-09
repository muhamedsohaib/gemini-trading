# Candidate Multi-Model Strategy v0.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Candidate v0.4 as a new, independently replayable BTCUSDT Spot long/cash research candidate that uses a canonical completed 1h tactical timeline conditioned by deterministic completed 4h regime/context information, while preserving all v0.1-v0.3 evidence and behavior.

**Architecture:** Keep prior candidates immutable. Add v0.4-specific policy adjuncts, Stage 1 handoff, deterministic 1h→4h context derivation/as-of joins, 1h tactical feature/model domains, 12-hour labels and guarded splits, regime-owned prediction/arbitration, controls/diagnostics, strict qualification, immutable evidence/replay, CLI/workflow surfaces, and prospective-seal support beside the existing v0.3 implementation. Reuse the deterministic simulator, execution costs, portable model artifacts, baseline implementations, canonical serialization, and provider-free verification infrastructure wherever their semantics remain valid.

**Tech Stack:** Python 3.12, `Decimal`, scikit-learn 1.9.0, NumPy only where already present, threadpoolctl, canonical JSON/JSONL, pytest, Ruff, strict Pyright, GitHub Actions.

## Global Constraints

- Entire milestone remains `RESEARCH_ONLY`.
- No credentials, private exchange endpoints, paper/demo/live order submission, leverage, margin, futures, options, shorting, portfolio allocation, autonomous capital, or production execution.
- Candidate v0.1, v0.2, and v0.3 serialized policies, decisions, qualification evidence, replay behavior, and terminal classifications must remain unchanged.
- v0.4 identity is exactly `candidate.multi_model.v0_4` / `candidate-multi-model-v0.4` / `candidate-strategy-policy-v4`.
- Market scope is exactly Binance Spot BTCUSDT, long or cash only.
- Development data is exactly `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`.
- Tactical clock is completed `1h`; context clock is completed `4h` derived deterministically from canonical 1h evidence.
- A valid 4h bar requires four consecutive valid completed 1h constituents in one verified continuous segment and UTC four-hour alignment.
- The 1h→4h join is strict as-of: a 1h decision may use only the latest 4h context whose close time is `<=` the decision timestamp.
- The compact 4h numeric context is exactly six features: signed EMA12/42 spread over ATR24, RV6/RV42, true-range/ATR24, trailing-24-bar range location, trailing-24-bar median displacement over ATR24, and 3-bar EMA12 slope over ATR24.
- Trend model family remains scikit-learn 1.9.0 elastic-net logistic regression with `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, one thread, `tol=1e-7`, `max_iter=50000`.
- Mean-reversion model family remains deterministic gradient boosting with 150 estimators, depth 2, learning rate `0.03`, minimum leaf 100, no subsampling, seed `1702`, one thread.
- Trend fitting/calibration uses only 4h-`TRENDING` rows. Mean-reversion fitting/calibration uses only 4h-`RANGING` rows with 1h `close_zscore_24 <= -0.75` or `drawdown_from_high_24 >= 0.02`.
- Economic label horizon is exactly 12 held hours; official simulated entry is next-1h-candle execution; the positive class requires full modeled round-trip costs plus 10 bps.
- Primary entry selectivity remains fold-local q75 with floor `0.50`; sensitivity neighbors are q70/q80; minimum eligible q75 scores are 160.
- Calibration minima per specialist/fold are 800 eligible observations, 160 positive labels, and 160 negative labels.
- Real-time risk durations are 8h minimum ordinary hold, 72h maximum hold, and 8h cooldown. Tactical protection is 2.5×1h ATR initial and 3.0×1h ATR trailing.
- `UNSTABLE` forces exit; position ownership is frozen at entry; specialist handoff while long is prohibited.
- Walk-forward structure is 24 calendar months train, 6 months calibration, 6 months development test, 6 months step, expanding history.
- Purge and embargo are each 12 completed 1h bars and all verified segment boundaries remain protected.
- Development gates remain at least: 60% positive folds, 60% baseline RTD wins when defined, <=50% positive-profit concentration, and >=60 completed trades.
- 1.5× costs require net return >0 and drawdown <=27.5%; 2× costs require return >=-5% and drawdown <=30%; higher costs may not improve aggregate return.
- Sensitivity requires >=7/10 positive variants, positive median return, and no aggregate drawdown above 35%.
- Paired moving-block bootstrap uses 1,000 replicates, 168 one-hour bars per block unless mathematically shortened by path length, frozen seed `1788`, median candidate-minus-baseline return >0, and 90% lower bound >-2 percentage points.
- Mandatory controls include shuffled labels, delayed features, no volume, no protection, no-percentile-selectivity, and no-4h-numeric-context.
- Opportunity-density diagnostics are evidence only and may never trigger threshold relaxation or performance-driven rescue.
- A complete valid mandatory failure is terminal `REJECTED`. Missing/invalid/interrupted evidence is `INCONCLUSIVE`. Only `QUALIFIED` permits a prospective seal.
- No v0.4 development result may alter the specification. Any financial redesign after evidence is Candidate v0.5.
- Prospective-final access remains impossible unless complete v0.4 development qualification is `QUALIFIED` and independently verified; the final era is exactly 18 calendar months with no interim strategy-performance peeking.
- Do not dispatch Stage 1 or qualification from an implementation branch. Stage 1 is permitted only after protected merge and exact merged-main CI success.
- Every implementation task follows RED -> verify RED -> minimal GREEN -> focused verification -> commit.

## File Structure

New version-specific modules keep the multi-timeframe experiment isolated from prior candidate behavior:

- `src/gemini_trading/strategy/v0_4_policy.py` — context/selectivity/timing constants not representable safely in the legacy `CandidatePolicy` schema.
- `src/gemini_trading/strategy/v0_4_stage1.py` — exact 1h development dataset/handoff identity and verification.
- `src/gemini_trading/strategy/v0_4_context.py` — deterministic 1h→4h aggregation, context features, regime observation, and strict as-of join.
- `src/gemini_trading/strategy/v0_4_features.py` — tactical feature registry plus exact six-context feature projection.
- `src/gemini_trading/strategy/v0_4_splits.py` — 12h-safe expanding development walk-forward plan.
- `src/gemini_trading/strategy/v0_4_predictions.py` — regime-matched fitting, calibration, expected-return mapping, thresholds, predictions, ownership, and opportunity diagnostics.
- `src/gemini_trading/strategy/v0_4_cases.py` — primary, baselines, controls, ablations, cost stresses, and sensitivity case IDs.
- `src/gemini_trading/strategy/v0_4_study_plans.py` — deterministic simulator plans for every required case.
- `src/gemini_trading/strategy/qualification_v0_4.py` — closed mandatory gate evaluation.
- `src/gemini_trading/strategy/qualification_execution_v0_4.py` — end-to-end development qualification executor.
- `src/gemini_trading/strategy/qualification_artifacts_v0_4.py` — immutable qualification evidence package and identity.
- `src/gemini_trading/strategy/qualification_replay_v0_4.py` — provider-free reconstruction of the qualification result.
- `src/gemini_trading/strategy/qualification_verification_v0_4.py` — independent evidence verification.
- `src/gemini_trading/strategy/prospective_seal_v0_4.py` — prospective seal available only from verified `QUALIFIED` evidence.
- `src/gemini_trading/cli/candidate_v0_4.py` — research-only Stage 1, qualify, verify, and seal CLI handlers.
- `.github/workflows/candidate-v0.4-stage1.yml` and `.github/workflows/candidate-v0.4-qualification.yml` — manual, exact-source governed workflows.

Shared files may be extended only through backward-compatible optional interfaces and must retain regression tests for v0.1-v0.3.

---

### Task 1: Freeze v0.4 Identity and Multi-Timeframe Policy Adjuncts

**Files:**
- Modify: `src/gemini_trading/strategy/policy.py`
- Create: `src/gemini_trading/strategy/v0_4_policy.py`
- Create: `tests/fixtures/strategy/candidate-v0.4-config.json`
- Modify: `tests/unit/strategy/test_policy.py`
- Create: `tests/unit/strategy/test_v0_4_policy.py`
- Modify: `tests/unit/cli/test_candidate_strategy_cli.py`

**Interfaces:**
- Produces: `CandidatePolicy.locked_v0_4() -> CandidatePolicy`
- Produces: `V04MultiTimeframePolicy.locked() -> V04MultiTimeframePolicy`
- Extends: `approved_candidate_policy(strategy_id: str, policy_version: str) -> CandidatePolicy`
- Constraint: serialization of `CandidatePolicy.locked_v0_1()`, `locked_v0_2()`, and `locked_v0_3()` stays byte-identical.

- [ ] **Step 1: Write RED identity, timing, and prior-byte regression tests**

```python
def test_locked_v0_4_translates_real_time_contract_to_hourly_policy() -> None:
    policy = CandidatePolicy.locked_v0_4()
    assert policy.strategy_id == "candidate.multi_model.v0_4"
    assert policy.policy_version == "candidate-multi-model-v0.4"
    assert policy.schema_version == "candidate-strategy-policy-v4"
    assert policy.timeframe == "1h"
    assert policy.label_horizon_candles == 12
    assert policy.maximum_feature_lookback_candles == 42
    assert policy.minimum_hold_candles == 8
    assert policy.maximum_hold_candles == 72
    assert policy.cooldown_candles == 8
    assert policy.purge_candles == 12
    assert policy.embargo_candles == 12
    assert policy.calibration_minimum_observations == 800
    assert policy.calibration_minimum_positive == 160
    assert policy.calibration_minimum_negative == 160
    assert policy.bootstrap_block_candles == 168
```

Freeze SHA-256 assertions for the current v0.1/v0.2/v0.3 serialized policy bytes before adding v0.4.

Run: `uv run pytest tests/unit/strategy/test_policy.py tests/unit/strategy/test_v0_4_policy.py -v`
Expected: FAIL because v0.4 policy constructors do not exist.

- [ ] **Step 2: Add `locked_v0_4()` without changing prior policy construction**

```python
@classmethod
def locked_v0_4(cls) -> "CandidatePolicy":
    return replace(
        cls.locked_v0_3(),
        schema_version="candidate-strategy-policy-v4",
        strategy_id="candidate.multi_model.v0_4",
        policy_version="candidate-multi-model-v0.4",
        timeframe="1h",
        label_horizon_candles=12,
        maximum_feature_lookback_candles=42,
        minimum_hold_candles=8,
        maximum_hold_candles=72,
        cooldown_candles=8,
        purge_candles=12,
        embargo_candles=12,
        calibration_minimum_observations=800,
        calibration_minimum_positive=160,
        calibration_minimum_negative=160,
        bootstrap_block_candles=168,
    )
```

Do not add fields to the legacy dataclass; v0.4-only context semantics belong in the adjunct below.

- [ ] **Step 3: Implement the v0.4 adjunct policy with canonical serialization**

```python
@dataclass(frozen=True, slots=True)
class V04MultiTimeframePolicy:
    schema_version: str
    tactical_timeframe: str
    context_timeframe: str
    context_feature_names: tuple[str, ...]
    entry_percentile: Decimal
    entry_floor: Decimal
    minimum_entry_scores: int
    sensitivity_percentiles: tuple[Decimal, Decimal]
    indeterminate_tolerance_context_bars: int
    incompatible_tolerance_context_bars: int

    @classmethod
    def locked(cls) -> "V04MultiTimeframePolicy":
        return cls(
            schema_version="candidate-v0.4-multitimeframe-policy-v1",
            tactical_timeframe="1h",
            context_timeframe="4h",
            context_feature_names=(
                "ctx4h_ema_12_42_signed_atr24",
                "ctx4h_volatility_ratio_6_42",
                "ctx4h_true_range_ratio_24",
                "ctx4h_range_location_24",
                "ctx4h_median_distance_atr24",
                "ctx4h_ema12_slope_3_atr24",
            ),
            entry_percentile=Decimal("0.75"),
            entry_floor=Decimal("0.50"),
            minimum_entry_scores=160,
            sensitivity_percentiles=(Decimal("0.70"), Decimal("0.80")),
            indeterminate_tolerance_context_bars=1,
            incompatible_tolerance_context_bars=2,
        )
```

Serialize with `canonical_json_bytes(asdict(policy))`; qualification identity later binds the digest.

- [ ] **Step 4: Add exact config/loader tests**

Create `tests/fixtures/strategy/candidate-v0.4-config.json` with the v0.4 identity and existing simulation economics. Assert mismatched strategy/policy pairs fail closed and prior fixtures still load unchanged.

Run: `uv run pytest tests/unit/strategy/test_policy.py tests/unit/strategy/test_v0_4_policy.py tests/unit/cli/test_candidate_strategy_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/policy.py src/gemini_trading/strategy/v0_4_policy.py tests/fixtures/strategy/candidate-v0.4-config.json tests/unit/strategy/test_policy.py tests/unit/strategy/test_v0_4_policy.py tests/unit/cli/test_candidate_strategy_cli.py
git commit -m "feat: define Candidate v0.4 policy"
```

---

### Task 2: Add the Canonical 1h Stage 1 Contract and Version-Isolated Handoff

**Files:**
- Create: `src/gemini_trading/strategy/v0_4_stage1.py`
- Create: `tests/unit/strategy/test_v0_4_stage1.py`
- Modify only if required for interval-generic closure validation: `src/gemini_trading/data/exchange_closures.py`
- Modify corresponding tests only if the shared closure validator needs interval-generic behavior: `tests/unit/data/test_exchange_closures.py`

**Interfaces:**
- Produces: `V04_STAGE1_START`, `V04_STAGE1_END_EXCLUSIVE`
- Produces: `V04DatasetHandoffManifest`
- Produces: `build_v0_4_closure_manifest(project_root: Path) -> tuple[ExchangeClosureManifest, bytes]`
- Produces: `assert_v0_4_dataset_identity(dataset: VerifiedDataset, project_root: Path) -> None`
- Produces: `create_v0_4_dataset_handoff(...)`, `load_v0_4_dataset_handoff(...)`, `verify_v0_4_dataset_handoff(...)`

- [ ] **Step 1: Write RED tests for exact 1h scope and fail-closed handoff identity**

```python
def test_v0_4_stage1_requires_exact_hourly_window() -> None:
    manifest, _ = build_v0_4_closure_manifest(PROJECT_ROOT)
    assert manifest.start_time == datetime(2018, 1, 1, tzinfo=UTC)
    assert manifest.end_time == datetime(2026, 8, 1, tzinfo=UTC)


def test_v0_4_handoff_rejects_wrong_interval(valid_manifest: V04DatasetHandoffManifest) -> None:
    payload = asdict(valid_manifest)
    payload["interval"] = "4h"
    with pytest.raises(DatasetHandoffError, match="market scope mismatch"):
        load_v0_4_dataset_handoff(canonical_json_bytes(payload))
```

Also test wrong source commit, run attempt, post-cutoff candle, incomplete candle, missing closure/exclusion/segment evidence, inventory mismatch, and a segment manifest that does not cover the canonical 1h series.

Run: `uv run pytest tests/unit/strategy/test_v0_4_stage1.py -v`
Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement the exact Stage 1 constants and 1h handoff schema**

Use:

```python
V04_STAGE1_START = datetime(2018, 1, 1, tzinfo=UTC)
V04_STAGE1_END_EXCLUSIVE = datetime(2026, 8, 1, tzinfo=UTC)
_SCHEMA_VERSION = "candidate-v0.4-dataset-handoff-v1"
_WORKFLOW_NAME = "candidate-v0.4-stage1"
_PROVIDER = "binance_spot"
_SYMBOL = "BTCUSDT"
_INTERVAL = "1h"
```

The handoff must persist source commit, workflow run/attempt, dataset ID, canonical schema, closure/exclusion/segment identities, segment boundaries, candle count, first/last opens, replay/verification status, complete file inventory, and inventory-root SHA-256.

- [ ] **Step 3: Make closure validation interval-generic only where mathematically necessary**

The implementation may reuse the same declared exchange-closure time intervals, but it must derive expected 1h unavailable slots and segment boundaries from timestamps rather than copying v0.3's 4h `EXPECTED_COUNTS`/`EXPECTED_BOUNDARIES`. Do not inspect prices or strategy outcomes to derive them.

```python
def expected_missing_opens(
    start: datetime,
    end_exclusive: datetime,
    timeframe: Timeframe,
    closures: tuple[ExchangeClosure, ...],
) -> tuple[datetime, ...]:
    opens = tuple(iter_expected_opens(start, end_exclusive, timeframe.duration))
    return tuple(open_time for open_time in opens if any(covers(item, open_time) for item in closures))
```

If the existing closure primitives already provide an equivalent interval-generic function, reuse it and leave shared files untouched.

- [ ] **Step 4: Verify synthetic and existing v0.3 Stage 1 regressions**

```bash
uv run pytest tests/unit/strategy/test_v0_4_stage1.py tests/unit/strategy/test_v0_3_stage1.py -v
uv run pyright src/gemini_trading/strategy/v0_4_stage1.py
uv run ruff check src/gemini_trading/strategy/v0_4_stage1.py tests/unit/strategy/test_v0_4_stage1.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/v0_4_stage1.py tests/unit/strategy/test_v0_4_stage1.py src/gemini_trading/data/exchange_closures.py tests/unit/data/test_exchange_closures.py
git commit -m "feat: add v0.4 hourly Stage 1 contract"
```

If the two shared closure files are unchanged, omit them from `git add`.

---

### Task 3: Derive Completed 4h Context and Enforce the Strict As-Of Join

**Files:**
- Create: `src/gemini_trading/strategy/v0_4_context.py`
- Create: `tests/unit/strategy/test_v0_4_context.py`

**Interfaces:**
- Produces: `DerivedContextBar`
- Produces: `ContextObservation`
- Produces: `derive_v0_4_context_bars(candles: tuple[Candle, ...], segment_boundaries: tuple[int, ...]) -> tuple[DerivedContextBar, ...]`
- Produces: `join_v0_4_context(candles: tuple[Candle, ...], context_bars: tuple[DerivedContextBar, ...]) -> tuple[ContextObservation | None, ...]`

- [ ] **Step 1: Write RED aggregation and look-ahead tests**

```python
def test_context_bar_uses_exactly_four_completed_hourly_constituents() -> None:
    bars = derive_v0_4_context_bars(hourly_00_to_04, ())
    assert len(bars) == 1
    bar = bars[0].candle
    assert bar.timeframe is Timeframe.H4
    assert bar.open == Decimal("100")
    assert bar.high == Decimal("109")
    assert bar.low == Decimal("98")
    assert bar.close == Decimal("107")
    assert bar.volume == Decimal("46")


def test_context_is_not_visible_before_its_close() -> None:
    bars = derive_v0_4_context_bars(hourly_00_to_04, ())
    joined = join_v0_4_context(hourly_00_to_04, bars)
    assert joined[2] is None
    assert joined[3] is None
```

Add an explicit decision-row fixture at `04:00` and assert it sees `[00:00,04:00)` while a `03:00` decision does not. Add tests rejecting a partial four-hour block, a block crossing a segment boundary, duplicate/out-of-order hours, and mixed instruments/timeframes.

Run: `uv run pytest tests/unit/strategy/test_v0_4_context.py -v`
Expected: FAIL because the module is absent.

- [ ] **Step 2: Implement deterministic four-hour aggregation with constituent identities**

```python
@dataclass(frozen=True, slots=True)
class DerivedContextBar:
    candle: Candle
    constituent_indices: tuple[int, int, int, int]
    constituent_sha256: str


def _valid_group(indices: tuple[int, int, int, int], candles: tuple[Candle, ...]) -> bool:
    first = candles[indices[0]]
    return (
        first.open_time.hour % 4 == 0
        and all(candles[index].completed for index in indices)
        and all(candles[index].timeframe is Timeframe.H1 for index in indices)
        and all(candles[indices[offset]].open_time + timedelta(hours=1) == candles[indices[offset + 1]].open_time for offset in range(3))
    )
```

Persist a canonical digest of constituent indices/open times/OHLCV so independent replay proves exactly which hourly evidence generated every context bar.

- [ ] **Step 3: Implement strict as-of joining by close timestamp**

```python
def join_v0_4_context(
    candles: tuple[Candle, ...],
    context_bars: tuple[DerivedContextBar, ...],
) -> tuple[ContextObservation | None, ...]:
    result: list[ContextObservation | None] = []
    cursor = -1
    for candle in candles:
        decision_time = candle.close_time + timedelta(milliseconds=1)
        while cursor + 1 < len(context_bars) and context_bars[cursor + 1].candle.close_time < decision_time:
            cursor += 1
        result.append(None if cursor < 0 else ContextObservation.from_bar(context_bars[cursor]))
    return tuple(result)
```

Use the repository's exact candle close/open convention in the final implementation; tests must prove `context.close_time <= decision_time` and never future visibility.

- [ ] **Step 4: Verify determinism**

Rebuilding from identical candles must produce byte-identical canonical context inventory and joins.

```bash
uv run pytest tests/unit/strategy/test_v0_4_context.py -v
uv run pyright src/gemini_trading/strategy/v0_4_context.py
uv run ruff check src/gemini_trading/strategy/v0_4_context.py tests/unit/strategy/test_v0_4_context.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/v0_4_context.py tests/unit/strategy/test_v0_4_context.py
git commit -m "feat: derive v0.4 four-hour context"
```

---

### Task 4: Build the Exact Tactical + Compact Context Feature Contract

**Files:**
- Create: `src/gemini_trading/strategy/v0_4_features.py`
- Modify only through a backward-compatible helper if needed: `src/gemini_trading/strategy/features.py`
- Create: `tests/unit/strategy/test_v0_4_features.py`
- Modify: `tests/unit/strategy/test_features.py`

**Interfaces:**
- Produces: `V04FeatureRegistry.locked() -> V04FeatureRegistry`
- Produces: `build_v0_4_feature_matrix(candles, segment_manifest, context_join) -> FeatureMatrix`
- Produces exact `trend_feature_names` and `mean_reversion_feature_names` including the six context names.

- [ ] **Step 1: Write RED registry and point-in-time tests**

```python
def test_v0_4_registry_has_exactly_six_context_features_per_specialist() -> None:
    registry = V04FeatureRegistry.locked()
    context = V04MultiTimeframePolicy.locked().context_feature_names
    assert tuple(name for name in registry.trend_feature_names if name.startswith("ctx4h_")) == context
    assert tuple(name for name in registry.mean_reversion_feature_names if name.startswith("ctx4h_")) == context
```

Add tests that the tactical portion retains the approved v0.1 economic feature families on 1h bars, maximum tactical dependency is 42 hours, no categorical regime feature is present, and mutating a future 1h candle cannot change any earlier feature row.

Run: `uv run pytest tests/unit/strategy/test_v0_4_features.py -v`
Expected: FAIL because the registry is absent.

- [ ] **Step 2: Reuse existing tactical calculations at 1h resolution**

Do not rewrite indicator mathematics. Call the established feature builder on the canonical 1h candles, then append only the six context columns from the joined completed 4h evidence.

```python
CONTEXT_FEATURE_NAMES = V04MultiTimeframePolicy.locked().context_feature_names

@dataclass(frozen=True, slots=True)
class V04FeatureRegistry:
    trend_feature_names: tuple[str, ...]
    mean_reversion_feature_names: tuple[str, ...]
    context_feature_names: tuple[str, ...]
```

- [ ] **Step 3: Compute the six context values only from completed 4h history**

The context matrix must compute exactly:

```python
signed_spread = (ema12 - ema42) / atr24
volatility_ratio = rv6 / rv42
true_range_ratio = true_range / atr24
range_location = (close - low24) / (high24 - low24)
median_distance = (close - median24) / atr24
ema12_slope = (ema12 - ema12_three_bars_ago) / atr24
```

Zero denominators or insufficient 4h history make that 1h tactical observation ineligible; do not impute.

- [ ] **Step 4: Verify old feature bytes and new matrix determinism**

```bash
uv run pytest tests/unit/strategy/test_features.py tests/unit/strategy/test_v0_4_features.py -v
uv run pyright src/gemini_trading/strategy/features.py src/gemini_trading/strategy/v0_4_features.py
uv run ruff check src/gemini_trading/strategy/features.py src/gemini_trading/strategy/v0_4_features.py tests/unit/strategy/test_v0_4_features.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/v0_4_features.py src/gemini_trading/strategy/features.py tests/unit/strategy/test_v0_4_features.py tests/unit/strategy/test_features.py
git commit -m "feat: add v0.4 hierarchical features"
```

Omit unchanged shared files from `git add`.

---

### Task 5: Implement 12h Labels and the 12h-Safe Expanding Split Plan

**Files:**
- Modify through optional/generalized interfaces only: `src/gemini_trading/strategy/labels.py`
- Create: `src/gemini_trading/strategy/v0_4_splits.py`
- Create: `tests/unit/strategy/test_v0_4_labels.py`
- Create: `tests/unit/strategy/test_v0_4_splits.py`
- Modify: `tests/unit/strategy/test_labels.py`

**Interfaces:**
- Produces: the existing `LabelVector` under `CandidatePolicy.locked_v0_4()` with 12 held one-hour bars.
- Produces: `V04DevelopmentQualificationPlan.build(...) -> V04DevelopmentQualificationPlan`
- Label boundary offset must be derived from the exact simulator next-candle/12-held-candle convention and tested, not copied from v0.3's `_LABEL_EXIT_OFFSET = 4`.

- [ ] **Step 1: Write RED label economics/timing tests**

```python
def test_v0_4_positive_label_uses_next_hour_entry_and_twelve_hour_horizon() -> None:
    labels = build_labels(hourly_candles, simulation, CandidatePolicy.locked_v0_4())
    label = labels.for_index(50)
    assert label.entry_candle_index == 51
    assert label.exit_candle_index == 63
    assert label.hurdle_bps == simulation.round_trip_market_cost_bps + Decimal("10")
```

Use the actual label artifact fields exposed by `labels.py`; if entry/exit indexes are not currently persisted, add version-neutral fields only if old serialized labels remain unchanged, otherwise verify via gross-return construction and keep the v0.4 timing receipt separate.

- [ ] **Step 2: Generalize label horizon only where current code assumes three candles**

Replace hard-coded three-held-candle arithmetic with `policy.label_horizon_candles`, preserving the v0.1-v0.3 result when that value is `3`.

Run: `uv run pytest tests/unit/strategy/test_labels.py tests/unit/strategy/test_v0_4_labels.py -v`
Expected: PASS for old labels and new 12h vectors.

- [ ] **Step 3: Write RED split tests for exact calendar folds and boundary protection**

```python
def test_v0_4_plan_has_twelve_complete_development_folds(hourly_dataset: VerifiedDataset) -> None:
    plan = V04DevelopmentQualificationPlan.build(
        hourly_dataset.candles,
        eligible_indices(hourly_dataset),
        CandidatePolicy.locked_v0_4(),
        hourly_dataset.segment_manifest,
    )
    assert tuple(fold.fold_number for fold in plan.folds) == tuple(range(1, 13))
    assert plan.purge_candles == 12
    assert plan.embargo_candles == 12
```

Add tests proving no used label path crosses train/calibration/test boundaries or a verified segment boundary and every fold is 24m expanding train + 6m calibration + 6m forward test + 6m step.

- [ ] **Step 4: Implement `V04DevelopmentQualificationPlan` independently of v0.3**

Use calendar timestamps for fold boundaries and derive `label_exit_offset` from the v0.4 label timing helper. Preserve every complete fold through `2026-08-01T00:00:00Z`; no performance-based omission.

```bash
uv run pytest tests/unit/strategy/test_v0_4_labels.py tests/unit/strategy/test_v0_4_splits.py tests/unit/strategy/test_v0_3_splits.py -v
uv run pyright src/gemini_trading/strategy/labels.py src/gemini_trading/strategy/v0_4_splits.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/labels.py src/gemini_trading/strategy/v0_4_splits.py tests/unit/strategy/test_labels.py tests/unit/strategy/test_v0_4_labels.py tests/unit/strategy/test_v0_4_splits.py
git commit -m "feat: add v0.4 hourly labels and splits"
```

---

### Task 6: Add Regime-Matched Fitting, Calibration, and q75 Threshold Evidence

**Files:**
- Modify backward-compatibly: `src/gemini_trading/strategy/models.py`
- Modify backward-compatibly: `src/gemini_trading/strategy/entry_selectivity.py`
- Create: `src/gemini_trading/strategy/v0_4_predictions.py`
- Modify: `tests/unit/strategy/test_models.py`
- Modify: `tests/unit/strategy/test_entry_selectivity.py`
- Create: `tests/unit/strategy/test_v0_4_predictions.py`
- Modify: `tests/regression/test_strategy_model_determinism.py`

**Interfaces:**
- Extends trainer fitting with explicit feature names/domain indices while default calls remain v0.1-v0.3-equivalent.
- Produces: `V04PredictionContext`
- Produces: `fit_v0_4_prediction_context(...) -> V04PredictionContext`
- Produces v0.4 threshold artifacts for q70/q75/q80 with minimum 160 regime-matched calibration scores.

- [ ] **Step 1: Write RED tests for explicit model domains and old-default equivalence**

```python
def test_trend_v0_4_fit_consumes_only_trending_training_rows() -> None:
    context = fit_v0_4_prediction_context(fold_fixture)
    assert set(context.trend_training_indices) == set(fold_fixture.trending_training_indices)


def test_old_trend_trainer_default_artifact_is_unchanged() -> None:
    first = TrendSpecialistTrainer(CandidatePolicy.locked_v0_3()).fit(matrix, labels, indices)
    second = TrendSpecialistTrainer(CandidatePolicy.locked_v0_3()).fit(matrix, labels, indices)
    assert serialize_model_artifact(first) == serialize_model_artifact(second)
```

Add equivalent mean-reversion tests and assert every selected row is both `RANGING` and stretch-eligible.

- [ ] **Step 2: Refactor trainers to accept explicit feature/domain inputs without changing defaults**

Use optional keyword-only parameters:

```python
def fit(
    self,
    matrix: FeatureMatrix,
    labels: LabelVector,
    training_indices: tuple[int, ...],
    *,
    feature_names: tuple[str, ...] | None = None,
    eligible_indices: tuple[int, ...] | None = None,
) -> ModelArtifact:
    selected = training_indices if eligible_indices is None else eligible_indices
```

When `feature_names is None`, use `FeatureRegistry.locked_v0_1()` exactly as before. For the mean-reversion trainer, keep the legacy stretch filter only on the legacy/default path; the v0.4 caller supplies its already regime+stretch-filtered indices.

- [ ] **Step 3: Extend entry-selectivity primitives with a version-neutral builder, preserving v0.3 bytes**

Do not mutate v0.3 artifact schemas. Add a v0.4-specific artifact/builder that reuses `linear_quantile()`:

```python
@dataclass(frozen=True, slots=True)
class V04EntryThresholdArtifact:
    schema_version: str
    fold_number: int
    specialist: SpecialistKind
    percentile: Decimal
    eligible_indices: tuple[int, ...]
    eligible_scores: tuple[Decimal, ...]
    raw_quantile: Decimal
    effective_threshold: Decimal
    eligible_rows_sha256: str
    score_vector_sha256: str
```

Require q70/q75/q80 only and `len(eligible_indices) >= 160`.

- [ ] **Step 4: Build `V04PredictionContext` from fold-local evidence only**

For each fold:

```python
@dataclass(frozen=True, slots=True)
class V04PredictionContext:
    fold_number: int
    trend_model: ModelArtifact
    mean_reversion_model: ModelArtifact
    trend_platt: PlattArtifact
    mean_reversion_platt: PlattArtifact
    trend_return_map: ExpectedReturnMap
    mean_reversion_return_map: ExpectedReturnMap
    primary_thresholds: Mapping[SpecialistKind, V04EntryThresholdArtifact]
    sensitivity_thresholds: Mapping[tuple[SpecialistKind, Decimal], V04EntryThresholdArtifact]
    predictions: tuple[V04Prediction, ...]
```

Fit/calibrate only on the proper regime domains. Platt minima are 800/160/160. Expected-return maps use only the same regime-matched calibration population. Prediction rows persist tactical index/timestamp, context identity/timestamp, regime, raw score, calibrated probability, expected gross return, and owning specialist eligibility.

- [ ] **Step 5: Verify determinism and commit**

```bash
uv run pytest tests/unit/strategy/test_models.py tests/unit/strategy/test_entry_selectivity.py tests/unit/strategy/test_v0_4_predictions.py tests/regression/test_strategy_model_determinism.py -v
uv run pyright src/gemini_trading/strategy/models.py src/gemini_trading/strategy/entry_selectivity.py src/gemini_trading/strategy/v0_4_predictions.py
uv run ruff check src/gemini_trading/strategy/models.py src/gemini_trading/strategy/entry_selectivity.py src/gemini_trading/strategy/v0_4_predictions.py tests/unit/strategy/test_v0_4_predictions.py
git add src/gemini_trading/strategy/models.py src/gemini_trading/strategy/entry_selectivity.py src/gemini_trading/strategy/v0_4_predictions.py tests/unit/strategy/test_models.py tests/unit/strategy/test_entry_selectivity.py tests/unit/strategy/test_v0_4_predictions.py tests/regression/test_strategy_model_determinism.py
git commit -m "feat: fit v0.4 regime-owned specialists"
```

---

### Task 7: Implement v0.4 Arbitration, Frozen Position Ownership, and Hourly Risk Timing

**Files:**
- Create: `src/gemini_trading/strategy/v0_4_arbitration.py`
- Create: `tests/unit/strategy/test_v0_4_arbitration.py`
- Modify only if a generic schedule primitive is required: `src/gemini_trading/strategy/study_strategy.py`
- Modify corresponding tests if shared schedule code changes: `tests/unit/strategy/test_study_strategy.py`

**Interfaces:**
- Produces: `V04PositionState`
- Produces: `V04DecisionReason`
- Produces: `build_v0_4_candidate_events(context, candles, matrix, label_policy, policy, variant) -> tuple[tuple[int, ScheduledAction], ...]`
- Produces deterministic reason-coded opportunity funnel counters.

- [ ] **Step 1: Write RED ownership and timing tests**

```python
def test_trend_owned_position_never_hands_off_to_mean_reversion() -> None:
    events, trace = build_v0_4_candidate_events(trend_entry_then_ranging_fixture)
    entered = next(item for item in trace if item.action == "enter_long")
    assert entered.owner is SpecialistKind.TREND
    assert all(item.owner in (None, SpecialistKind.TREND) for item in trace[entered.trace_index:])


def test_unstable_context_forces_next_hour_exit() -> None:
    events, trace = build_v0_4_candidate_events(unstable_after_entry_fixture)
    assert any(item.reason == "unstable_context_exit" for item in trace)
```

Add tests for q75 admission, expected-edge veto, 8h minimum ordinary hold, protection override, 72h maximum hold, 8h cooldown, one completed 4h `INDETERMINATE` tolerance, two completed incompatible 4h contexts, and segment-boundary cash reset.

- [ ] **Step 2: Implement a v0.4-specific state machine instead of reinterpreting v0.3 candle counters**

```python
@dataclass(frozen=True, slots=True)
class V04PositionState:
    currently_long: bool
    owner: SpecialistKind | None
    entry_index: int | None
    hold_hours: int
    cooldown_hours: int
    last_context_sha256: str | None
    indeterminate_context_streak: int
    incompatible_context_streak: int
```

Context streaks increment only when the context-bar identity changes; repeated 1h rows joined to the same 4h context do not increment them.

- [ ] **Step 3: Implement primary entry requirements exactly**

Entry requires owner-eligible regime, active probability `>= max(q75, 0.50)`, expected gross return strictly above full modeled hurdle plus the frozen extra edge requirement, cash state, zero cooldown, valid stop inputs, and safe chronology. The non-owning specialist cannot veto or approve.

- [ ] **Step 4: Persist opportunity-funnel reasons without making them gates**

Use closed reason codes:

```python
class V04OpportunityReason(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    REGIME_INELIGIBLE = "regime_ineligible"
    STRETCH_INELIGIBLE = "stretch_ineligible"
    BELOW_Q75 = "below_q75"
    BELOW_EXPECTED_EDGE = "below_expected_edge"
    COOLDOWN = "cooldown"
    RISK_INVALID = "risk_invalid"
    ENTERED = "entered"
```

Persist per-fold counts and exact row identities. No count changes thresholds.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_v0_4_arbitration.py tests/unit/strategy/test_study_strategy.py -v
uv run pyright src/gemini_trading/strategy/v0_4_arbitration.py
uv run ruff check src/gemini_trading/strategy/v0_4_arbitration.py tests/unit/strategy/test_v0_4_arbitration.py
git add src/gemini_trading/strategy/v0_4_arbitration.py tests/unit/strategy/test_v0_4_arbitration.py src/gemini_trading/strategy/study_strategy.py tests/unit/strategy/test_study_strategy.py
git commit -m "feat: add v0.4 hourly arbitration"
```

Omit unchanged shared files from `git add`.

---

### Task 8: Define All v0.4 Study Cases, Baselines, Controls, and Sensitivity Variants

**Files:**
- Create: `src/gemini_trading/strategy/v0_4_cases.py`
- Create: `src/gemini_trading/strategy/v0_4_study_plans.py`
- Create: `tests/unit/strategy/test_v0_4_cases.py`
- Create: `tests/unit/strategy/test_v0_4_study_plans.py`

**Interfaces:**
- Produces a closed required case inventory.
- Produces: `build_v0_4_case_plans(...) -> dict[tuple[StudyPhase, int, str], CasePlan]`

- [ ] **Step 1: Write RED exact-case inventory tests**

```python
def test_v0_4_required_cases_are_closed_and_unique() -> None:
    assert PRIMARY_CASE_ID == "candidate.multi_model.v0_4"
    assert len(REQUIRED_V04_CASE_IDS) == len(set(REQUIRED_V04_CASE_IDS))
    assert "control.shuffled_labels.seed_1799" in REQUIRED_V04_CASE_IDS
    assert "control.delayed_features" in REQUIRED_V04_CASE_IDS
    assert "ablation.no_volume" in REQUIRED_V04_CASE_IDS
    assert "ablation.no_protection" in REQUIRED_V04_CASE_IDS
    assert "ablation.no_percentile_selectivity" in REQUIRED_V04_CASE_IDS
    assert "ablation.no_4h_numeric_context" in REQUIRED_V04_CASE_IDS
```

Also require the five simple baselines (`cash.v1`, `buy_hold.v1`, `ema_20_50.v1`, `donchian_20_10.v1`, `mean_reversion_z24.v1`), 1.5×/2× fixed-decision cost stresses, and exactly ten one-dimensional sensitivity variants.

- [ ] **Step 2: Freeze the ten sensitivity variants**

Use:

```python
SENSITIVITY_VARIANTS = {
    "sensitivity.entry_q70": {"entry_percentile": Decimal("0.70")},
    "sensitivity.entry_q80": {"entry_percentile": Decimal("0.80")},
    "sensitivity.exit_042": {"exit_probability": Decimal("0.42")},
    "sensitivity.exit_048": {"exit_probability": Decimal("0.48")},
    "sensitivity.max_hold_48h": {"maximum_hold_hours": 48},
    "sensitivity.max_hold_96h": {"maximum_hold_hours": 96},
    "sensitivity.stop_20atr": {"initial_stop_atr": Decimal("2.0")},
    "sensitivity.stop_30atr": {"initial_stop_atr": Decimal("3.0")},
    "sensitivity.cooldown_4h": {"cooldown_hours": 4},
    "sensitivity.cooldown_12h": {"cooldown_hours": 12},
}
```

Each variant changes only one declared dimension.

- [ ] **Step 3: Implement controls with identical datasets/timing/costs**

`no-percentile-selectivity` uses fixed `0.50`; `no_4h_numeric_context` keeps the deterministic 4h regime gate but removes the six numeric context inputs from specialist fitting/calibration/inference; delayed features delay tactical and context inputs by one additional 1h decision while preserving strict causality; shuffled labels use seed `1799` only inside training labels.

- [ ] **Step 4: Verify plan completeness**

```bash
uv run pytest tests/unit/strategy/test_v0_4_cases.py tests/unit/strategy/test_v0_4_study_plans.py -v
uv run pyright src/gemini_trading/strategy/v0_4_cases.py src/gemini_trading/strategy/v0_4_study_plans.py
uv run ruff check src/gemini_trading/strategy/v0_4_cases.py src/gemini_trading/strategy/v0_4_study_plans.py tests/unit/strategy/test_v0_4_cases.py tests/unit/strategy/test_v0_4_study_plans.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/v0_4_cases.py src/gemini_trading/strategy/v0_4_study_plans.py tests/unit/strategy/test_v0_4_cases.py tests/unit/strategy/test_v0_4_study_plans.py
git commit -m "feat: define v0.4 qualification cases"
```

---

### Task 9: Implement Closed v0.4 Qualification Gates and 168h Bootstrap

**Files:**
- Create: `src/gemini_trading/strategy/qualification_v0_4.py`
- Modify only if generic bootstrap support is needed: `src/gemini_trading/strategy/evaluation.py`
- Create: `tests/unit/strategy/test_qualification_v0_4.py`
- Modify: `tests/unit/strategy/test_promotion_gates.py`

**Interfaces:**
- Produces: `V04QualificationEvidence`
- Produces: `V04QualificationReport`
- Produces: `evaluate_v0_4_qualification(evidence: V04QualificationEvidence) -> V04QualificationReport`
- Classification set is exactly `QUALIFIED`, `REJECTED`, `INCONCLUSIVE`.

- [ ] **Step 1: Write RED gate inventory and classification tests**

```python
def test_v0_4_gate_inventory_contains_context_ablation() -> None:
    assert "control.no_4h_numeric_context" in V04_QUALIFICATION_GATE_IDS
    assert "development.trade_count" in V04_QUALIFICATION_GATE_IDS
    assert "uncertainty.bootstrap_lower_bound" in V04_QUALIFICATION_GATE_IDS


def test_complete_failed_gate_is_rejected_not_inconclusive() -> None:
    report = evaluate_v0_4_qualification(complete_evidence_with_trade_count(59))
    assert report.classification is QualificationClassification.REJECTED
```

Add missing-evidence tests that classify `INCONCLUSIVE` and all-pass evidence that classifies `QUALIFIED`.

- [ ] **Step 2: Encode development/cost/sensitivity thresholds exactly**

Use Decimal comparisons for:

```python
positive_fold_fraction >= Decimal("0.60")
baseline_rtd_win_fraction >= Decimal("0.60")
profit_concentration <= Decimal("0.50")
completed_trades >= 60
cost_1_5x.net_return > Decimal("0")
cost_1_5x.maximum_drawdown <= Decimal("0.275")
cost_2x.net_return >= Decimal("-0.05")
cost_2x.maximum_drawdown <= Decimal("0.30")
positive_neighbors >= 7
median_neighbor_return > Decimal("0")
max_neighbor_drawdown <= Decimal("0.35")
```

Cost monotonicity remains base >= 1.5× >= 2× aggregate return.

- [ ] **Step 3: Reuse deterministic moving-block bootstrap with exact 168h block length**

Call the existing bootstrap with `block_length=min(168, path_length)`, `replicate_count=1000`, and seed `1788`. Require median paired net-return difference `>0` and p05 `>-0.02`.

- [ ] **Step 4: Encode component-control semantics without turning diagnostics into tuning**

The shuffled-label control must not pass positive economic gates. Delayed features must not materially improve RTD. No-volume, no-protection, no-percentile-selectivity, and no-4h-context each use the existing component-support principle: an ablation may not improve RTD by at least 10% while satisfying the corresponding non-worse/reduced drawdown condition. Persist exact primary/ablation RTD and drawdown values.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification_v0_4.py tests/unit/strategy/test_promotion_gates.py -v
uv run pyright src/gemini_trading/strategy/qualification_v0_4.py src/gemini_trading/strategy/evaluation.py
uv run ruff check src/gemini_trading/strategy/qualification_v0_4.py src/gemini_trading/strategy/evaluation.py tests/unit/strategy/test_qualification_v0_4.py
git add src/gemini_trading/strategy/qualification_v0_4.py src/gemini_trading/strategy/evaluation.py tests/unit/strategy/test_qualification_v0_4.py tests/unit/strategy/test_promotion_gates.py
git commit -m "feat: add v0.4 qualification gates"
```

Omit unchanged `evaluation.py`/test files from `git add`.

---

### Task 10: Execute Qualification and Package Immutable Multi-Timeframe Evidence

**Files:**
- Create: `src/gemini_trading/strategy/qualification_execution_v0_4.py`
- Create: `src/gemini_trading/strategy/qualification_artifacts_v0_4.py`
- Create: `tests/unit/strategy/test_qualification_execution_v0_4.py`
- Create: `tests/unit/strategy/test_qualification_artifacts_v0_4.py`

**Interfaces:**
- Produces: `execute_candidate_v0_4_qualification(...) -> V04QualificationExecution`
- Produces: `build_v0_4_qualification_artifacts(...) -> V04QualificationArtifacts`
- Qualification identity binds source commit, dataset/handoff identities, base policy bytes, v0.4 adjunct policy bytes, split plan, context inventory, features, model/calibration/threshold evidence, study case evidence, diagnostics, gates, bootstrap, and result.

- [ ] **Step 1: Write RED complete-execution evidence tests on a deterministic synthetic fixture**

```python
def test_v0_4_execution_persists_context_and_opportunity_evidence(synthetic_hourly_dataset) -> None:
    result = execute_candidate_v0_4_qualification(
        dataset=synthetic_hourly_dataset,
        handoff=synthetic_handoff,
        simulation=simulation_config,
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit="1" * 40,
    )
    assert result.context_inventory_sha256
    assert result.opportunity_diagnostics
    assert result.report.classification in QualificationClassification
```

Use a fixture large enough to exercise the pipeline mechanics; qualification outcome itself is not required to be profitable in unit tests.

- [ ] **Step 2: Execute every required fold/case through the deterministic simulator**

For each of 12 folds, build v0.4 prediction context once per required model variant, derive schedules, run primary/baselines/controls/stresses/sensitivity through the existing research engine, and collect `FoldEvaluation`, component metrics, and opportunity-funnel evidence. Never execute network/provider calls in qualification.

- [ ] **Step 3: Define immutable artifact files and canonical inventory**

At minimum write canonical evidence for:

```text
qualification-result.json
qualification-gates.jsonl
split-plan.json
context-bars.jsonl
context-joins.jsonl
feature-identities.json
models.jsonl
calibration.jsonl
entry-thresholds.jsonl
predictions.jsonl
opportunity-diagnostics.jsonl
case-evidence.jsonl
cost-stress.json
sensitivity.jsonl
bootstrap.json
limitations.json
```

Every file gets size/SHA-256 inventory and one inventory-root SHA-256. `limitations.json` must contain `research_only=true`, `execution_authorized=false`, `future_profitability_not_established=true`, and `prospective_final_accessed=false`.

- [ ] **Step 4: Assert terminal semantics in artifact construction**

A complete valid failed gate produces `REJECTED`; incomplete evidence produces `INCONCLUSIVE`; artifacts never set `promotable=true` or `execution_authorized=true`. Only `QUALIFIED` may later be consumed by the seal store.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification_execution_v0_4.py tests/unit/strategy/test_qualification_artifacts_v0_4.py -v
uv run pyright src/gemini_trading/strategy/qualification_execution_v0_4.py src/gemini_trading/strategy/qualification_artifacts_v0_4.py
uv run ruff check src/gemini_trading/strategy/qualification_execution_v0_4.py src/gemini_trading/strategy/qualification_artifacts_v0_4.py tests/unit/strategy/test_qualification_execution_v0_4.py tests/unit/strategy/test_qualification_artifacts_v0_4.py
git add src/gemini_trading/strategy/qualification_execution_v0_4.py src/gemini_trading/strategy/qualification_artifacts_v0_4.py tests/unit/strategy/test_qualification_execution_v0_4.py tests/unit/strategy/test_qualification_artifacts_v0_4.py
git commit -m "feat: execute and package v0.4 qualification"
```

---

### Task 11: Add Provider-Free Replay and Independent v0.4 Verification

**Files:**
- Create: `src/gemini_trading/strategy/qualification_replay_v0_4.py`
- Create: `src/gemini_trading/strategy/qualification_verification_v0_4.py`
- Create: `tests/unit/strategy/test_qualification_replay_v0_4.py`
- Create: `tests/unit/strategy/test_qualification_verification_v0_4.py`

**Interfaces:**
- Produces: `replay_candidate_v0_4_qualification(...) -> V04QualificationArtifacts`
- Produces: `verify_candidate_v0_4_qualification(...) -> V04QualificationArtifacts`

- [ ] **Step 1: Write RED tamper and replay tests**

```python
def test_v0_4_replay_reproduces_exact_result(valid_bundle) -> None:
    replayed = replay_candidate_v0_4_qualification(valid_bundle.root, valid_bundle.qualification_id)
    assert replayed.qualification_id == valid_bundle.qualification_id
    assert replayed.inventory_root_sha256 == valid_bundle.inventory_root_sha256
    assert replayed.classification == valid_bundle.classification


def test_v0_4_verifier_rejects_context_join_tamper(valid_bundle) -> None:
    tamper_jsonl(valid_bundle.root / "context-joins.jsonl")
    with pytest.raises(StudyArtifactError, match="inventory"):
        verify_candidate_v0_4_qualification(valid_bundle.root, valid_bundle.qualification_id)
```

Also tamper policy bytes, threshold score vector, model artifact, bootstrap, gate row, and source commit.

- [ ] **Step 2: Recompute all content identities without provider/network access**

Verification must reconstruct context bars/joins from bundled canonical 1h evidence, recompute feature/model/calibration/threshold identities, rebuild gate decisions from stored case evidence, recompute qualification ID/inventory root, and compare byte-for-byte where the contract requires canonical bytes.

- [ ] **Step 3: Prove no provider import/call is required for replay**

Use a test that monkeypatches provider constructors to raise immediately and still verifies the bundle successfully.

```python
def forbidden_provider(*args: object, **kwargs: object) -> Never:
    raise AssertionError("provider access is forbidden during qualification replay")
```

- [ ] **Step 4: Verify old replay suites remain green**

```bash
uv run pytest tests/unit/strategy/test_qualification_replay_v0_4.py tests/unit/strategy/test_qualification_verification_v0_4.py tests/unit/strategy/test_qualification_verification_v0_3.py -v
uv run pyright src/gemini_trading/strategy/qualification_replay_v0_4.py src/gemini_trading/strategy/qualification_verification_v0_4.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/qualification_replay_v0_4.py src/gemini_trading/strategy/qualification_verification_v0_4.py tests/unit/strategy/test_qualification_replay_v0_4.py tests/unit/strategy/test_qualification_verification_v0_4.py
git commit -m "feat: verify v0.4 qualification provider-free"
```

---

### Task 12: Add v0.4 CLI and Manual Governance Workflows

**Files:**
- Create: `src/gemini_trading/cli/candidate_v0_4.py`
- Modify: `src/gemini_trading/cli/main.py`
- Create: `tests/integration/test_candidate_v0_4_cli.py`
- Create: `.github/workflows/candidate-v0.4-stage1.yml`
- Create: `.github/workflows/candidate-v0.4-qualification.yml`
- Create: `tests/acceptance/test_candidate_v0_4_workflow.py`

**Interfaces:**
- CLI commands: `dataset-v0-4-ingest`, `strategy-v0-4-handoff`, `strategy-v0-4-qualify`, `strategy-v0-4-verify-qualification`, `strategy-v0-4-create-prospective-seal`.
- Workflows are manual `workflow_dispatch` only.
- Qualification workflow requires an exact owner-authored Issue #73 marker: `<!-- candidate-v0.4-dataset-approved:<SOURCE_COMMIT>:<STAGE1_GITHUB_RUN_ID>:<DATASET_ID> -->`.

- [ ] **Step 1: Write RED CLI boundary tests**

```python
def test_v0_4_qualify_cli_is_research_only(cli_runner) -> None:
    payload = cli_runner("research", "strategy-v0-4-qualify", valid_args)
    assert payload["boundary"] == "RESEARCH_ONLY"
    assert payload["execution_authorized"] is False
    assert payload["promotable"] is False
```

Assert exact v0.4 config required, Stage 1 handoff path cannot escape output root, source commit must be clean/exact, and `create-prospective-seal` rejects non-`QUALIFIED` evidence.

- [ ] **Step 2: Implement CLI dispatch by mirroring v0.3 safety structure with v0.4 modules**

`candidate_v0_4.py` must use public Binance only in `dataset-v0-4-ingest`; qualify/verify/seal are provider-free. Every returned payload is wrapped by the same research-only envelope.

- [ ] **Step 3: Add a Stage 1 workflow that cannot run on arbitrary source state**

Workflow requirements:

```yaml
on:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: candidate-v0-4-stage1
  cancel-in-progress: false
```

Checkout the exact main commit, require `GITHUB_REF_NAME=main`, require clean source, ingest exact BTCUSDT 1h `[2018-01-01,2026-08-01)` public history, independently verify canonical data/handoff/context-derivability, assert worktree clean, and upload immutable `candidate-v0.4-stage1-<sha>-<run_id>` artifact. Do not run this workflow during the implementation PR.

- [ ] **Step 4: Add qualification workflow with Issue #73 exact approval gate**

Use manual inputs `source_commit`, `dataset_run_id`, `dataset_artifact_name`, `dataset_id`. Require merged-main identity, clean source, exact owner-authored Issue #73 marker, download the exact Stage 1 artifact, verify 1h handoff/cutoff, run strict qualification, provider-free verification, build portable bundle, and upload `candidate-v0.4-qualification-${{ github.run_id }}` for 90 days.

- [ ] **Step 5: Acceptance-test workflow safety and commit**

```bash
uv run pytest tests/integration/test_candidate_v0_4_cli.py tests/acceptance/test_candidate_v0_4_workflow.py -v
uv run pyright src/gemini_trading/cli/candidate_v0_4.py src/gemini_trading/cli/main.py
uv run ruff check src/gemini_trading/cli/candidate_v0_4.py src/gemini_trading/cli/main.py tests/integration/test_candidate_v0_4_cli.py tests/acceptance/test_candidate_v0_4_workflow.py
git add src/gemini_trading/cli/candidate_v0_4.py src/gemini_trading/cli/main.py tests/integration/test_candidate_v0_4_cli.py .github/workflows/candidate-v0.4-stage1.yml .github/workflows/candidate-v0.4-qualification.yml tests/acceptance/test_candidate_v0_4_workflow.py
git commit -m "feat: add governed v0.4 research workflows"
```

---

### Task 13: Add the v0.4 Prospective Seal Without Exposing Prospective Performance

**Files:**
- Create: `src/gemini_trading/strategy/prospective_seal_v0_4.py`
- Create: `tests/unit/strategy/test_prospective_seal_v0_4.py`
- Modify CLI integration coverage: `tests/integration/test_candidate_v0_4_cli.py`

**Interfaces:**
- Produces: `V04ProspectiveFinalSeal`
- Produces: `V04LocalProspectiveFinalSealStore.create(artifacts: V04QualificationArtifacts) -> V04ProspectiveFinalSeal`

- [ ] **Step 1: Write RED seal eligibility and calendar tests**

```python
def test_v0_4_seal_requires_verified_qualified_bundle(verified_rejected_bundle, tmp_path) -> None:
    with pytest.raises(StudyArtifactError, match="QUALIFIED"):
        V04LocalProspectiveFinalSealStore(tmp_path).create(verified_rejected_bundle)


def test_v0_4_final_window_is_exactly_eighteen_calendar_months(qualified_bundle, tmp_path) -> None:
    seal = V04LocalProspectiveFinalSealStore(tmp_path).create(qualified_bundle)
    assert seal.final_start.day == 1
    assert seal.final_start.hour == 0
    assert add_months(seal.final_start, 18) == seal.final_end
```

- [ ] **Step 2: Bind the complete frozen identity into the seal**

The seal includes exact source commit, dataset ID/handoff inventory root, qualification ID/inventory root, base policy digest, multi-timeframe policy digest, context inventory digest, split identity, model/calibration/threshold identities, final start/end, bridge start/end, `research_only=true`, and `execution_authorized=false`.

- [ ] **Step 3: Enforce bridge/final access restrictions**

No function in this task may compute strategy predictions, decisions, P&L, promotion gates, or interim final metrics. The seal is metadata only. Raw future ingestion integrity remains outside strategy outcome materialization.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_prospective_seal_v0_4.py tests/integration/test_candidate_v0_4_cli.py -v
uv run pyright src/gemini_trading/strategy/prospective_seal_v0_4.py
uv run ruff check src/gemini_trading/strategy/prospective_seal_v0_4.py tests/unit/strategy/test_prospective_seal_v0_4.py
git add src/gemini_trading/strategy/prospective_seal_v0_4.py tests/unit/strategy/test_prospective_seal_v0_4.py tests/integration/test_candidate_v0_4_cli.py
git commit -m "feat: add v0.4 prospective seal"
```

---

### Task 14: Add Operations Documentation, Full Regression Proof, and Merge Readiness

**Files:**
- Create: `docs/operations/candidate-multi-model-strategy-v0-4.md`
- Create: `docs/operations/candidate-multi-model-strategy-v0-4-step-verification.md`
- Modify only where command discovery is documented: `README.md`
- No strategy/economic code changes are permitted in this task.

**Interfaces:**
- Produces operator instructions for Stage 1, exact Issue #73 approval marker, qualification, independent verification, terminal semantics, and prospective seal.
- Produces one final exact-head verification record before merge.

- [ ] **Step 1: Document the governed operator sequence**

The operations doc must state this exact order:

```text
1. Merge protected v0.4 implementation only after exact-head CI is green.
2. Verify merged-main CI on the exact merge SHA.
3. Manually dispatch Candidate v0.4 Stage 1 once from exact merged main.
4. Independently verify the Stage 1 artifact and 1h/context integrity.
5. Add the exact owner-authored Issue #73 dataset approval marker.
6. Manually dispatch Candidate v0.4 Development Qualification once with exact IDs.
7. Independently verify the qualification artifact provider-free.
8. If REJECTED: stop v0.4 permanently; any redesign is v0.5.
9. If INCONCLUSIVE: repair evidence/infrastructure only, preserving financial specification.
10. If QUALIFIED: create the prospective seal; do not expose interim prospective performance.
```

- [ ] **Step 2: Document exact commands and safety outputs**

Include the five `strategy-v0-4-*`/`dataset-v0-4-ingest` commands, required arguments, expected `RESEARCH_ONLY`/`execution_authorized=false` envelope, artifact layouts, approval-marker format, and the fact that ChatGPT/GitHub tooling cannot substitute reruns for a new governed `workflow_dispatch`.

- [ ] **Step 3: Run the focused v0.4 suite before the expensive full suite**

```bash
uv run pytest \
  tests/unit/strategy/test_v0_4_policy.py \
  tests/unit/strategy/test_v0_4_stage1.py \
  tests/unit/strategy/test_v0_4_context.py \
  tests/unit/strategy/test_v0_4_features.py \
  tests/unit/strategy/test_v0_4_labels.py \
  tests/unit/strategy/test_v0_4_splits.py \
  tests/unit/strategy/test_v0_4_predictions.py \
  tests/unit/strategy/test_v0_4_arbitration.py \
  tests/unit/strategy/test_v0_4_cases.py \
  tests/unit/strategy/test_v0_4_study_plans.py \
  tests/unit/strategy/test_qualification_v0_4.py \
  tests/unit/strategy/test_qualification_execution_v0_4.py \
  tests/unit/strategy/test_qualification_artifacts_v0_4.py \
  tests/unit/strategy/test_qualification_replay_v0_4.py \
  tests/unit/strategy/test_qualification_verification_v0_4.py \
  tests/unit/strategy/test_prospective_seal_v0_4.py \
  tests/integration/test_candidate_v0_4_cli.py \
  tests/acceptance/test_candidate_v0_4_workflow.py -v
```

Expected: all PASS; no network access except tests explicitly marked `live_api`, which are not run.

- [ ] **Step 4: Run the complete repository gate exactly as CI does**

```bash
uv sync --all-groups --frozen
uv run ruff format --check --diff .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines())"
uv run pre-commit run detect-secrets --all-files
```

Then review `git diff --check`, `git status --short`, and the exact diff against the implementation base. GitHub CI must additionally pass Gitleaks on the exact PR head.

- [ ] **Step 5: Commit documentation and stop before any Stage 1 dispatch**

```bash
git add docs/operations/candidate-multi-model-strategy-v0-4.md docs/operations/candidate-multi-model-strategy-v0-4-step-verification.md README.md
git commit -m "docs: add Candidate v0.4 operator runbook"
```

Create/review the implementation PR, require exact-head CI, and merge only through the repository's protected process. Do not ingest fresh v0.4 data or dispatch qualification inside this implementation cycle.

---

## Post-Merge Evidence Sequence — Not Part of Code Implementation

After the implementation PR is merged and exact merged-main CI passes, perform the evidence sequence once under Issue #73:

1. Dispatch `.github/workflows/candidate-v0.4-stage1.yml` manually on exact merged main.
2. Verify the Stage 1 artifact independently: ZIP digest, complete inventory, 1h window/scope, closure/exclusion/segment evidence, deterministic 4h derivability, no post-cutoff rows, and handoff inventory root.
3. Add exactly one current-source approval marker: `<!-- candidate-v0.4-dataset-approved:<SOURCE_COMMIT>:<STAGE1_GITHUB_RUN_ID>:<DATASET_ID> -->`.
4. Dispatch `.github/workflows/candidate-v0.4-qualification.yml` once with exact source/run/artifact/dataset IDs.
5. Download and independently verify the complete qualification artifact and terminal classification.
6. Preserve `REJECTED` as terminal; classify only genuine evidence/infrastructure defects as `INCONCLUSIVE`; create a prospective seal only for verified `QUALIFIED`.

No result from this sequence authorizes paper, demo, live, or real-capital execution.
