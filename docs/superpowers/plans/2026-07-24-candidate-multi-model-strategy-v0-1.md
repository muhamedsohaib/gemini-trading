# Candidate Multi-Model Strategy v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved research-only BTC/USDT 4-hour multi-model candidate, including point-in-time features, cost-aware labels, sealed chronological evaluation, deterministic specialists, long/cash arbitration, robustness evidence, provider-free replay, and independent verification.

**Architecture:** Add a bounded `gemini_trading.strategy` package above the verified Market Data Core and deterministic `BacktestEngine`. Training produces immutable model artifacts and a precomputed decision schedule; only the existing engine may convert strategy intents into simulated orders, fills, accounting, and economic evidence. Model artifacts use canonical JSON and hexadecimal IEEE-754 values rather than pickle or joblib.

**Tech Stack:** Python 3.12, `Decimal`, NumPy, scikit-learn 1.9, threadpoolctl, pytest, Hypothesis, Ruff, strict Pyright, canonical JSON/JSONL, immutable local storage, and the existing deterministic research engine.

## Global Constraints

- Promotion level remains `RESEARCH_ONLY`; `production_eligible` and CLI `promotable` remain false for this milestone.
- Instrument is `BTC/USDT` Binance Spot; timeframe is completed `4h`; positioning is long or cash only.
- Consume only verified canonical `candle-dataset-v1` OHLCV data.
- Require at least seven years of continuous verified history.
- Use completed-candle features and official next-candle execution only.
- Use the existing simulator for fees, spread, slippage, latency, precision, minimums, liquidity participation, fills, and accounting.
- Trend specialist: elastic-net logistic regression, `C=1.0`, `l1_ratio=0.5`, seed `1701`.
- Mean-reversion specialist: gradient boosting, 150 estimators, depth 2, learning rate `0.03`, minimum leaf 100, no subsampling, seed `1702`.
- Platt calibration is fold-local and requires at least 200 observations, 40 positive labels, and 40 negative labels.
- Final untouched test is the last 18 calendar months and is evaluated once for Candidate v0.1.
- Development uses expanding windows: 24-month minimum training, 6-month calibration, 6-month forward test, 6-month step, 3-candle purge, 3-candle embargo, at least five folds.
- No credentials, private endpoints, broker/demo/live execution, leverage, shorting, portfolio allocation, or real-capital authority.
- Preserve failed folds, failed controls, and rejected candidates as immutable evidence.
- Every task uses TDD and ends in an independently reviewable commit.

---

## File Map

Create:

```text
src/gemini_trading/strategy/
  __init__.py
  errors.py
  contracts.py
  policy.py
  identity.py
  features.py
  labels.py
  splits.py
  models.py
  calibration.py
  regimes.py
  arbitration.py
  candidate.py
  baselines.py
  evaluation.py
  study.py
  artifacts.py
  replay.py
  verification.py
```

Modify only required integration points:

```text
pyproject.toml
uv.lock
src/gemini_trading/cli/main.py
src/gemini_trading/cli/research.py
src/gemini_trading/research/errors.py
src/gemini_trading/research/artifacts.py
src/gemini_trading/research/metrics.py
src/gemini_trading/research/replay.py
src/gemini_trading/research/verification.py
README.md
```

---

### Task 1: Locked Policy, Dependencies, and Contracts

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/gemini_trading/research/errors.py`
- Create: `src/gemini_trading/strategy/{__init__,errors,contracts,policy}.py`
- Test: `tests/unit/strategy/test_policy.py`, `test_contracts.py`, `test_errors.py`

**Interfaces:**
- Produces: `CandidatePolicy.locked_v0_1() -> CandidatePolicy`
- Produces: `serialize_candidate_policy(policy) -> bytes`
- Produces: `RegimeState`, `SpecialistKind`, `StrategyAction`, `IndexWindow`, `SpecialistPrediction`, `GateResult`

- [ ] **Step 1: Add dependencies and lock them**

```toml
dependencies = [
  "numpy>=2.2,<3",
  "scikit-learn==1.9.0",
  "threadpoolctl>=3.6,<4",
]
```

Run:

```bash
uv lock
uv sync --all-groups --frozen
```

Expected: dependency resolution succeeds under Python 3.12.

- [ ] **Step 2: Write failing policy tests**

```python
def test_locked_policy_matches_spec() -> None:
    policy = CandidatePolicy.locked_v0_1()
    assert policy.strategy_id == "candidate.multi_model.v0_1"
    assert policy.instrument_symbol == "BTCUSDT"
    assert policy.timeframe == "4h"
    assert policy.minimum_history_years == 7
    assert policy.final_test_months == 18
    assert policy.label_horizon_candles == 3
    assert policy.entry_probability == Decimal("0.62")
    assert policy.exit_probability == Decimal("0.45")
    assert policy.maximum_hold_candles == 18
    assert serialize_candidate_policy(policy) == serialize_candidate_policy(
        CandidatePolicy.locked_v0_1()
    )
```

Run `uv run pytest tests/unit/strategy/test_policy.py -v`; expect import failure.

- [ ] **Step 3: Implement stable enums and dataclasses**

```python
class RegimeState(StrEnum):
    UNSTABLE = "unstable"
    TRENDING = "trending"
    RANGING = "ranging"
    INDETERMINATE = "indeterminate"

class SpecialistKind(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"

class StrategyAction(StrEnum):
    ENTER_LONG = "enter_long"
    REMAIN_LONG = "remain_long"
    EXIT_TO_CASH = "exit_to_cash"
    REMAIN_IN_CASH = "remain_in_cash"

@dataclass(frozen=True, slots=True)
class IndexWindow:
    start_inclusive: int
    end_exclusive: int
```

Validate windows, finite probabilities, unique IDs, and ordered reason codes.

- [ ] **Step 4: Add safe error taxonomy**

Add `StrategyStudyError`, `InsufficientHistoryError`, `PointInTimeViolationError`, `SplitBoundaryError`, `LabelLeakageError`, `InsufficientCalibrationError`, `ModelDeterminismError`, `ProbabilityRangeError`, `FinalTestSealError`, `StudyArtifactError`, `StudyReplayMismatchError`, and `StudyVerificationError` as `ResearchError` subclasses.

- [ ] **Step 5: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_policy.py tests/unit/strategy/test_contracts.py tests/unit/strategy/test_errors.py -v
uv run ruff check src tests
uv run pyright
git add pyproject.toml uv.lock src/gemini_trading/strategy src/gemini_trading/research/errors.py tests/unit/strategy
git commit -m "feat: define locked candidate strategy policy"
```

---

### Task 2: Content-Addressed Study Identities

**Files:**
- Create: `src/gemini_trading/strategy/identity.py`
- Test: `tests/unit/strategy/test_identity.py`, `tests/property/strategy/test_strategy_identity.py`

**Interfaces:**
- Produces: `component_id(schema_version, payload) -> str`
- Produces: `StrategyStudyManifest`, `study_id()`, `serialize_study_manifest()`

- [ ] **Step 1: Write RED tests**

```python
def test_study_identity_changes_at_every_boundary() -> None:
    manifest = example_study_manifest()
    assert study_id(manifest) == study_id(manifest)
    assert study_id(replace(manifest, dataset_id="1" * 64)) != study_id(manifest)
    assert study_id(replace(manifest, code_commit="1" * 40)) != study_id(manifest)
    assert study_id(replace(manifest, policy_id="2" * 64)) != study_id(manifest)
```

- [ ] **Step 2: Implement exact manifest**

```python
@dataclass(frozen=True, slots=True)
class StrategyStudyManifest:
    schema_version: str
    dataset_id: str
    canonical_sha256: str
    code_commit: str
    policy_id: str
    simulation_config_id: str
    feature_registry_id: str
    label_policy_id: str
    split_plan_id: str
    random_seed_policy_id: str
    initial_cash: Decimal
```

Derive all IDs with `sha256(canonical_json_bytes(...))`. Validate SHA-256 and Git commit formats like `ExperimentManifest`.

- [ ] **Step 3: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_identity.py tests/property/strategy/test_strategy_identity.py -v
uv run pyright
git add src/gemini_trading/strategy/identity.py tests/unit/strategy/test_identity.py tests/property/strategy/test_strategy_identity.py
git commit -m "feat: add strategy study identities"
```

---

### Task 3: Point-in-Time Feature Registry

**Files:**
- Create: `src/gemini_trading/strategy/features.py`, `tests/strategy_fixture_support.py`
- Test: `tests/unit/strategy/test_features.py`, `tests/property/strategy/test_feature_point_in_time.py`, `tests/regression/test_strategy_feature_alignment.py`

**Interfaces:**
- Produces: `FeatureDefinition`, `FeatureRow`, `FeatureMatrix`
- Produces: `FeatureRegistry.locked_v0_1()` and `.compute(candles)`

- [ ] **Step 1: Add exact BTC candle fixtures**

```python
def btc_candle(index: int, *, close: str, volume: str = "100") -> Candle:
    opened = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=4 * index)
    value = Decimal(close)
    return Candle(
        instrument=Instrument("BTCUSDT", "BTC", "USDT"),
        timeframe=Timeframe.H4,
        open_time=opened,
        close_time=opened + timedelta(hours=4) - timedelta(milliseconds=1),
        open=value - Decimal("1"), high=value + Decimal("2"),
        low=value - Decimal("2"), close=value, volume=Decimal(volume),
        completed=True, source_provider="binance_spot",
    )
```

- [ ] **Step 2: Write RED feature and future-isolation tests**

```python
def test_first_eligible_row_is_42() -> None:
    matrix = FeatureRegistry.locked_v0_1().compute(rising_candles(50))
    assert matrix.rows[0].candle_index == 42
    assert all(value.is_finite() for value in matrix.rows[0].values)

def test_future_change_does_not_change_prior_row() -> None:
    candles = rising_candles(60)
    first = FeatureRegistry.locked_v0_1().compute(candles)
    changed = (*candles[:-1], replace(candles[-1], close=Decimal("999999"), high=Decimal("999999")))
    second = FeatureRegistry.locked_v0_1().compute(changed)
    assert first.row_for(58) == second.row_for(58)
```

- [ ] **Step 3: Implement approved feature registry**

Use local `Context(prec=34, rounding=ROUND_HALF_EVEN)`. Implement every feature in design section 6: returns/momentum, EMA trend, volatility/range, candle structure, mean-reversion state, and volume. Use trailing windows only. Zero denominators make the row ineligible; no silent imputation.

Expose exact `TREND_FEATURE_NAMES`, `MEAN_REVERSION_FEATURE_NAMES`, and `REGIME_FEATURE_NAMES` tuples and validate them as registry subsets.

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_features.py tests/property/strategy/test_feature_point_in_time.py tests/regression/test_strategy_feature_alignment.py -v
uv run pyright
git add src/gemini_trading/strategy/features.py tests/strategy_fixture_support.py tests/unit/strategy/test_features.py tests/property/strategy/test_feature_point_in_time.py tests/regression/test_strategy_feature_alignment.py
git commit -m "feat: add point-in-time strategy features"
```

---

### Task 4: Cost-Aware Labels and Sealed Splits

**Files:**
- Create: `src/gemini_trading/strategy/labels.py`, `splits.py`
- Test: `tests/unit/strategy/test_labels.py`, `test_splits.py`, `tests/property/strategy/test_label_boundaries.py`, `tests/regression/test_strategy_label_leakage.py`

**Interfaces:**
- Produces: `LabelObservation`, `LabelVector`, `LabelPolicy.locked_v0_1(config)`
- Produces: `ChronologicalSplitPlan`, `WalkForwardFold`

- [ ] **Step 1: Write RED label test**

```python
def test_label_uses_next_open_and_three_held_candles() -> None:
    labels = LabelPolicy.locked_v0_1(base_simulation()).build(
        exact_label_fixture(), eligible_indices=(42,)
    )
    item = labels.for_index(42)
    assert item.entry_candle_index == 43
    assert item.exit_candle_index == 46
    assert item.hurdle_bps == Decimal("60")
    assert item.positive is (item.net_return > Decimal("0.006"))
```

Use existing `market_fill_costs` and `round_fill_price` in expected calculations.

- [ ] **Step 2: Implement labels**

For a unit quantity: enter at `t+1.open`, exit at `t+4.open`, apply taker fee/spread/slippage on both sides, adverse tick rounding, and store gross return, net return, hurdle, fill prices, indices, and class. Hurdle is `2 * (fee_bps + half_spread_bps + slippage_bps) + 10`.

- [ ] **Step 3: Write RED split tests**

```python
def test_last_eighteen_months_are_sealed() -> None:
    plan = ChronologicalSplitPlan.build(candles, eligible_indices, CandidatePolicy.locked_v0_1())
    assert plan.final_test_months == 18
    assert len(plan.folds) >= 5
    assert all(fold.purge_candles == 3 and fold.embargo_candles == 3 for fold in plan.folds)
```

Assert no `index + 4` label window crosses training/calibration/test boundaries.

- [ ] **Step 4: Implement calendar splits**

Use deterministic UTC calendar-month arithmetic. Build 24-month minimum train, 6-month calibration, 6-month forward test, 6-month step, 3-candle purge/embargo, and final 18-month test. Raise explicit errors instead of shortening windows.

- [ ] **Step 5: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_labels.py tests/unit/strategy/test_splits.py tests/property/strategy/test_label_boundaries.py tests/regression/test_strategy_label_leakage.py -v
uv run pyright
git add src/gemini_trading/strategy/labels.py src/gemini_trading/strategy/splits.py tests/unit/strategy/test_labels.py tests/unit/strategy/test_splits.py tests/property/strategy/test_label_boundaries.py tests/regression/test_strategy_label_leakage.py
git commit -m "feat: add cost-aware labels and sealed splits"
```

---

### Task 5: Deterministic Specialist Models

**Files:**
- Create: `src/gemini_trading/strategy/models.py`
- Test: `tests/unit/strategy/test_models.py`, `tests/property/strategy/test_model_serialization.py`, `tests/regression/test_strategy_model_determinism.py`

**Interfaces:**
- Produces: `LinearModelArtifact`, `BoostedTreeArtifact`, `TreeNodeArtifact`
- Produces: `TrendSpecialistTrainer.fit()`, `MeanReversionSpecialistTrainer.fit()`
- Produces: `predict_raw()`, `serialize_model_artifact()`, `parse_model_artifact()`

- [ ] **Step 1: Write RED byte-determinism tests**

```python
def test_trend_fit_is_byte_deterministic() -> None:
    trainer = TrendSpecialistTrainer(CandidatePolicy.locked_v0_1())
    first = trainer.fit(deterministic_training_fixture())
    second = trainer.fit(deterministic_training_fixture())
    assert serialize_model_artifact(first) == serialize_model_artifact(second)
```

- [ ] **Step 2: Implement fold-local conversion/scaling**

Convert `Decimal` to `np.float64` only after selecting the fold. Fit means/scales on training rows only, reject zero-variance columns, store all floats with `float.hex()`, and use `threadpool_limits(1)` around fits.

- [ ] **Step 3: Fit locked trend model**

```python
LogisticRegression(
    penalty="elasticnet", solver="saga", C=1.0, l1_ratio=0.5,
    max_iter=5000, tol=1e-8, fit_intercept=True,
    class_weight=class_weight, random_state=1701, n_jobs=1,
)
```

Reject non-convergence. Use inverse-frequency class weights only when the training positive fraction is outside `[0.30, 0.70]`.

- [ ] **Step 4: Fit locked mean-reversion model**

```python
GradientBoostingClassifier(
    loss="log_loss", learning_rate=0.03, n_estimators=150,
    subsample=1.0, max_depth=2, min_samples_leaf=100,
    max_features=None, random_state=1702,
)
```

Train only rows satisfying z-score 24 `<= -0.75` or drawdown 24 `>= 0.02`.

- [ ] **Step 5: Serialize without executable objects**

Store feature names, scaling, coefficients/intercept, boosted initial score, and every tree node’s children, feature index, threshold, and value as canonical JSON using hexadecimal floats. Implement custom inference and assert it matches scikit-learn raw scores within `1e-12`.

- [ ] **Step 6: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_models.py tests/property/strategy/test_model_serialization.py tests/regression/test_strategy_model_determinism.py -v
uv run pyright
git add src/gemini_trading/strategy/models.py tests/unit/strategy/test_models.py tests/property/strategy/test_model_serialization.py tests/regression/test_strategy_model_determinism.py
git commit -m "feat: add deterministic specialist models"
```

---

### Task 6: Platt Calibration and Return Mapping

**Files:**
- Create: `src/gemini_trading/strategy/calibration.py`
- Test: `tests/unit/strategy/test_calibration.py`, `tests/property/strategy/test_probability_bounds.py`

**Interfaces:**
- Produces: `PlattArtifact`, `ExpectedReturnMap`, calibration metrics

- [ ] **Step 1: Write RED minimum-class and bounded-probability tests**

```python
def test_calibration_requires_class_counts() -> None:
    with pytest.raises(InsufficientCalibrationError):
        fit_platt_calibrator([0.0] * 200, [False] * 180 + [True] * 20)

def test_probability_is_bounded() -> None:
    artifact = fit_platt_calibrator(scores(), labels())
    assert all(Decimal("0") <= apply_platt(artifact, x) <= Decimal("1") for x in (-1e9, 0.0, 1e9))
```

- [ ] **Step 2: Implement deterministic Platt scaling**

Use fixed Newton-Raphson: 100 iterations, diagonal stabilizer `1e-12`, delta tolerance `1e-12`, stable sigmoid branches, and explicit singular/non-convergence errors. Store coefficients with `float.hex()`.

- [ ] **Step 3: Implement expected-gross-return mapping**

Fit OLS `gross_return = intercept + slope * calibrated_probability` on calibration rows. Reject zero probability variance and clamp inference probabilities to the observed calibration range.

- [ ] **Step 4: Add Brier, log loss, and ten-bin ECE; test and commit**

```bash
uv run pytest tests/unit/strategy/test_calibration.py tests/property/strategy/test_probability_bounds.py -v
uv run pyright
git add src/gemini_trading/strategy/calibration.py tests/unit/strategy/test_calibration.py tests/property/strategy/test_probability_bounds.py
git commit -m "feat: calibrate specialist probabilities"
```

---

### Task 7: Regime Classification

**Files:**
- Create: `src/gemini_trading/strategy/regimes.py`
- Test: `tests/unit/strategy/test_regimes.py`, `tests/property/strategy/test_regime_determinism.py`

**Interfaces:**
- Produces: `RegimeObservation`, `RegimeClassifier.classify()`

- [ ] **Step 1: Write exact rule-order tests**

Test: unstable at volatility ratio `>=1.75` or range ratio `>=2.5`; trending at strength `>=1.0`, volatility `<1.5`, sign streak `>=3`; ranging at strength `<=0.5`, volatility `<=1.25`; otherwise indeterminate.

- [ ] **Step 2: Implement classifier with input evidence and reason code**

Persist trend strength, volatility ratio, range ratio, sign streak, selected state, and ordered reason code.

- [ ] **Step 3: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_regimes.py tests/property/strategy/test_regime_determinism.py -v
uv run pyright
git add src/gemini_trading/strategy/regimes.py tests/unit/strategy/test_regimes.py tests/property/strategy/test_regime_determinism.py
git commit -m "feat: classify deterministic market regimes"
```

---

### Task 8: Arbitration and Strategy Adapter

**Files:**
- Create: `src/gemini_trading/strategy/arbitration.py`, `candidate.py`
- Test: `tests/unit/strategy/test_arbitration.py`, `test_candidate_strategy.py`, `tests/property/strategy/test_candidate_order_safety.py`, `tests/regression/test_candidate_next_candle_only.py`

**Interfaces:**
- Produces: `ArbitrationInput`, `ArbitrationDecision`, `MultiModelArbiter`
- Produces: `CandidateDecisionSchedule`, `CandidateMultiModelStrategy`

- [ ] **Step 1: Write RED tests for entry, disagreement, unstable abstention, hold, exits, stop, maximum hold, cooldown, and no pyramiding**

```python
def test_trending_entry_requires_locked_thresholds() -> None:
    decision = arbiter().decide(flat_input(
        regime=RegimeState.TRENDING,
        trend_probability="0.62",
        trend_expected_gross="0.0070",
        mean_reversion_probability="0.50",
    ))
    assert decision.action is StrategyAction.ENTER_LONG
```

- [ ] **Step 2: Implement arbiter exactly from approved rules**

Use `Decimal` comparisons. Persist specialist probabilities/expected returns, cost hurdle, regime, hold age, cooldown, protection levels, action, active specialist, and ordered reason codes.

- [ ] **Step 3: Implement Strategy protocol adapter**

`on_candle()` reads only current schedule row and `StrategyContext`; returns no intent, one market buy, or one market sell-to-close. Buy quantity is rounded down from available cash using existing precision rules; sell quantity is current position. `strategy_id="candidate.multi_model.v0_1"`; `production_eligible=False`.

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/unit/strategy/test_arbitration.py tests/unit/strategy/test_candidate_strategy.py tests/property/strategy/test_candidate_order_safety.py tests/regression/test_candidate_next_candle_only.py -v
uv run pyright
git add src/gemini_trading/strategy/arbitration.py src/gemini_trading/strategy/candidate.py tests/unit/strategy/test_arbitration.py tests/unit/strategy/test_candidate_strategy.py tests/property/strategy/test_candidate_order_safety.py tests/regression/test_candidate_next_candle_only.py
git commit -m "feat: arbitrate candidate long-cash decisions"
```

---

### Task 9: Locked Baseline Suite

**Files:**
- Create: `src/gemini_trading/strategy/baselines.py`
- Test: `tests/unit/strategy/test_baselines.py`, `tests/integration/test_strategy_baseline_engine.py`

**Interfaces:**
- Produces: `CashBaseline`, `BuyHoldBaseline`, `Ema2050Baseline`, `Donchian2010Baseline`, `MeanReversionZ24Baseline`, `BaselineSuite.locked_v0_1()`

- [ ] **Step 1: Write exact ID and signal tests**

```python
assert tuple(item.strategy_id for item in BaselineSuite.locked_v0_1()) == (
    "cash.v1", "buy_hold.v1", "ema_20_50.v1",
    "donchian_20_10.v1", "mean_reversion_z24.v1",
)
```

- [ ] **Step 2: Implement baselines through existing Strategy protocol**

Use precomputed trailing indicator schedules; no future candles or execution control. All active baselines use common sizing and simulator assumptions.

- [ ] **Step 3: Integration-test identical simulation hashes and commit**

```bash
uv run pytest tests/unit/strategy/test_baselines.py tests/integration/test_strategy_baseline_engine.py -v
uv run pyright
git add src/gemini_trading/strategy/baselines.py tests/unit/strategy/test_baselines.py tests/integration/test_strategy_baseline_engine.py
git commit -m "feat: add locked strategy baselines"
```

---

### Task 10: Metrics, Bootstrap, and Promotion Gates

**Files:**
- Modify: `src/gemini_trading/research/metrics.py`, `research/artifacts.py`
- Create: `src/gemini_trading/strategy/evaluation.py`
- Test: `tests/unit/research/test_metrics.py`, `tests/unit/strategy/test_evaluation_metrics.py`, `tests/property/strategy/test_cost_monotonicity.py`

**Interfaces:**
- Produces: expanded `BacktestMetrics`, `RegimeMetrics`, `BootstrapResult`, `PromotionReport`

- [ ] **Step 1: Write RED tests for annualized return/volatility, downside deviation, Sortino, return-to-drawdown, turnover, exposure-adjusted return, trade returns, profit factor, and hold duration**

Use 2,190 four-hour periods per year. Undefined ratios remain `None`.

- [ ] **Step 2: Extend research metric/artifact schemas**

Add entry/exit candle indices, gross/net trade return, and hold candles. Bump result schema to `research-result-v2`; update serialization, replay parsing, and verification in the same task.

- [ ] **Step 3: Implement regime attribution and deterministic moving-block bootstrap**

Use NumPy `Generator(PCG64(1788))`, 1,000 replicates, block length 42; report median, 5th, and 95th percentiles.

- [ ] **Step 4: Encode every mandatory gate as `GateResult`**

Stable IDs must include integrity, development stability, final economics, cost stress, sensitivity, bootstrap, negative controls, and component controls. Classification is `PASS`, `REJECTED`, or `INCONCLUSIVE`; all mandatory gates must pass for `PASS`.

- [ ] **Step 5: Test and commit**

```bash
uv run pytest tests/unit/research/test_metrics.py tests/unit/strategy/test_evaluation_metrics.py tests/property/strategy/test_cost_monotonicity.py -v
uv run pyright
git add src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py src/gemini_trading/strategy/evaluation.py tests/unit/research/test_metrics.py tests/unit/strategy/test_evaluation_metrics.py tests/property/strategy/test_cost_monotonicity.py
git commit -m "feat: evaluate strategy economics and gates"
```

---

### Task 11: Walk-Forward Study, Ablations, and Final-Test Seal

**Files:**
- Create: `src/gemini_trading/strategy/study.py`
- Test: `tests/integration/test_strategy_walk_forward_study.py`, `test_strategy_ablation_suite.py`, `tests/regression/test_final_test_seal.py`

**Interfaces:**
- Produces: `StrategyStudyEvidence`, `StrategyStudyRunner.run()`

- [ ] **Step 1: Write final-test access regression**

```python
def test_selection_cannot_read_final_test() -> None:
    with pytest.raises(FinalTestSealError):
        DevelopmentSelector(FinalTestSeal.create(plan)).read_predictions(plan.final_test)
```

- [ ] **Step 2: Implement each development fold**

Fit models on train, calibrate on calibration, predict forward test, classify regimes, run candidate, five baselines, standalone specialists, and development-safe ablations through `BacktestEngine`. Preserve every fold.

- [ ] **Step 3: Implement one final locked fit/test**

Seal all identities, fit on permitted pre-final data, use final six pre-test months for calibration, generate final predictions once, then run candidate, baselines, specialists, all ablations, shuffled labels seed `1799`, one-candle delayed features, 1.5x/2x costs, ten neighborhood variants, and bootstrap.

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/integration/test_strategy_walk_forward_study.py tests/integration/test_strategy_ablation_suite.py tests/regression/test_final_test_seal.py -v
uv run pyright
git add src/gemini_trading/strategy/study.py tests/integration/test_strategy_walk_forward_study.py tests/integration/test_strategy_ablation_suite.py tests/regression/test_final_test_seal.py
git commit -m "feat: run sealed multi-model strategy studies"
```

---

### Task 12: Immutable Study Artifacts

**Files:**
- Create: `src/gemini_trading/strategy/artifacts.py`
- Test: `tests/unit/strategy/test_study_artifacts.py`, `tests/property/strategy/test_study_result_identity.py`, `tests/regression/test_tampered_strategy_artifacts.py`

**Interfaces:**
- Produces: `StrategyStudyArtifacts`, `build_study_artifacts()`, `LocalStrategyStudyStore`

- [ ] **Step 1: Write required artifact-set test**

Require canonical policy, feature registry/matrix, labels, split plan, folds, models, calibration, predictions, regimes, arbitration, experiment references, baselines, ablations, controls, cost stress, sensitivity, bootstrap, promotion gates, limitations, and result manifest.

- [ ] **Step 2: Derive study result identity**

```text
study_result_id = sha256(canonical_json({schema_version, study_id, artifact_hashes, classification}))
```

Store under `data/strategy-studies/<study_id>/` with `write_immutable`.

- [ ] **Step 3: Test byte-identical reruns, conflict rejection, tampering, and missing failed-fold evidence; commit**

```bash
uv run pytest tests/unit/strategy/test_study_artifacts.py tests/property/strategy/test_study_result_identity.py tests/regression/test_tampered_strategy_artifacts.py -v
uv run pyright
git add src/gemini_trading/strategy/artifacts.py tests/unit/strategy/test_study_artifacts.py tests/property/strategy/test_study_result_identity.py tests/regression/test_tampered_strategy_artifacts.py
git commit -m "feat: persist immutable strategy study evidence"
```

---

### Task 13: Provider-Free Replay and Independent Verification

**Files:**
- Create: `src/gemini_trading/strategy/replay.py`, `verification.py`
- Modify: `src/gemini_trading/research/replay.py`, `verification.py`
- Test: `tests/integration/test_strategy_replay_without_network.py`, `tests/unit/strategy/test_strategy_verification.py`, `tests/regression/test_strategy_replay_commit_mismatch.py`

**Interfaces:**
- Produces: `StrategyStudyReplayService.replay(study_id)`
- Produces: `StrategyStudyVerificationService.verify(study_id)`

- [ ] **Step 1: Write network-denial replay test**

Monkeypatch sockets, HTTP provider, and Binance provider construction to raise. Replay must regenerate byte-identical core artifacts from canonical local evidence.

- [ ] **Step 2: Replace fixture-only replay branching with a closed strategy factory registry**

Support fixture, candidate, and five baseline IDs; unknown IDs fail closed.

- [ ] **Step 3: Verify all hashes, identities, referenced experiments, final-test receipt, mandatory gates, exact replay, and code commit**

Return safe check names only; no model arrays, provider bodies, environment dumps, or absolute paths.

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/integration/test_strategy_replay_without_network.py tests/unit/strategy/test_strategy_verification.py tests/regression/test_strategy_replay_commit_mismatch.py -v
uv run pyright
git add src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/verification.py src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_strategy_replay_without_network.py tests/unit/strategy/test_strategy_verification.py tests/regression/test_strategy_replay_commit_mismatch.py
git commit -m "feat: replay and verify strategy studies"
```

---

### Task 14: Safe CLI and Locked Configuration

**Files:**
- Create: `src/gemini_trading/cli/strategy.py`, `tests/fixtures/strategy/candidate-v0.1-config.json`
- Modify: `src/gemini_trading/cli/main.py`, `cli/research.py`
- Test: `tests/unit/cli/test_strategy.py`, `tests/acceptance/test_strategy_cli.py`

**Interfaces:**
- Adds: `research strategy-evaluate`, `strategy-replay`, `strategy-verify`

- [ ] **Step 1: Write parser, safe JSON, and live-mode rejection tests**

- [ ] **Step 2: Add exact CLI config**

```json
{
  "schema_version": "candidate-strategy-cli-v1",
  "initial_cash": "10000",
  "simulation": {
    "maker_fee_rate": "0.001", "taker_fee_rate": "0.001",
    "half_spread_bps": "5", "slippage_bps": "10", "latency_bars": 0,
    "price_tick": "0.01", "quantity_step": "0.000001",
    "min_quantity": "0.000001", "min_notional": "5",
    "max_volume_participation": "0.01", "max_active_candles": 3,
    "timing_policy": "next_candle", "limit_fill_policy": "conservative",
    "default_time_in_force": "bar", "promotable": true
  },
  "strategy": {
    "id": "candidate.multi_model.v0_1",
    "policy_version": "candidate-multi-model-v0.1"
  }
}
```

Reject extra fields, changed policy identity, zero costs, or diagnostic policies.

- [ ] **Step 3: Implement safe outputs**

Evaluate returns `classification`, `status`, `study_id`, `study_result_id`, and `promotable:false`. Replay/verify accept study ID. All failures use existing compact JSON and exit code 2.

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/unit/cli/test_strategy.py tests/acceptance/test_strategy_cli.py -v
uv run pyright
git add src/gemini_trading/cli src/gemini_trading/cli/main.py tests/fixtures/strategy tests/unit/cli/test_strategy.py tests/acceptance/test_strategy_cli.py
git commit -m "feat: expose safe strategy study CLI"
```

---

### Task 15: Documentation, Acceptance, and Exact Verification

**Files:**
- Modify: `README.md`
- Create: `docs/operations/candidate-multi-model-strategy.md`, `candidate-multi-model-strategy-step-verification.md`
- Create: `reports/verification/candidate-multi-model-strategy-progress.md`, `candidate-multi-model-strategy-final.md`
- Test: `tests/acceptance/test_candidate_strategy_documentation.py`, `test_candidate_strategy_end_to_end.py`

- [ ] **Step 1: Document research-only scope, seven-year history, final-test sealing, evaluate/replay/verify commands, and rejection as a valid outcome**

- [ ] **Step 2: Build a synthetic diagnostic acceptance fixture**

Exercise the complete pipeline but force `INCONCLUSIVE` because synthetic/short history is non-promotable. Prove byte-stable replay, verification, tamper detection, and live/demo/production rejection. Do not claim edge.

- [ ] **Step 3: Run complete gates**

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv build
uv run pip-audit
uv run pre-commit run --all-files
git diff --check
git status --short
```

- [ ] **Step 4: Run deterministic acceptance twice and compare study/result IDs and artifact hashes**

- [ ] **Step 5: Write final evidence with exact commit, lock hash, test counts, study/result IDs, replay/verification receipts, every mandatory gate, limitations, and final classification**

- [ ] **Step 6: Commit and perform PR gates**

```bash
git add README.md docs/operations reports/verification tests/acceptance
git commit -m "docs: verify candidate multi-model strategy milestone"
```

Before merge: verify exact PR head, ordinary CI, focused deterministic acceptance, independent evidence review, protected merge, then exact merged-main verification. Close Issue #16 only after the implementation milestone and post-merge verification complete.

---

## Self-Review

**Spec coverage:** Tasks 1–4 cover scope, identities, point-in-time features, labels, leakage, and splits. Tasks 5–8 cover specialists, calibration, regimes, arbitration, abstention, and risk. Tasks 9–11 cover baselines, metrics, folds, ablations, stresses, controls, uncertainty, and promotion gates. Tasks 12–15 cover immutable evidence, replay, independent verification, CLI safety, documentation, and exact acceptance.

**Type consistency:** The plan consistently uses `CandidatePolicy`, `FeatureRegistry`, `FeatureMatrix`, `LabelPolicy`, `LabelVector`, `ChronologicalSplitPlan`, `LinearModelArtifact`, `BoostedTreeArtifact`, `PlattArtifact`, `ExpectedReturnMap`, `RegimeObservation`, `MultiModelArbiter`, `CandidateMultiModelStrategy`, `StrategyStudyEvidence`, and `StrategyStudyArtifacts`.

**Scope check:** No task introduces OKX, derivatives, funding, order books, news, geopolitics, on-chain data, cross-assets, deep learning, live execution, leverage, shorting, portfolio allocation, or real-capital authority.
