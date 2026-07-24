# Candidate Multi-Model Strategy v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved research-only BTC/USDT 4-hour multi-model candidate with point-in-time features, cost-aware labels, deterministic specialists, sealed walk-forward evaluation, long/cash arbitration, immutable evidence, provider-free replay, and independent verification.

**Architecture:** Create a bounded `gemini_trading.strategy` package above the verified Market Data Core and existing `BacktestEngine`. Model training produces canonical non-executable artifacts and a decision schedule; the existing engine remains the only authority for orders, fills, precision, liquidity, accounting, and economic evidence. A strategy-study layer references the resulting research experiments and evaluates every predeclared baseline, control, stress, and promotion gate.

**Tech Stack:** Python 3.12, `Decimal`, NumPy, scikit-learn 1.9, threadpoolctl, pytest, Hypothesis, Ruff, strict Pyright, canonical JSON/JSONL, immutable local storage, and the deterministic research engine.

## Global Constraints

- Promotion remains `RESEARCH_ONLY`; the candidate is always `production_eligible=False` and study CLI output is always `promotable:false`.
- Scope is BTC/USDT Binance Spot, completed 4-hour candles, long or cash only.
- Consume only verified canonical `candle-dataset-v1` OHLCV evidence.
- Require seven years of continuous verified history for a promotable historical study.
- Features use completed candles only; official execution remains next-candle and conservative.
- Reuse simulator fees, spread, slippage, latency, tick/step precision, minimums, liquidity participation, fills, and accounting.
- Trend model: elastic-net logistic regression, `C=1.0`, `l1_ratio=0.5`, seed `1701`.
- Mean-reversion model: gradient boosting, 150 trees, depth 2, learning rate `0.03`, minimum leaf 100, full row/feature participation, seed `1702`.
- Calibration is fold-local and requires at least 200 rows, 40 positive labels, and 40 negative labels.
- Development: expanding 24-month minimum train, 6-month calibration, 6-month forward test, 6-month step, 3-candle purge, 3-candle embargo, at least five folds.
- Final untouched test: last 18 calendar months, evaluated once for Candidate v0.1.
- No credentials, private endpoints, broker/demo/live execution, leverage, futures, shorting, portfolio allocation, or real-capital authority.
- Preserve every failed fold, rejected experiment, negative control, and failed promotion gate.
- Every task follows RED → GREEN → quality gates → commit.

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

Modify only these integration surfaces when their task requires it:

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

### Task 1: Locked Policy, Contracts, Errors, and Identities

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/gemini_trading/research/errors.py`
- Create: `src/gemini_trading/strategy/__init__.py`, `errors.py`, `contracts.py`, `policy.py`, `identity.py`
- Create: `tests/strategy_fixture_support.py`
- Test: `tests/unit/strategy/test_policy.py`, `test_contracts.py`, `test_errors.py`, `test_identity.py`
- Test: `tests/property/strategy/test_strategy_identity.py`

**Interfaces:**
- `CandidatePolicy.locked_v0_1() -> CandidatePolicy`
- `serialize_candidate_policy(policy: CandidatePolicy) -> bytes`
- `component_id(schema_version: str, payload: Mapping[str, object]) -> str`
- `StrategyStudyManifest`, `serialize_study_manifest()`, `study_id()`
- `RegimeState`, `SpecialistKind`, `StrategyAction`, `IndexWindow`, `SpecialistPrediction`, `GateResult`

- [ ] **Step 1: Add and lock deterministic ML dependencies**

```toml
dependencies = [
  "numpy>=2.2,<3",
  "scikit-learn==1.9.0",
  "threadpoolctl>=3.6,<4",
]
```

```bash
uv lock
uv sync --all-groups --frozen
```

Expected: Python 3.12 environment resolves and imports NumPy, scikit-learn, and threadpoolctl.

- [ ] **Step 2: Write failing policy/contract tests**

```python
from decimal import Decimal

from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy


def test_locked_policy_matches_approved_spec() -> None:
    policy = CandidatePolicy.locked_v0_1()
    assert policy.strategy_id == "candidate.multi_model.v0_1"
    assert (policy.instrument_symbol, policy.timeframe) == ("BTCUSDT", "4h")
    assert policy.minimum_history_years == 7
    assert policy.final_test_months == 18
    assert policy.label_horizon_candles == 3
    assert policy.entry_probability == Decimal("0.62")
    assert policy.hold_probability == Decimal("0.50")
    assert policy.exit_probability == Decimal("0.45")
    assert policy.disagreement_limit == Decimal("0.25")
    assert policy.minimum_hold_candles == 2
    assert policy.maximum_hold_candles == 18
    assert policy.cooldown_candles == 2
    assert policy.initial_stop_atr == Decimal("2.5")
    assert policy.trailing_stop_atr == Decimal("3.0")
    assert serialize_candidate_policy(policy) == serialize_candidate_policy(
        CandidatePolicy.locked_v0_1()
    )


def test_closed_enums_are_stable() -> None:
    assert tuple(x.value for x in RegimeState) == (
        "unstable", "trending", "ranging", "indeterminate"
    )
    assert tuple(x.value for x in SpecialistKind) == ("trend", "mean_reversion")
    assert tuple(x.value for x in StrategyAction) == (
        "enter_long", "remain_long", "exit_to_cash", "remain_in_cash"
    )
```

Run:

```bash
uv run pytest tests/unit/strategy/test_policy.py tests/unit/strategy/test_contracts.py -v
```

Expected: FAIL because `gemini_trading.strategy` does not exist.

- [ ] **Step 3: Implement exact contracts**

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

@dataclass(frozen=True, slots=True)
class SpecialistPrediction:
    candle_index: int
    specialist: SpecialistKind
    raw_score_hex: str
    probability: Decimal
    expected_gross_return: Decimal

@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    passed: bool
    observed: str
    required: str
    reason: str
```

Validate non-negative indices, strict window order, finite `[0,1]` probabilities, non-empty IDs, and finite returns.

- [ ] **Step 4: Implement `CandidatePolicy` as the only promotable structural policy**

`locked_v0_1()` must contain every fixed value from the approved spec, including model parameters, seeds `1701/1702/1788/1799`, regime thresholds, arbitration thresholds, risk rules, fold lengths, baseline IDs, sensitivity values, and gate thresholds. The CLI must never accept overrides for those fields.

- [ ] **Step 5: Add safe errors**

Add these `ResearchError` subclasses and re-export them from `strategy/errors.py`:

```python
class StrategyStudyError(ResearchError): ...
class InsufficientHistoryError(StrategyStudyError): ...
class PointInTimeViolationError(StrategyStudyError): ...
class SplitBoundaryError(StrategyStudyError): ...
class LabelLeakageError(StrategyStudyError): ...
class InsufficientCalibrationError(StrategyStudyError): ...
class ModelDeterminismError(StrategyStudyError): ...
class ProbabilityRangeError(StrategyStudyError): ...
class FinalTestSealError(StrategyStudyError): ...
class StudyArtifactError(StrategyStudyError): ...
class StudyReplayMismatchError(StrategyStudyError): ...
class StudyVerificationError(StrategyStudyError): ...
```

- [ ] **Step 6: Write and implement study identity tests**

```python
def test_study_id_changes_for_each_trust_boundary() -> None:
    manifest = example_study_manifest()
    assert study_id(manifest) == study_id(manifest)
    assert study_id(replace(manifest, dataset_id="1" * 64)) != study_id(manifest)
    assert study_id(replace(manifest, code_commit="1" * 40)) != study_id(manifest)
    assert study_id(replace(manifest, policy_id="2" * 64)) != study_id(manifest)
    assert study_id(replace(manifest, split_plan_id="3" * 64)) != study_id(manifest)
```

Use this exact manifest:

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

Derive component and study IDs with SHA-256 over canonical JSON bytes.

- [ ] **Step 7: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_policy.py tests/unit/strategy/test_contracts.py tests/unit/strategy/test_errors.py tests/unit/strategy/test_identity.py tests/property/strategy/test_strategy_identity.py -v
uv run ruff format --check src tests
uv run ruff check src tests
uv run pyright
git add pyproject.toml uv.lock src/gemini_trading/strategy src/gemini_trading/research/errors.py tests/strategy_fixture_support.py tests/unit/strategy tests/property/strategy
git commit -m "feat: define candidate strategy trust contracts"
```

---

### Task 2: Point-in-Time Feature Registry

**Files:**
- Create: `src/gemini_trading/strategy/features.py`
- Test: `tests/unit/strategy/test_features.py`
- Test: `tests/property/strategy/test_feature_point_in_time.py`
- Test: `tests/regression/test_strategy_feature_alignment.py`

**Interfaces:**
- `FeatureDefinition`, `FeatureRow`, `FeatureMatrix`
- `FeatureRegistry.locked_v0_1() -> FeatureRegistry`
- `FeatureRegistry.compute(candles: tuple[Candle, ...]) -> FeatureMatrix`
- `FeatureMatrix.row_for(index: int) -> FeatureRow`

- [ ] **Step 1: Write deterministic BTC fixture helper**

```python
def btc_candle(index: int, *, close: str, volume: str = "100") -> Candle:
    opened = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=4 * index)
    value = Decimal(close)
    return Candle(
        instrument=Instrument("BTCUSDT", "BTC", "USDT"),
        timeframe=Timeframe.H4,
        open_time=opened,
        close_time=opened + timedelta(hours=4) - timedelta(milliseconds=1),
        open=value - Decimal("1"),
        high=value + Decimal("2"),
        low=value - Decimal("2"),
        close=value,
        volume=Decimal(volume),
        completed=True,
        source_provider="binance_spot",
    )
```

- [ ] **Step 2: Write RED point-in-time tests**

```python
def test_first_eligible_row_is_index_42() -> None:
    matrix = FeatureRegistry.locked_v0_1().compute(rising_candles(50))
    assert matrix.rows[0].candle_index == 42
    assert all(value.is_finite() for value in matrix.rows[0].values)


def test_future_mutation_cannot_change_prior_features() -> None:
    candles = rising_candles(60)
    registry = FeatureRegistry.locked_v0_1()
    first = registry.compute(candles)
    changed = (*candles[:-1], replace(
        candles[-1], close=Decimal("999999"), high=Decimal("999999")
    ))
    second = registry.compute(changed)
    assert first.row_for(58) == second.row_for(58)
```

- [ ] **Step 3: Implement the exact registry construction**

Use `Context(prec=34, rounding=ROUND_HALF_EVEN)` and build definitions with these fixed loops:

```python
for lag in (1, 2, 3, 6, 12, 24, 42): add_log_return(lag)
for window in (6, 12, 24, 42): add_positive_fraction(window)
add_return_acceleration(current=3, previous=3)
for window in (12, 42): add_high_low_distances(window)
for span in (6, 12, 24, 42): add_ema_distance(span)
for fast, slow in ((6, 24), (12, 42), (24, 42)): add_ema_spread(fast, slow)
for span in (6, 12, 24, 42):
    for slope_window in (3, 6): add_ema_slope(span, slope_window)
for window in (6, 12, 24): add_trend_consistency(window)
for window in (6, 12, 24, 42): add_realized_volatility(window)
for window in (6, 12, 24): add_average_true_range(window)
add_current_true_range_ratio(24)
add_candle_body_wicks_and_close_location()
for window in (12, 24): add_rolling_close_location(window)
for window in (12, 24, 42):
    add_close_zscore(window)
    add_median_atr_distance(window, atr_window=24)
    add_drawdown_and_rebound(window)
for lag in (1, 3, 6, 12): add_log_volume_change(lag)
for window in (12, 24, 42): add_median_volume_ratio(window)
for window in (24, 42): add_volume_zscore(window)
add_signed_volume_proxy()
add_range_volume_proxy()
```

Every feature is trailing-only. A zero denominator, missing lookback, non-positive log input, or non-finite output omits the row; no imputation.

- [ ] **Step 4: Define specialist isolation exactly**

- Trend: return, momentum, trend, volatility, and volume groups.
- Mean reversion: mean-reversion, candle-structure, volatility, and volume groups.
- Regime: `trend_strength_12_42_atr24`, `volatility_ratio_6_42`, `true_range_ratio_24`, `ema_12_42_sign_streak`.

Validate all tuples as strict subsets of the registry and reject duplicate feature names.

- [ ] **Step 5: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_features.py tests/property/strategy/test_feature_point_in_time.py tests/regression/test_strategy_feature_alignment.py -v
uv run ruff check src tests
uv run pyright
git add src/gemini_trading/strategy/features.py tests/unit/strategy/test_features.py tests/property/strategy/test_feature_point_in_time.py tests/regression/test_strategy_feature_alignment.py
git commit -m "feat: add point-in-time strategy features"
```

---

### Task 3: Cost-Aware Labels and Sealed Chronological Splits

**Files:**
- Create: `src/gemini_trading/strategy/labels.py`, `splits.py`
- Test: `tests/unit/strategy/test_labels.py`, `test_splits.py`
- Test: `tests/property/strategy/test_label_boundaries.py`
- Test: `tests/regression/test_strategy_label_leakage.py`

**Interfaces:**
- `LabelObservation`, `LabelVector`, `LabelPolicy.locked_v0_1(config)`
- `IndexWindow`, `WalkForwardFold`, `ChronologicalSplitPlan.build()`

- [ ] **Step 1: Write RED label timing/cost test**

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

The expected fill prices must call `market_fill_costs()` and `round_fill_price()` rather than reproduce their formula in the test.

- [ ] **Step 2: Implement labels exactly**

For unit quantity:
1. entry reference is candle `t+1.open`;
2. exit reference is candle `t+4.open`;
3. apply taker fee, half-spread, and slippage on both sides;
4. adversely round buy and sell prices by `price_tick`;
5. gross return is `(rounded_sell / rounded_buy) - 1`;
6. net return is `(sell_notional - sell_fee - buy_notional - buy_fee) / (buy_notional + buy_fee)`;
7. hurdle bps is `2 * (taker_fee_rate * 10000 + half_spread_bps + slippage_bps) + 10`;
8. positive class is `net_return > hurdle_bps / 10000`.

Persist all indices, prices, returns, hurdle, and class.

- [ ] **Step 3: Write RED split/boundary tests**

```python
def test_split_plan_locks_required_windows() -> None:
    plan = ChronologicalSplitPlan.build(candles, eligible_indices, CandidatePolicy.locked_v0_1())
    assert plan.final_test_months == 18
    assert len(plan.folds) >= 5
    assert all(fold.purge_candles == 3 for fold in plan.folds)
    assert all(fold.embargo_candles == 3 for fold in plan.folds)


def test_no_label_window_crosses_a_boundary() -> None:
    for boundary in plan.boundary_indices:
        assert all(not (index < boundary < index + 4) for index in plan.used_label_indices)
```

- [ ] **Step 4: Implement deterministic UTC calendar windows**

Build last-18-month final test, then expanding 24-month minimum train, 6-month calibration, 6-month forward test, and 6-month steps. Exclude three candles for purge and three for embargo at each boundary. Raise `InsufficientHistoryError`, `SplitBoundaryError`, or `FinalTestSealError`; never shorten required windows.

- [ ] **Step 5: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_labels.py tests/unit/strategy/test_splits.py tests/property/strategy/test_label_boundaries.py tests/regression/test_strategy_label_leakage.py -v
uv run pyright
git add src/gemini_trading/strategy/labels.py src/gemini_trading/strategy/splits.py tests/unit/strategy/test_labels.py tests/unit/strategy/test_splits.py tests/property/strategy/test_label_boundaries.py tests/regression/test_strategy_label_leakage.py
git commit -m "feat: add cost-aware labels and sealed splits"
```

---

### Task 4: Deterministic Specialist Models and Calibration

**Files:**
- Create: `src/gemini_trading/strategy/models.py`, `calibration.py`
- Test: `tests/unit/strategy/test_models.py`, `test_calibration.py`
- Test: `tests/property/strategy/test_model_serialization.py`, `test_probability_bounds.py`
- Test: `tests/regression/test_strategy_model_determinism.py`

**Interfaces:**
- `LinearModelArtifact`, `TreeNodeArtifact`, `BoostedTreeArtifact`
- `TrendSpecialistTrainer.fit()`, `MeanReversionSpecialistTrainer.fit()`
- `PlattArtifact`, `ExpectedReturnMap`, `fit_platt_calibrator()`, `apply_platt()`
- `predict_raw()`, `serialize_model_artifact()`, `parse_model_artifact()`

- [ ] **Step 1: Write RED deterministic-fit tests**

```python
def test_trend_fit_is_byte_deterministic() -> None:
    trainer = TrendSpecialistTrainer(CandidatePolicy.locked_v0_1())
    first = trainer.fit(deterministic_training_fixture())
    second = trainer.fit(deterministic_training_fixture())
    assert serialize_model_artifact(first) == serialize_model_artifact(second)


def test_mean_reversion_shape_is_locked() -> None:
    model = MeanReversionSpecialistTrainer(CandidatePolicy.locked_v0_1()).fit(
        deterministic_mean_reversion_fixture()
    )
    assert model.estimator_count == 150
    assert model.max_depth == 2
    assert model.learning_rate_hex == float(0.03).hex()
```

- [ ] **Step 2: Implement fold-local matrix preparation**

Convert `Decimal` to `np.float64` only after split selection. Fit mean and population standard deviation on training rows only. Reject zero-variance columns. Store mean/scale with `float.hex()`. Wrap every fit in `threadpool_limits(limits=1)`.

- [ ] **Step 3: Fit the trend model exactly**

```python
LogisticRegression(
    penalty="elasticnet",
    solver="saga",
    C=1.0,
    l1_ratio=0.5,
    max_iter=5000,
    tol=1e-8,
    fit_intercept=True,
    class_weight=class_weight,
    random_state=1701,
    n_jobs=1,
)
```

Use `class_weight=None` when positive fraction is within `[0.30,0.70]`; otherwise exact inverse-frequency weights. Reject `n_iter_ >= 5000`.

- [ ] **Step 4: Fit the mean-reversion model exactly**

```python
GradientBoostingClassifier(
    loss="log_loss",
    learning_rate=0.03,
    n_estimators=150,
    subsample=1.0,
    max_depth=2,
    min_samples_leaf=100,
    max_features=None,
    random_state=1702,
)
```

Training rows must satisfy z-score 24 `<= -0.75` or drawdown 24 `>= 0.02` and contain both classes.

- [ ] **Step 5: Serialize non-executable model artifacts**

Store feature names, means/scales, intercept/coefficients, boosted initial raw score, and every tree node’s left child, right child, feature index, threshold, and value using hexadecimal floats. Custom inference must match scikit-learn raw scores within `1e-12`. Do not persist pickle, joblib, or arbitrary executable objects.

- [ ] **Step 6: Write RED calibration tests**

```python
def test_calibration_requires_minimum_classes() -> None:
    with pytest.raises(InsufficientCalibrationError, match="40 positive"):
        fit_platt_calibrator([0.0] * 200, [False] * 180 + [True] * 20)


def test_platt_probability_is_bounded() -> None:
    artifact = fit_platt_calibrator(calibration_scores(), calibration_labels())
    values = [apply_platt(artifact, score) for score in (-1e9, -10.0, 0.0, 10.0, 1e9)]
    assert all(Decimal("0") <= value <= Decimal("1") for value in values)
```

- [ ] **Step 7: Implement calibration and expected-return map**

Fit `p = sigmoid(a * raw_score + b)` with Newton-Raphson: maximum 100 iterations, diagonal stabilizer `1e-12`, parameter-delta tolerance `1e-12`, stable positive/negative sigmoid branches, explicit singular/non-convergence errors. Fit OLS `gross_return = intercept + slope * probability`; reject zero probability variance and clamp inference to calibration probability range. Add Brier score, log loss clipped to `[1e-15,1-1e-15]`, and ten-bin ECE.

- [ ] **Step 8: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_models.py tests/unit/strategy/test_calibration.py tests/property/strategy/test_model_serialization.py tests/property/strategy/test_probability_bounds.py tests/regression/test_strategy_model_determinism.py -v
uv run pyright
git add src/gemini_trading/strategy/models.py src/gemini_trading/strategy/calibration.py tests/unit/strategy/test_models.py tests/unit/strategy/test_calibration.py tests/property/strategy/test_model_serialization.py tests/property/strategy/test_probability_bounds.py tests/regression/test_strategy_model_determinism.py
git commit -m "feat: train and calibrate deterministic specialists"
```

---

### Task 5: Regime Classifier, Arbitration, and Candidate Strategy

**Files:**
- Create: `src/gemini_trading/strategy/regimes.py`, `arbitration.py`, `candidate.py`
- Test: `tests/unit/strategy/test_regimes.py`, `test_arbitration.py`, `test_candidate_strategy.py`
- Test: `tests/property/strategy/test_candidate_order_safety.py`
- Test: `tests/regression/test_candidate_next_candle_only.py`

**Interfaces:**
- `RegimeObservation`, `RegimeClassifier.classify()`
- `ArbitrationInput`, `ArbitrationDecision`, `MultiModelArbiter.decide()`
- `CandidateDecisionSchedule`, `CandidateMultiModelStrategy`

- [ ] **Step 1: Write exact regime tests**

```python
@pytest.mark.parametrize(
    ("strength", "vol_ratio", "range_ratio", "streak", "expected"),
    [
        ("2.0", "1.75", "1.0", 4, RegimeState.UNSTABLE),
        ("1.0", "1.49", "1.0", 3, RegimeState.TRENDING),
        ("0.5", "1.25", "1.0", 0, RegimeState.RANGING),
        ("0.8", "1.30", "1.0", 2, RegimeState.INDETERMINATE),
    ],
)
def test_regime_rule_order(strength, vol_ratio, range_ratio, streak, expected) -> None:
    assert classify_values(strength, vol_ratio, range_ratio, streak).state is expected
```

Evaluate unstable first, then trending, then ranging, else indeterminate. Persist all inputs and one reason code.

- [ ] **Step 2: Write exact entry/abstention tests**

```python
def test_trending_entry_passes_at_locked_boundary() -> None:
    decision = arbiter().decide(flat_input(
        regime=RegimeState.TRENDING,
        trend_probability="0.62",
        trend_expected_gross="0.0071",
        mean_reversion_probability="0.45",
    ))
    assert decision.action is StrategyAction.ENTER_LONG


def test_unstable_or_conflicting_evidence_abstains() -> None:
    assert arbiter().decide(flat_input(regime=RegimeState.UNSTABLE)).action is StrategyAction.REMAIN_IN_CASH
    assert arbiter().decide(flat_input(
        regime=RegimeState.TRENDING,
        trend_probability="0.80",
        mean_reversion_probability="0.40",
    )).action is StrategyAction.REMAIN_IN_CASH
```

Base hurdle is 60 bps; entry expected gross must exceed 70 bps. Trending uses trend `>=0.62`; ranging uses active stretch and mean reversion `>=0.62`; companion probability must be `>=0.45`; conflicting specialist difference must be `<=0.25`.

- [ ] **Step 3: Write exact hold/exit/risk tests**

Test all boundaries:
- hold active probability `>=0.50`;
- probability `<=0.45` exits;
- unstable exits at next candle;
- one indeterminate candle is tolerated, second incompatible candle exits;
- initial stop is entry minus `2.5 * ATR24`;
- trailing stop is max completed close since entry minus `3.0 * ATR24` and never decreases;
- maximum hold 18 candles;
- minimum hold 2 except unstable/stop;
- cooldown 2 candles;
- no pyramiding and no sell above current position.

- [ ] **Step 4: Implement arbiter and strategy adapter**

`ArbitrationDecision` stores candle index, action, active specialist, regime, probabilities, expected gross returns, hurdle, hold age, cooldown, stop levels, and ordered reasons. `CandidateMultiModelStrategy.on_candle()` reads only current schedule row and `StrategyContext`, returning no intent, one market buy, or one market sell-to-close. Buy target is 100% available cash subject to existing quantity rounding/minimums; sell quantity equals current position. Set `strategy_id="candidate.multi_model.v0_1"` and `production_eligible=False`.

- [ ] **Step 5: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_regimes.py tests/unit/strategy/test_arbitration.py tests/unit/strategy/test_candidate_strategy.py tests/property/strategy/test_candidate_order_safety.py tests/regression/test_candidate_next_candle_only.py -v
uv run pyright
git add src/gemini_trading/strategy/regimes.py src/gemini_trading/strategy/arbitration.py src/gemini_trading/strategy/candidate.py tests/unit/strategy/test_regimes.py tests/unit/strategy/test_arbitration.py tests/unit/strategy/test_candidate_strategy.py tests/property/strategy/test_candidate_order_safety.py tests/regression/test_candidate_next_candle_only.py
git commit -m "feat: arbitrate candidate long-cash decisions"
```

---

### Task 6: Locked Baseline Suite

**Files:**
- Create: `src/gemini_trading/strategy/baselines.py`
- Test: `tests/unit/strategy/test_baselines.py`
- Test: `tests/integration/test_strategy_baseline_engine.py`

**Interfaces:**
- `CashBaseline`, `BuyHoldBaseline`, `Ema2050Baseline`, `Donchian2010Baseline`, `MeanReversionZ24Baseline`
- `BaselineSuite.locked_v0_1()`

- [ ] **Step 1: Write exact ID/rule tests**

```python
def test_baseline_ids_are_locked() -> None:
    assert tuple(item.strategy_id for item in BaselineSuite.locked_v0_1()) == (
        "cash.v1", "buy_hold.v1", "ema_20_50.v1",
        "donchian_20_10.v1", "mean_reversion_z24.v1",
    )
```

Rules:
- cash: no intents;
- buy/hold: enter first eligible next candle, hold until evaluation terminal policy;
- EMA: long while completed-candle EMA20 `> EMA50`, cash otherwise;
- Donchian: enter when completed close exceeds prior 20-candle high, exit when completed close is below prior 10-candle low;
- z24: enter when completed close z-score `<=-1.5`, exit at z-score `>=0` or common stop.

- [ ] **Step 2: Implement through existing Strategy protocol**

Use precomputed trailing schedules and common sizing/risk helpers. Baselines cannot access providers, future candles, or fill/accounting internals.

- [ ] **Step 3: Verify identical simulation policy**

Integration tests assert all active comparisons share `simulation_config_sha256`, next-candle timing, conservative fill policy, and no provider calls.

- [ ] **Step 4: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_baselines.py tests/integration/test_strategy_baseline_engine.py -v
uv run pyright
git add src/gemini_trading/strategy/baselines.py tests/unit/strategy/test_baselines.py tests/integration/test_strategy_baseline_engine.py
git commit -m "feat: add locked strategy baselines"
```

---

### Task 7: Expanded Metrics, Robustness, and Promotion Gates

**Files:**
- Modify: `src/gemini_trading/research/metrics.py`, `research/artifacts.py`, `research/replay.py`, `research/verification.py`
- Create: `src/gemini_trading/strategy/evaluation.py`
- Test: `tests/unit/research/test_metrics.py`
- Test: `tests/unit/strategy/test_evaluation_metrics.py`, `test_promotion_gates.py`
- Test: `tests/property/strategy/test_cost_monotonicity.py`

**Interfaces:**
- Expanded `CompletedTrade`, `BacktestMetrics`
- `RegimeMetrics`, `BootstrapResult`, `PromotionReport`, `evaluate_promotion()`

- [ ] **Step 1: Write exact metric tests and formulas**

Use 2,190 four-hour periods/year:

```text
annualized_geometric = (ending / starting) ** (2190 / observed_periods) - 1
annualized_volatility = population_std(period_returns) * sqrt(2190)
downside_deviation = sqrt(mean(min(return, 0) ** 2)) * sqrt(2190)
sortino = annualized_geometric / downside_deviation
return_to_drawdown = annualized_geometric / maximum_drawdown
turnover = sum(fill.notional) / mean(account.marked_equity)
exposure_adjusted_return = net_return / exposure_fraction
profit_factor = sum(positive_trade_pnl) / abs(sum(negative_trade_pnl))
```

Undefined denominators return `None`.

- [ ] **Step 2: Extend core artifacts atomically**

Add entry/exit candle indices, gross/net return, and hold candles to `CompletedTrade`; add approved metrics to `BacktestMetrics`; bump result schema to `research-result-v2`; update serialization, replay parsing, and verification required fields in the same commit.

- [ ] **Step 3: Implement regime attribution**

For each of `TRENDING`, `RANGING`, `INDETERMINATE`, `UNSTABLE`, calculate net return, maximum drawdown, exposure fraction, and completed-trade count from stored regime states and account changes.

- [ ] **Step 4: Implement deterministic bootstrap**

Use `np.random.Generator(np.random.PCG64(1788))`, 1,000 moving-block replicates, block length 42. Store sampled-start matrix identity. Report median, 5th percentile, and 95th percentile for candidate-minus-strongest-baseline net return, drawdown, and return-to-drawdown differences.

- [ ] **Step 5: Encode every mandatory gate with exact thresholds**

Development:
- at least 5 folds;
- at least 60% positive candidate net return;
- at least 60% beat strongest active baseline return-to-drawdown when defined;
- no fold contributes over 50% of summed positive fold profit;
- at least 60 completed development trades.

Final:
- positive base-cost net return;
- at least 30 trades;
- drawdown `<=25%` and `<=80%` of buy/hold drawdown;
- return-to-drawdown `>=0.50`, `>=10%` above strongest simple active baseline, and `>=5%` above strongest standalone learned specialist;
- net return no more than 2 percentage points below strongest active simple baseline;
- no trade contributes over 25% of positive trade profit;
- at least two required regimes non-negative and no required regime loses over 25% of aggregate positive profit.

Costs/sensitivity/uncertainty:
- 1.5x cost return positive and drawdown `<=27.5%`;
- 2x cost return `>=-5%` and drawdown `<=30%`;
- at least 7/10 neighboring variants positive, median positive, no drawdown over 35%;
- when primary return `<=2%`, no neighbor improves it by over 100%;
- bootstrap median difference positive and 90% lower bound above `-2` percentage points;
- shuffled labels fail all economic gates;
- one-candle delayed features do not beat primary return-to-drawdown by over 5%;
- no-disagreement, no-volume, and no-protection controls satisfy the approved component-value rules.

Each becomes a `GateResult`; classification is `PASS`, `REJECTED`, or `INCONCLUSIVE`, with `PASS` requiring every mandatory gate.

- [ ] **Step 6: Run gates and commit**

```bash
uv run pytest tests/unit/research/test_metrics.py tests/unit/strategy/test_evaluation_metrics.py tests/unit/strategy/test_promotion_gates.py tests/property/strategy/test_cost_monotonicity.py -v
uv run pyright
git add src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py src/gemini_trading/strategy/evaluation.py tests/unit/research/test_metrics.py tests/unit/strategy/test_evaluation_metrics.py tests/unit/strategy/test_promotion_gates.py tests/property/strategy/test_cost_monotonicity.py
git commit -m "feat: evaluate strategy economics and promotion gates"
```

---

### Task 8: Walk-Forward Study, Ablations, and Final-Test Seal

**Files:**
- Create: `src/gemini_trading/strategy/study.py`
- Test: `tests/integration/test_strategy_walk_forward_study.py`, `test_strategy_ablation_suite.py`
- Test: `tests/regression/test_final_test_seal.py`

**Interfaces:**
- `FinalTestSeal`, `StrategyStudyEvidence`, `StrategyStudyRunner.run()`

- [ ] **Step 1: Write final-test seal regression**

```python
def test_development_selector_cannot_read_final_test() -> None:
    seal = FinalTestSeal.create(split_plan)
    with pytest.raises(FinalTestSealError, match="final test"):
        DevelopmentSelector(seal).read_predictions(split_plan.final_test)
```

Also assert final evaluation count equals one and any post-seal policy/config change creates a different study ID.

- [ ] **Step 2: Implement each development fold in this order**

1. select training rows/labels;
2. fit trend and eligible mean-reversion models;
3. score calibration rows;
4. fit Platt and expected-return maps;
5. generate forward-test predictions;
6. classify regimes;
7. run candidate, five baselines, standalone specialists, regime-gated simple baselines, no-disagreement, no-volume, no-protection, delayed-feature, and shuffled-label controls through `BacktestEngine`;
8. persist fold evidence, including failures.

- [ ] **Step 3: Implement the final locked fit/test**

After development is complete, seal all structural identities. Fit final specialists using permitted pre-final data, reserve the final six pre-test months for calibration, generate final predictions once, and run candidate/comparators plus:
- costs 1.5x and 2x with decisions unchanged;
- entry thresholds `0.59`, `0.65`;
- exit thresholds `0.42`, `0.48`;
- maximum hold 12, 24;
- initial stop 2.0, 3.0 ATR;
- cooldown 1, 3;
- shuffled labels seed `1799`;
- one-candle delayed features;
- deterministic bootstrap seed `1788`.

Final outputs cannot modify configuration.

- [ ] **Step 4: Run gates and commit**

```bash
uv run pytest tests/integration/test_strategy_walk_forward_study.py tests/integration/test_strategy_ablation_suite.py tests/regression/test_final_test_seal.py -v
uv run pyright
git add src/gemini_trading/strategy/study.py tests/integration/test_strategy_walk_forward_study.py tests/integration/test_strategy_ablation_suite.py tests/regression/test_final_test_seal.py
git commit -m "feat: run sealed multi-model strategy studies"
```

---

### Task 9: Immutable Strategy Study Artifacts

**Files:**
- Create: `src/gemini_trading/strategy/artifacts.py`
- Test: `tests/unit/strategy/test_study_artifacts.py`
- Test: `tests/property/strategy/test_study_result_identity.py`
- Test: `tests/regression/test_tampered_strategy_artifacts.py`

**Interfaces:**
- `StrategyStudyArtifacts`, `build_study_artifacts()`, `LocalStrategyStudyStore`

- [ ] **Step 1: Write the exact required-file test**

```python
REQUIRED_FILES = {
    "study-manifest.json", "policy.json", "feature-registry.json",
    "feature-matrix.jsonl", "labels.jsonl", "split-plan.json",
    "folds.jsonl", "models.jsonl", "calibration.jsonl",
    "predictions.jsonl", "regimes.jsonl", "arbitration-decisions.jsonl",
    "experiments.jsonl", "baselines.json", "ablations.json",
    "negative-controls.json", "cost-stress.json",
    "parameter-sensitivity.json", "bootstrap.json",
    "promotion-gates.json", "limitations.json", "study-result-manifest.json",
}
assert set(artifacts.names) == REQUIRED_FILES
```

- [ ] **Step 2: Build canonical bytes and identity**

Hash every core artifact and derive:

```text
study_result_id = sha256(canonical_json({
  "schema_version": "strategy-study-result-v1",
  "study_id": study_id,
  "artifacts": sorted_artifact_hashes,
  "classification": classification
}))
```

Store under `data/strategy-studies/<study_id>/` with `write_immutable`.

- [ ] **Step 3: Test idempotency and tampering**

Byte-identical rerun succeeds. Any different byte conflicts. Modifying a model, prediction, gate, or experiment reference changes result ID. Missing failed-fold/control evidence prevents artifact construction.

- [ ] **Step 4: Run gates and commit**

```bash
uv run pytest tests/unit/strategy/test_study_artifacts.py tests/property/strategy/test_study_result_identity.py tests/regression/test_tampered_strategy_artifacts.py -v
uv run pyright
git add src/gemini_trading/strategy/artifacts.py tests/unit/strategy/test_study_artifacts.py tests/property/strategy/test_study_result_identity.py tests/regression/test_tampered_strategy_artifacts.py
git commit -m "feat: persist immutable strategy study evidence"
```

---

### Task 10: Provider-Free Replay and Independent Verification

**Files:**
- Create: `src/gemini_trading/strategy/replay.py`, `verification.py`
- Modify: `src/gemini_trading/research/replay.py`, `verification.py`
- Test: `tests/integration/test_strategy_replay_without_network.py`
- Test: `tests/unit/strategy/test_strategy_verification.py`
- Test: `tests/regression/test_strategy_replay_commit_mismatch.py`

**Interfaces:**
- `StrategyStudyReplayService.replay(study_id: str) -> StrategyStudyArtifacts`
- `StrategyStudyVerificationService.verify(study_id: str) -> StrategyStudyVerificationResult`

- [ ] **Step 1: Write network-denial replay test**

```python
def test_strategy_study_replays_without_network(monkeypatch, stored_study) -> None:
    monkeypatch.setattr(socket, "socket", network_forbidden)
    monkeypatch.setattr(BinanceSpotProvider, "__init__", provider_forbidden)
    replayed = stored_study.replay_service.replay(stored_study.study_id)
    assert replayed.study_result_id == stored_study.study_result_id
    assert replayed.files == stored_study.files
```

- [ ] **Step 2: Add a closed reconstruction registry**

Support exactly `fixture.scripted.v1`, `candidate.multi_model.v0_1`, `cash.v1`, `buy_hold.v1`, `ema_20_50.v1`, `donchian_20_10.v1`, and `mean_reversion_z24.v1`. Unknown IDs raise `StudyReplayMismatchError`.

- [ ] **Step 3: Independently verify all boundaries**

Recompute canonical dataset/provenance, every artifact hash, all component/study/result IDs, referenced research experiment artifacts, final-test single-use receipt, complete mandatory gate IDs, exact replay equivalence, and exact code commit. Return safe check names only; no arrays, raw provider bodies, environment dumps, or absolute paths.

- [ ] **Step 4: Run gates and commit**

```bash
uv run pytest tests/integration/test_strategy_replay_without_network.py tests/unit/strategy/test_strategy_verification.py tests/regression/test_strategy_replay_commit_mismatch.py -v
uv run pyright
git add src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/verification.py src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_strategy_replay_without_network.py tests/unit/strategy/test_strategy_verification.py tests/regression/test_strategy_replay_commit_mismatch.py
git commit -m "feat: replay and verify strategy studies"
```

---

### Task 11: Safe CLI and Locked Configuration

**Files:**
- Create: `src/gemini_trading/cli/strategy.py`
- Modify: `src/gemini_trading/cli/main.py`, `cli/research.py`
- Create: `tests/fixtures/strategy/candidate-v0.1-config.json`
- Test: `tests/unit/cli/test_strategy.py`, `tests/acceptance/test_strategy_cli.py`

**Interfaces:**
- `research strategy-evaluate`
- `research strategy-replay`
- `research strategy-verify`

- [ ] **Step 1: Write exact parser and safety tests**

```python
def test_strategy_evaluate_help() -> None:
    result = invoke_cli(["research", "strategy-evaluate", "--help"])
    assert result.exit_code == 0
    assert "--dataset-id" in result.stdout
    assert "--config" in result.stdout


def test_live_mode_fails_before_dataset_or_model_work(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", "live")
    result = invoke_candidate_evaluate()
    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["type"] == "UnsafeExecutionModeError"
```

- [ ] **Step 2: Add exact strict config fixture**

```json
{
  "schema_version": "candidate-strategy-cli-v1",
  "initial_cash": "10000",
  "simulation": {
    "maker_fee_rate": "0.001",
    "taker_fee_rate": "0.001",
    "half_spread_bps": "5",
    "slippage_bps": "10",
    "latency_bars": 0,
    "price_tick": "0.01",
    "quantity_step": "0.000001",
    "min_quantity": "0.000001",
    "min_notional": "5",
    "max_volume_participation": "0.01",
    "max_active_candles": 3,
    "timing_policy": "next_candle",
    "limit_fill_policy": "conservative",
    "default_time_in_force": "bar",
    "promotable": true
  },
  "strategy": {
    "id": "candidate.multi_model.v0_1",
    "policy_version": "candidate-multi-model-v0.1"
  }
}
```

Reject extra fields, changed strategy/policy IDs, zero costs, same-close timing, optimistic fills, or non-research runtime modes.

- [ ] **Step 3: Implement commands and safe output**

Evaluate arguments: `--dataset-id`, `--config`, `--project-root`, `--output-root`. Replay/verify arguments: `--study-id`, `--project-root`, `--output-root`. Evaluate output contains exactly `classification`, `promotable`, `status`, `study_id`, `study_result_id`; `promotable` is false. Failures use compact safe JSON and exit code 2.

- [ ] **Step 4: Run gates and commit**

```bash
uv run pytest tests/unit/cli/test_strategy.py tests/acceptance/test_strategy_cli.py -v
uv run pyright
git add src/gemini_trading/cli/main.py src/gemini_trading/cli/research.py src/gemini_trading/cli/strategy.py tests/fixtures/strategy/candidate-v0.1-config.json tests/unit/cli/test_strategy.py tests/acceptance/test_strategy_cli.py
git commit -m "feat: expose safe strategy study CLI"
```

---

### Task 12: Documentation, Acceptance, and Exact Verification

**Files:**
- Modify: `README.md`
- Create: `docs/operations/candidate-multi-model-strategy.md`
- Create: `docs/operations/candidate-multi-model-strategy-step-verification.md`
- Create: `reports/verification/candidate-multi-model-strategy-progress.md`
- Create: `reports/verification/candidate-multi-model-strategy-final.md`
- Test: `tests/acceptance/test_candidate_strategy_documentation.py`
- Test: `tests/acceptance/test_candidate_strategy_end_to_end.py`

- [ ] **Step 1: Write exact documentation acceptance test**

```python
@pytest.mark.parametrize(
    "required",
    [
        "RESEARCH_ONLY", "BTC/USDT", "4h", "seven years",
        "18 calendar months", "strategy-evaluate", "strategy-replay",
        "strategy-verify", "rejection is a valid outcome",
        "does not establish durable profitability",
    ],
)
def test_operations_document_contains_safety_and_protocol(required: str) -> None:
    text = Path("docs/operations/candidate-multi-model-strategy.md").read_text()
    assert required in text
```

- [ ] **Step 2: Build diagnostic end-to-end acceptance**

Use a deterministic synthetic canonical BTCUSDT H4 dataset that exercises features, labels, splits, both model families, calibration, regimes, candidate/baselines, artifacts, replay, verification, tamper detection, and unsafe-mode rejection. It must classify `INCONCLUSIVE` because synthetic/short history is non-promotable and must never claim edge.

- [ ] **Step 3: Run complete quality/security gates**

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

Expected: every command passes; only intended tracked files differ before commit.

- [ ] **Step 4: Run deterministic acceptance twice**

```bash
export GEMINI_TRADING_MODE=research
uv run pytest tests/acceptance/test_candidate_strategy_end_to_end.py -v
uv run pytest tests/acceptance/test_candidate_strategy_end_to_end.py -v
```

Expected: identical study ID, study result ID, and core artifact hashes.

- [ ] **Step 5: Write final evidence**

The final report must contain exact commit, dependency-lock hash, test counts, acceptance IDs, replay/verification receipts, each mandatory gate with pass/fail/not-evaluated, limitations, whether a real seven-year historical run occurred, and final classification without profitability exaggeration.

- [ ] **Step 6: Commit documentation/evidence**

```bash
git add README.md docs/operations reports/verification tests/acceptance
git commit -m "docs: verify candidate multi-model strategy milestone"
```

- [ ] **Step 7: PR and protected-main verification**

1. fetch exact PR head SHA;
2. pass ordinary CI on that SHA;
3. pass focused deterministic strategy acceptance on that SHA;
4. independently review evidence, failed gates, and limitations;
5. confirm no scope beyond the approved spec;
6. merge through protected main;
7. run a purpose-built exact merged-main verification;
8. close Issue #16 only after implementation and post-merge verification complete.

---

## Plan Self-Review

**Spec coverage:** Tasks 1–3 cover policy, identities, point-in-time features, labels, leakage, and splits. Tasks 4–6 cover models, calibration, regimes, arbitration, risk, and baselines. Tasks 7–8 cover metrics, walk-forward testing, ablations, cost stress, sensitivities, controls, bootstrap, and promotion gates. Tasks 9–12 cover immutable evidence, replay, independent verification, CLI safety, documentation, and exact acceptance.

**Placeholder scan:** No `TBD`, `TODO`, `implement later`, unspecified error handling, unspecified test request, or “similar to” instruction remains.

**Type consistency:** The plan consistently uses `CandidatePolicy`, `FeatureRegistry`, `FeatureMatrix`, `LabelPolicy`, `LabelVector`, `ChronologicalSplitPlan`, `LinearModelArtifact`, `BoostedTreeArtifact`, `PlattArtifact`, `ExpectedReturnMap`, `RegimeObservation`, `MultiModelArbiter`, `CandidateMultiModelStrategy`, `StrategyStudyEvidence`, and `StrategyStudyArtifacts`.

**Scope check:** No task introduces OKX, derivatives, funding, order books, news, geopolitics, on-chain data, cross-assets, deep learning, live execution, leverage, shorting, portfolio allocation, or real-capital authority.
