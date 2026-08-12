# Candidate Multi-Model Strategy v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Candidate v0.3 as a new, independently replayable research candidate whose only substantive strategy change is calibration-only fold-local entry selectivity, while preserving v0.1/v0.2 behavior and all existing fail-closed research controls.

**Architecture:** Keep v0.1 and v0.2 immutable. Add v0.3-specific identity, entry-selectivity artifacts, development split/case planning, qualification evaluation/execution, evidence packaging, CLI/workflow surfaces, and prospective-seal support beside the existing v0.2 implementation. Reuse the validated specialists, calibration, regime classifier, simulator, costs, risk state machine, determinism receipts, baselines, and research verification services without changing their established v0.2 semantics.

**Tech Stack:** Python 3.12, `Decimal`, scikit-learn 1.9.0, NumPy only where already present, threadpoolctl, canonical JSON/JSONL, pytest, Ruff, strict Pyright, GitHub Actions.

## Global Constraints

- Entire milestone remains `RESEARCH_ONLY`.
- No credentials, private exchange endpoints, paper/demo/live order submission, leverage, futures, shorting, portfolio allocation, or capital authority.
- Candidate v0.1 and v0.2 serialized policies, decisions, qualification evidence, and replay behavior must not change.
- v0.3 identity is exactly `candidate.multi_model.v0_3` / `candidate-multi-model-v0.3` / `candidate-strategy-policy-v3`.
- Development data is exactly `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`.
- Trend model remains elastic-net logistic regression with scikit-learn 1.9.0, `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, single thread, `tol=1e-7`, `max_iter=50000`.
- Mean-reversion model, features, labels, regimes, simulator, costs, hold/exit/cooldown/stops, purge/embargo, baselines, and bootstrap contract remain v0.2-equivalent.
- Primary v0.3 entry percentile is exactly `0.75`; effective threshold floor is exactly `0.50`; minimum eligible calibration scores per specialist/fold is exactly `40`.
- Empirical quantiles use deterministic linear interpolation on the sorted eligible calibrated probability vector.
- Companion probability floor `0.45` and disagreement limit `0.25` remain persisted diagnostics but are not v0.3 entry vetoes.
- Expected gross edge must remain strictly above the complete transaction-cost hurdle plus the unchanged extra edge requirement.
- Sensitivity entry neighbors are exactly `0.70` and `0.80`; the `no-percentile-selectivity` ablation uses the fixed `0.50` floor.
- No v0.3 development result may alter the specification. Any redesign after evidence is Candidate v0.4.
- Prospective-final access remains impossible unless complete v0.3 pre-final qualification is `QUALIFIED` and independently verified.
- Every implementation task follows RED -> verify RED -> minimal GREEN -> focused verification -> commit.

---

### Task 1: Add the v0.3 Candidate Identity Without Altering Older Policy Bytes

**Files:**
- Modify: `src/gemini_trading/strategy/policy.py`
- Create: `tests/fixtures/strategy/candidate-v0.3-config.json`
- Modify: `tests/unit/strategy/test_policy.py`
- Modify: `tests/unit/cli/test_candidate_strategy_cli.py`

**Interfaces:**
- Produces: `CandidatePolicy.locked_v0_3() -> CandidatePolicy`
- Extends: `approved_candidate_policy(strategy_id: str, policy_version: str) -> CandidatePolicy`
- Constraint: `serialize_candidate_policy(CandidatePolicy.locked_v0_1())` and v0.2 bytes remain byte-identical to their pre-v0.3 values.

- [ ] **Step 1: Write RED identity and regression tests**

```python
def test_locked_v0_3_changes_only_candidate_identity_from_v0_2() -> None:
    old = CandidatePolicy.locked_v0_2()
    new = CandidatePolicy.locked_v0_3()
    assert new.strategy_id == "candidate.multi_model.v0_3"
    assert new.policy_version == "candidate-multi-model-v0.3"
    assert new.schema_version == "candidate-strategy-policy-v3"
    differing = {
        name
        for name in old.__dataclass_fields__
        if getattr(old, name) != getattr(new, name)
    }
    assert differing == {"schema_version", "strategy_id", "policy_version"}
```

Also freeze the current v0.1 and v0.2 serialized-policy SHA-256 values in regression assertions before adding v0.3.

Run: `uv run pytest tests/unit/strategy/test_policy.py -v`
Expected: FAIL because `locked_v0_3()` is absent.

- [ ] **Step 2: Implement the v0.3 identity as a replace over v0.2**

```python
@classmethod
def locked_v0_3(cls) -> "CandidatePolicy":
    return replace(
        cls.locked_v0_2(),
        schema_version="candidate-strategy-policy-v3",
        strategy_id="candidate.multi_model.v0_3",
        policy_version="candidate-multi-model-v0.3",
    )
```

Extend `approved_candidate_policy()` with only the exact v0.3 identity pair. Do not add percentile fields to `CandidatePolicy`; doing so would change v0.1/v0.2 serialized policy bytes.

- [ ] **Step 3: Add the v0.3 strategy fixture and loader coverage**

Create `tests/fixtures/strategy/candidate-v0.3-config.json` from the locked v0.2 fixture, changing only the strategy identity pair. Assert arbitrary `v0_3`/policy mismatches fail closed.

- [ ] **Step 4: Verify GREEN and old-policy byte stability**

```bash
uv run pytest tests/unit/strategy/test_policy.py tests/unit/cli/test_candidate_strategy_cli.py -v
uv run pyright src/gemini_trading/strategy/policy.py tests/unit/strategy/test_policy.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/policy.py tests/fixtures/strategy/candidate-v0.3-config.json tests/unit/strategy/test_policy.py tests/unit/cli/test_candidate_strategy_cli.py
git commit -m "feat: define Candidate v0.3 identity"
```

---

### Task 2: Build Deterministic Calibration-Only Entry Selectivity Artifacts

**Files:**
- Create: `src/gemini_trading/strategy/entry_selectivity.py`
- Create: `tests/unit/strategy/test_entry_selectivity.py`

**Interfaces:**
- Produces: `EntrySelectivityPolicy.locked_v0_3() -> EntrySelectivityPolicy`
- Produces: `EntryThresholdArtifact`
- Produces: `linear_quantile(values: tuple[Decimal, ...], percentile: Decimal) -> Decimal`
- Produces: `build_entry_threshold_artifact(...) -> EntryThresholdArtifact`

- [ ] **Step 1: Write RED quantile tests including ties and interpolation**

```python
def test_linear_quantile_uses_n_minus_one_position() -> None:
    values = tuple(Decimal(str(value)) for value in (0.1, 0.2, 0.3, 0.8, 0.9))
    assert linear_quantile(values, Decimal("0.75")) == Decimal("0.8")


def test_effective_threshold_has_hold_floor() -> None:
    artifact = build_entry_threshold_artifact(...)
    assert artifact.raw_quantile < Decimal("0.50")
    assert artifact.effective_threshold == Decimal("0.50")
```

Add exact tests for duplicate/tied scores, non-finite values, percentile outside `[0,1]`, fewer than 40 eligible scores, and input order invariance after deterministic sort.

Run: `uv run pytest tests/unit/strategy/test_entry_selectivity.py -v`
Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement the frozen adjunct selectivity policy**

```python
@dataclass(frozen=True, slots=True)
class EntrySelectivityPolicy:
    schema_version: str
    primary_percentile: Decimal
    threshold_floor: Decimal
    minimum_eligible_scores: int
    sensitivity_percentiles: tuple[Decimal, Decimal]

    @classmethod
    def locked_v0_3(cls) -> "EntrySelectivityPolicy":
        return cls(
            schema_version="candidate-v0.3-entry-selectivity-v1",
            primary_percentile=Decimal("0.75"),
            threshold_floor=Decimal("0.50"),
            minimum_eligible_scores=40,
            sensitivity_percentiles=(Decimal("0.70"), Decimal("0.80")),
        )
```

Keep this policy separate from `CandidatePolicy` and bind its canonical bytes into the v0.3 qualification identity later.

- [ ] **Step 3: Implement exact linear interpolation and artifact hashing**

For `n` sorted values and percentile `p`, compute `position = (n - 1) * p`, interpolate between floor/ceiling indexes using `Decimal`, and persist:

```python
@dataclass(frozen=True, slots=True)
class EntryThresholdArtifact:
    schema_version: str
    fold_number: int
    specialist: SpecialistKind
    percentile: Decimal
    eligible_indices: tuple[int, ...]
    eligible_scores: tuple[Decimal, ...]
    eligible_rows_sha256: str
    score_vector_sha256: str
    raw_quantile: Decimal
    effective_threshold: Decimal
    quantile_method: str
```

Use canonical JSON bytes for identities. Reject fewer than 40 eligible rows.

- [ ] **Step 4: Implement regime/stret​ch eligibility from calibration rows only**

`build_entry_threshold_artifact()` must classify each calibration index with the unchanged `RegimeClassifier(policy)`. Trend eligibility is `TRENDING`; mean-reversion eligibility is `RANGING` plus the existing stretch predicate (`close_zscore_24 <= -0.75` or `drawdown_from_high_24 >= 0.02`). The function must never accept development-test indexes as an input source.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_entry_selectivity.py -v
uv run ruff check src/gemini_trading/strategy/entry_selectivity.py tests/unit/strategy/test_entry_selectivity.py
uv run pyright src/gemini_trading/strategy/entry_selectivity.py tests/unit/strategy/test_entry_selectivity.py
git add src/gemini_trading/strategy/entry_selectivity.py tests/unit/strategy/test_entry_selectivity.py
git commit -m "feat: add v0.3 calibration entry selectivity"
```

---

### Task 3: Add a Backward-Compatible Arbitration Overlay

**Files:**
- Modify: `src/gemini_trading/strategy/arbitration.py`
- Modify: `tests/unit/strategy/test_arbitration.py`

**Interfaces:**
- Produces: `ArbitrationOverlay`
- Extends: `MultiModelArbiter.decide(source: ArbitrationInput, overlay: ArbitrationOverlay | None = None) -> ArbitrationDecision`
- Old callers: no overlay, byte/decision-equivalent v0.1/v0.2 behavior.

- [ ] **Step 1: Write RED tests for diagnostic-only companion/disagreement**

Create a cash-state `TRENDING` source where active trend probability and expected edge pass, companion probability is below `0.45`, and disagreement exceeds `0.25`.

```python
overlay = ArbitrationOverlay(
    entry_probability_threshold=Decimal("0.58"),
    enforce_companion_probability=False,
    enforce_disagreement=False,
)
assert MultiModelArbiter(policy).decide(source, overlay).action is StrategyAction.ENTER_LONG
assert MultiModelArbiter(policy).decide(source).action is StrategyAction.REMAIN_IN_CASH
```

Also assert expected-edge failure still vetoes entry and hold/exit/risk decisions are identical with or without the v0.3 overlay once already long.

- [ ] **Step 2: Implement `ArbitrationOverlay` with old behavior as defaults**

```python
@dataclass(frozen=True, slots=True)
class ArbitrationOverlay:
    entry_probability_threshold: Decimal | None = None
    enforce_companion_probability: bool = True
    enforce_disagreement: bool = True
```

`_decide_cash()` uses the overlay threshold when present; otherwise it uses `policy.entry_probability`. Skip only the companion and disagreement veto checks when their overlay flags are false. Do not change regime, stretch, expected-edge, stop-validity, cooldown, or position-state logic.

- [ ] **Step 3: Add old-decision regression vectors**

Run existing v0.1/v0.2 arbitration fixtures through `decide(source)` and assert their exact actions/reasons are unchanged.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_arbitration.py -v
uv run pyright src/gemini_trading/strategy/arbitration.py tests/unit/strategy/test_arbitration.py
uv run ruff check src/gemini_trading/strategy/arbitration.py tests/unit/strategy/test_arbitration.py
git add src/gemini_trading/strategy/arbitration.py tests/unit/strategy/test_arbitration.py
git commit -m "feat: add v0.3 arbitration overlay"
```

---

### Task 4: Produce v0.3 Prediction Contexts and Schedules Without Changing v0.2 Bundles

**Files:**
- Create: `src/gemini_trading/strategy/v0_3_predictions.py`
- Modify: `src/gemini_trading/strategy/study_predictions.py`
- Create: `tests/unit/strategy/test_v0_3_predictions.py`
- Modify: `tests/unit/strategy/test_study_predictions.py`

**Interfaces:**
- Produces: `V03PredictionContext`
- Produces: `fit_v0_3_prediction_context(...) -> V03PredictionContext`
- Extends: `candidate_events(..., entry_thresholds: Mapping[SpecialistKind, Decimal] | None = None, companion_disagreement_diagnostic_only: bool = False)`

- [ ] **Step 1: Write RED context tests**

Assert one fold context contains the existing `PredictionBundle`, unchanged `TrendDeterminismReceipt`, primary q75 threshold artifact for each specialist, and q70/q80 threshold artifacts needed by sensitivity cases. Recomputing the context from identical inputs must produce identical canonical threshold artifact bytes.

- [ ] **Step 2: Build threshold artifacts by recomputing only calibration probabilities**

`fit_v0_3_prediction_context()` first calls the existing `fit_verified_prediction_bundle()` unchanged. For each calibration index, recompute raw specialist score using the fitted model, apply the fitted Platt artifact, then build q70/q75/q80 artifacts using `entry_selectivity.py`. Do not add calibration vectors to `PredictionBundle`, because that would change established v0.2 deterministic bundle identities.

- [ ] **Step 3: Extend `candidate_events()` through optional arguments only**

When `entry_thresholds` is `None`, preserve exact old behavior. When supplied, choose the active threshold by current regime (`TREND` for `TRENDING`, `MEAN_REVERSION` for eligible `RANGING`) and call `MultiModelArbiter.decide()` with an `ArbitrationOverlay`. Set both companion/disagreement enforcement flags to `False` only when `companion_disagreement_diagnostic_only=True`.

- [ ] **Step 4: Add schedule tests**

Prove:
- q75 can admit a trade rejected by fixed `0.62` when all remaining v0.3 gates pass;
- companion/disagreement no longer veto v0.3;
- expected-edge remains a veto;
- mean reversion still requires ranging stretch;
- segment-gap cash resets remain intact;
- calling `candidate_events()` without new options reproduces existing v0.2 schedules exactly.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_v0_3_predictions.py tests/unit/strategy/test_study_predictions.py -v
uv run ruff check src/gemini_trading/strategy/v0_3_predictions.py src/gemini_trading/strategy/study_predictions.py tests/unit/strategy/test_v0_3_predictions.py tests/unit/strategy/test_study_predictions.py
uv run pyright src/gemini_trading/strategy/v0_3_predictions.py src/gemini_trading/strategy/study_predictions.py
git add src/gemini_trading/strategy/v0_3_predictions.py src/gemini_trading/strategy/study_predictions.py tests/unit/strategy/test_v0_3_predictions.py tests/unit/strategy/test_study_predictions.py
git commit -m "feat: build v0.3 calibrated prediction schedules"
```

---

### Task 5: Add the Immutable v0.3 Development Split Plan

**Files:**
- Create: `src/gemini_trading/strategy/v0_3_splits.py`
- Create: `tests/unit/strategy/test_v0_3_development_splits.py`

**Interfaces:**
- Produces: `V03DevelopmentQualificationPlan.build(...) -> V03DevelopmentQualificationPlan`
- Preserves: existing `DevelopmentQualificationPlan` v0.2 schema and serialized bytes.

- [ ] **Step 1: Write RED fixed-window tests**

Use completed 4h candles covering exactly `[2018-01-01, 2026-08-01)` and verified segment boundaries.

```python
plan = V03DevelopmentQualificationPlan.build(
    candles,
    eligible_indices,
    CandidatePolicy.locked_v0_3(),
    segment_manifest,
)
assert plan.dataset_start_time == datetime(2018, 1, 1, tzinfo=UTC)
assert plan.dataset_end_exclusive == datetime(2026, 8, 1, tzinfo=UTC)
assert tuple(f.fold_number for f in plan.folds) == tuple(range(1, 13))
```

Assert the one-month tail after the last complete six-month development test is not silently turned into a partial fold.

- [ ] **Step 2: Implement v0.3 plan beside v0.2**

Use the same `_safe_indices`, purge/embargo, label-exit-offset, month arithmetic, and protected segment-boundary rules as `DevelopmentQualificationPlan`, but require the exact v0.3 identity and cutoff. Schema: `candidate-v0.3-development-qualification-plan-v1`.

- [ ] **Step 3: Add leakage and old-plan regressions**

Assert no training/calibration/development label crosses fold/segment boundaries, all fold windows are ordered, and existing v0.2 split tests remain byte/behavior stable.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_v0_3_development_splits.py tests/unit/strategy/test_v0_2_development_splits.py -v
uv run pyright src/gemini_trading/strategy/v0_3_splits.py tests/unit/strategy/test_v0_3_development_splits.py
uv run ruff check src/gemini_trading/strategy/v0_3_splits.py tests/unit/strategy/test_v0_3_development_splits.py
git add src/gemini_trading/strategy/v0_3_splits.py tests/unit/strategy/test_v0_3_development_splits.py
git commit -m "feat: add v0.3 development split plan"
```

---

### Task 6: Define v0.3 Qualification Cases, Percentile Sensitivity, and Ablations

**Files:**
- Create: `src/gemini_trading/strategy/v0_3_cases.py`
- Create: `src/gemini_trading/strategy/v0_3_study_plans.py`
- Create: `tests/unit/strategy/test_v0_3_study_plans.py`

**Interfaces:**
- Produces: `V03_QUALIFICATION_CASE_IDS`
- Produces: `prepare_v0_3_phase(...) -> None`

- [ ] **Step 1: Write RED exact-case inventory test**

Required v0.3 qualification inventory must include the primary candidate, unchanged simple/specialist baselines, cost cases, exit/max-hold/stop/cooldown sensitivities, `sensitivity.entry_percentile_0_70`, `sensitivity.entry_percentile_0_80`, shuffled/delayed controls, `ablation.no_percentile_selectivity.v1`, no-volume, no-protection, and bootstrap case. It must not include `ablation.no_disagreement.v1` or fixed entry `0.59/0.65` variants.

- [ ] **Step 2: Implement v0.3 phase preparation**

Primary events use q75 thresholds. The q70/q80 variants use their calibration-only artifacts. `ablation.no_percentile_selectivity.v1` uses per-specialist threshold `0.50` with companion/disagreement still diagnostic-only. Other sensitivity and control cases reuse existing policy replacements and simulation-cost multipliers unchanged.

- [ ] **Step 3: Persist diagnostic distributions**

For each fold, produce canonical diagnostics containing the companion probability distribution and absolute trend/mean probability disagreement distribution over development decision rows. These are evidence only and never gates or threshold inputs.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_v0_3_study_plans.py -v
uv run ruff check src/gemini_trading/strategy/v0_3_cases.py src/gemini_trading/strategy/v0_3_study_plans.py tests/unit/strategy/test_v0_3_study_plans.py
uv run pyright src/gemini_trading/strategy/v0_3_cases.py src/gemini_trading/strategy/v0_3_study_plans.py
git add src/gemini_trading/strategy/v0_3_cases.py src/gemini_trading/strategy/v0_3_study_plans.py tests/unit/strategy/test_v0_3_study_plans.py
git commit -m "feat: define v0.3 qualification cases"
```

---

### Task 7: Implement the v0.3 Pre-Final Qualification Gate Set

**Files:**
- Create: `src/gemini_trading/strategy/qualification_v0_3.py`
- Create: `tests/unit/strategy/test_qualification_v0_3.py`

**Interfaces:**
- Produces: `V03QualificationEvidence`
- Produces: `V03QualificationReport`
- Produces: `evaluate_v0_3_development_qualification(...) -> V03QualificationReport`

- [ ] **Step 1: Write RED fixed gate-order tests**

Use a separate v0.3 gate tuple so v0.2 remains unchanged. Gate order is:

```python
V03_QUALIFICATION_GATE_IDS = (
    "integrity.verified",
    "convergence.trend_determinism",
    "calibration.complete",
    "selectivity.replay",
    "development.fold_count",
    "development.positive_return_folds",
    "development.baseline_rtd_folds",
    "development.profit_concentration",
    "development.trade_count",
    "control.shuffled_labels",
    "control.delayed_features",
    "control.no_percentile_selectivity",
    "control.no_volume",
    "control.no_protection",
    "cost.one_half_return",
    "cost.one_half_drawdown",
    "cost.double_return",
    "cost.double_drawdown",
    "cost.monotonicity",
    "sensitivity.positive_neighbors",
    "sensitivity.median_return",
    "sensitivity.drawdown",
    "sensitivity.primary_stability",
    "uncertainty.bootstrap_median",
    "uncertainty.bootstrap_lower_bound",
    "replay.verified",
    "independent.verified",
)
```

Explicit valid evidence failure => `REJECTED`; missing/ambiguous evidence without explicit failure => `INCONCLUSIVE`; all gates pass => `QUALIFIED`.

- [ ] **Step 2: Implement exact unchanged economic thresholds**

Apply: at least 60% positive folds, at least 60% baseline RTD wins, <=50% positive-profit concentration, >=60 completed trades, 1.5x return >0/DD <=0.275, 2x return >=-0.05/DD <=0.30, monotonic costs, >=7/10 positive neighbors, positive sensitivity median, <=0.35 max neighbor drawdown, existing primary stability rule, bootstrap median >0 and p05 >-0.02.

- [ ] **Step 3: Implement the new component gate**

`control.no_percentile_selectivity` passes only when the `0.50` ablation does **not** improve RTD by at least 10% while maximum drawdown is no higher than primary. Undefined required ratios fail closed exactly as in v0.2 component evaluation.

- [ ] **Step 4: Implement selectivity replay gate**

The gate passes only when every expected fold/specialist q75 artifact independently reproduces the same eligible row identity, score vector identity, raw quantile, effective threshold, and canonical bytes. Missing q70/q80 artifacts make sensitivity evidence incomplete and therefore `INCONCLUSIVE` unless another complete mandatory gate already explicitly fails.

- [ ] **Step 5: Verify v0.2 isolation and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification_v0_3.py tests/unit/strategy/test_qualification.py -v
uv run pyright src/gemini_trading/strategy/qualification_v0_3.py tests/unit/strategy/test_qualification_v0_3.py
uv run ruff check src/gemini_trading/strategy/qualification_v0_3.py tests/unit/strategy/test_qualification_v0_3.py
git add src/gemini_trading/strategy/qualification_v0_3.py tests/unit/strategy/test_qualification_v0_3.py
git commit -m "feat: add v0.3 qualification gates"
```

---

### Task 8: Execute and Package the Complete v0.3 Qualification

**Files:**
- Create: `src/gemini_trading/strategy/qualification_execution_v0_3.py`
- Create: `src/gemini_trading/strategy/qualification_artifacts_v0_3.py`
- Create: `src/gemini_trading/strategy/qualification_verification_v0_3.py`
- Create: `tests/unit/strategy/test_qualification_execution_v0_3.py`
- Create: `tests/unit/strategy/test_qualification_artifacts_v0_3.py`
- Create: `tests/unit/strategy/test_qualification_verification_v0_3.py`
- Create: `tests/integration/test_candidate_v0_3_qualification.py`

**Interfaces:**
- Produces: `execute_candidate_v0_3_qualification(...) -> V03QualificationRun`
- Produces: immutable v0.3 qualification artifact directory/manifest
- Produces: provider-free `verify_candidate_v0_3_qualification(...)`

- [ ] **Step 1: Write RED orchestration tests**

Assert exact v0.3 policy/selectivity identities, exact dataset cutoff, no prospective-final construction, every complete fold executed, q70/q75/q80 artifacts present, all controls/cost/sensitivity/bootstrap cases present, and qualification classification sourced only from `qualification_v0_3.py`.

- [ ] **Step 2: Implement execution beside v0.2**

Follow the established v0.2 `qualification_execution.py` flow but use `V03DevelopmentQualificationPlan`, `fit_v0_3_prediction_context`, `prepare_v0_3_phase`, and `evaluate_v0_3_development_qualification`. Bind canonical bytes/hashes for:

```text
CandidatePolicy.locked_v0_3()
EntrySelectivityPolicy.locked_v0_3()
V03DevelopmentQualificationPlan
simulation configuration
Stage 1 dataset/handoff identity
all threshold artifacts and diagnostics
all case evidence
bootstrap sampled-start identity
```

- [ ] **Step 3: Implement version-isolated artifact packaging**

Schema roots must be v0.3-specific, e.g. `candidate-v0.3-qualification-result-v1`; do not change existing v0.2 manifest schemas. The artifact inventory includes byte size and SHA-256 for every file.

- [ ] **Step 4: Implement provider-free verification**

Reload only portable artifact contents and recompute policy/selectivity/split/threshold/case/bootstrap/report identities. Recompute q75 artifacts from persisted calibration evidence without an exchange provider. Tampering any threshold score, quantile, case evidence, or report classification must fail verification.

- [ ] **Step 5: Run bounded integration qualification**

Use fixture-sized data and patched minimum counts only for test runtime; do not alter locked production policy values. Assert no final rows/provider exist and a complete explicit failed gate produces `REJECTED` rather than an exception.

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification_execution_v0_3.py tests/unit/strategy/test_qualification_artifacts_v0_3.py tests/unit/strategy/test_qualification_verification_v0_3.py tests/integration/test_candidate_v0_3_qualification.py -v
uv run pyright src/gemini_trading/strategy/qualification_execution_v0_3.py src/gemini_trading/strategy/qualification_artifacts_v0_3.py src/gemini_trading/strategy/qualification_verification_v0_3.py
uv run ruff check src/gemini_trading/strategy/qualification_execution_v0_3.py src/gemini_trading/strategy/qualification_artifacts_v0_3.py src/gemini_trading/strategy/qualification_verification_v0_3.py tests/unit/strategy/test_qualification_execution_v0_3.py tests/unit/strategy/test_qualification_artifacts_v0_3.py tests/unit/strategy/test_qualification_verification_v0_3.py tests/integration/test_candidate_v0_3_qualification.py
git add src/gemini_trading/strategy/qualification_execution_v0_3.py src/gemini_trading/strategy/qualification_artifacts_v0_3.py src/gemini_trading/strategy/qualification_verification_v0_3.py tests/unit/strategy/test_qualification_execution_v0_3.py tests/unit/strategy/test_qualification_artifacts_v0_3.py tests/unit/strategy/test_qualification_verification_v0_3.py tests/integration/test_candidate_v0_3_qualification.py
git commit -m "feat: execute and verify v0.3 qualification"
```

---

### Task 9: Add v0.3 CLI and Governed GitHub Qualification Workflow

**Files:**
- Create: `src/gemini_trading/cli/candidate_v0_3.py`
- Modify: `src/gemini_trading/cli/main.py`
- Create: `.github/workflows/candidate-v0.3-qualification.yml`
- Create: `tests/integration/test_candidate_v0_3_cli.py`
- Create: `tests/acceptance/test_candidate_v0_3_workflow.py`

**Interfaces:**
- Produces CLI commands: `strategy-v0-3-qualify`, `strategy-v0-3-verify-qualification`, `strategy-v0-3-create-prospective-seal`
- Workflow consumes only exact merged-main SHA, fresh Stage 1 artifact identity, dataset identity, and one owner-authored Issue #69 approval marker.

- [ ] **Step 1: Write RED CLI/workflow acceptance tests**

Assert command registration, exact identity validation, `RESEARCH_ONLY` output, no order/exchange-private commands, workflow `workflow_dispatch` only, `permissions` least privilege, exact-main guard, Stage 1 source/dataset guard, owner approval marker guard, and no prospective-final evaluation step.

- [ ] **Step 2: Implement v0.3 CLI surfaces**

Mirror v0.2 argument hygiene but call only v0.3 execution/verification/seal modules. Reject v0.2 artifact schemas, wrong cutoff, wrong source commit, or a `REJECTED`/`INCONCLUSIVE` qualification for seal creation.

- [ ] **Step 3: Implement qualification workflow**

Workflow stages:

```text
checkout exact main
uv sync --all-groups --frozen
verify clean source + exact source SHA
verify Issue #69 owner approval marker
download exact fresh Stage 1 artifact
verify Stage 1 handoff/source/dataset/cutoff
run strategy-v0-3-qualify
run strategy-v0-3-verify-qualification
upload portable qualification artifact
```

No workflow step creates a prospective seal automatically.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/integration/test_candidate_v0_3_cli.py tests/acceptance/test_candidate_v0_3_workflow.py -v
uv run pyright src/gemini_trading/cli/candidate_v0_3.py src/gemini_trading/cli/main.py
uv run ruff check src/gemini_trading/cli/candidate_v0_3.py src/gemini_trading/cli/main.py tests/integration/test_candidate_v0_3_cli.py tests/acceptance/test_candidate_v0_3_workflow.py
git add src/gemini_trading/cli/candidate_v0_3.py src/gemini_trading/cli/main.py .github/workflows/candidate-v0.3-qualification.yml tests/integration/test_candidate_v0_3_cli.py tests/acceptance/test_candidate_v0_3_workflow.py
git commit -m "feat: add governed v0.3 qualification workflow"
```

---

### Task 10: Add v0.3 Prospective Seal Support Without Accessing Final Data

**Files:**
- Create: `src/gemini_trading/strategy/prospective_seal_v0_3.py`
- Create: `tests/unit/strategy/test_prospective_seal_v0_3.py`

**Interfaces:**
- Produces: `create_v0_3_prospective_seal(...)`
- Consumes only an independently verified `QUALIFIED` v0.3 qualification artifact and observed verification timestamp.

- [ ] **Step 1: Write RED seal tests**

Assert `REJECTED` and `INCONCLUSIVE` artifacts cannot seal; wrong candidate/selectivity/dataset/source identities cannot seal; the verification timestamp cannot be supplied as a backdated performance choice; the final starts at the first UTC month boundary strictly after successful verification and lasts exactly 18 calendar months.

- [ ] **Step 2: Implement v0.3-specific seal schema**

Bind source SHA, dataset ID, v0.3 policy SHA, entry-selectivity policy SHA, qualification ID/inventory root, development cutoff `2026-08-01T00:00:00Z`, bridge interval, final start, and final end. Do not read, predict, simulate, or materialize any prospective-final market row.

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_prospective_seal_v0_3.py tests/unit/strategy/test_prospective_seal.py tests/unit/strategy/test_prospective_final.py -v
uv run pyright src/gemini_trading/strategy/prospective_seal_v0_3.py tests/unit/strategy/test_prospective_seal_v0_3.py
uv run ruff check src/gemini_trading/strategy/prospective_seal_v0_3.py tests/unit/strategy/test_prospective_seal_v0_3.py
git add src/gemini_trading/strategy/prospective_seal_v0_3.py tests/unit/strategy/test_prospective_seal_v0_3.py
git commit -m "feat: add v0.3 prospective seal contract"
```

---

### Task 11: Document Operations, Freeze Acceptance Contracts, and Run Full Verification

**Files:**
- Create: `docs/operations/candidate-multi-model-strategy-v0-3.md`
- Create: `docs/operations/candidate-multi-model-strategy-v0-3-step-verification.md`
- Modify: `README.md`
- Create: `tests/acceptance/test_candidate_v0_3_documentation.py`
- Modify as required by repository policy: tracked-file allowlists or documentation indexes only if tests demonstrate they are required.

**Interfaces:**
- Produces: exact operator procedure for implementation merge -> exact-main CI -> fresh Stage 1 -> independent verification -> Issue #69 approval marker -> single governed qualification -> independent qualification verification -> optional seal only on `QUALIFIED`.

- [ ] **Step 1: Write RED documentation-contract test**

Assert documentation contains exact values/tokens:

```text
candidate.multi_model.v0_3
candidate-multi-model-v0.3
2026-08-01T00:00:00Z
q75
0.50
40 eligible calibration scores
q70
q80
no-percentile-selectivity
RESEARCH_ONLY
QUALIFIED
REJECTED
INCONCLUSIVE
no prospective-final performance peeks
```

- [ ] **Step 2: Write operations documentation**

Document the exact no-rescue rule, Stage 1 freshness requirement, approval marker format, qualification workflow inputs, artifact verification, prospective sealing boundary, and explicit absence of execution/capital authority.

- [ ] **Step 3: Run focused v0.3 suite**

```bash
uv run pytest \
  tests/unit/strategy/test_entry_selectivity.py \
  tests/unit/strategy/test_v0_3_predictions.py \
  tests/unit/strategy/test_v0_3_development_splits.py \
  tests/unit/strategy/test_v0_3_study_plans.py \
  tests/unit/strategy/test_qualification_v0_3.py \
  tests/unit/strategy/test_qualification_execution_v0_3.py \
  tests/unit/strategy/test_qualification_artifacts_v0_3.py \
  tests/unit/strategy/test_qualification_verification_v0_3.py \
  tests/unit/strategy/test_prospective_seal_v0_3.py \
  tests/integration/test_candidate_v0_3_qualification.py \
  tests/integration/test_candidate_v0_3_cli.py \
  tests/acceptance/test_candidate_v0_3_workflow.py \
  tests/acceptance/test_candidate_v0_3_documentation.py -v
```

Expected: PASS.

- [ ] **Step 4: Run v0.1/v0.2 regression suite**

```bash
uv run pytest \
  tests/unit/strategy/test_policy.py \
  tests/unit/strategy/test_arbitration.py \
  tests/unit/strategy/test_study_predictions.py \
  tests/unit/strategy/test_v0_2_development_splits.py \
  tests/unit/strategy/test_qualification.py \
  tests/unit/strategy/test_qualification_execution.py \
  tests/unit/strategy/test_qualification_artifacts.py \
  tests/unit/strategy/test_qualification_verification.py \
  tests/integration/test_candidate_v0_2_qualification.py \
  tests/integration/test_candidate_v0_2_cli.py \
  tests/acceptance/test_candidate_v0_2_workflow.py -v
```

Expected: PASS with unchanged v0.1/v0.2 identities and outcomes.

- [ ] **Step 5: Run complete repository verification**

```bash
uv run ruff format --check --diff .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
```

Then run the repository's tracked-file policy, detect-secrets scan, and Gitleaks exactly as `.github/workflows/ci.yml` defines them. Every check must pass on the exact implementation head before review/merge.

- [ ] **Step 6: Review exact diff and commit documentation**

```bash
git diff --check
git status --short
git diff --stat main...HEAD
git diff main...HEAD
git add README.md docs/operations/candidate-multi-model-strategy-v0-3.md docs/operations/candidate-multi-model-strategy-v0-3-step-verification.md tests/acceptance/test_candidate_v0_3_documentation.py
git commit -m "docs: add Candidate v0.3 operations contract"
```

---

### Task 12: Protected Integration and Pre-Qualification Gate

**Files:**
- No new production behavior unless exact CI/review evidence requires a defect correction through a new RED/GREEN cycle.
- Issue: `#69`
- PR: implementation PR created from the approved design/plan baseline.

**Interfaces:**
- Produces: exact protected merged-main v0.3 source SHA eligible for a fresh Stage 1 dataset.

- [ ] **Step 1: Request code review on the exact implementation head**

Review specifically for v0.1/v0.2 drift, calibration leakage, threshold provenance, diagnostic-only companion/disagreement behavior, expected-edge preservation, case inventory correctness, artifact tamper coverage, and absence of final/execution authority.

- [ ] **Step 2: Re-run full exact-head CI after the final review commit**

Do not rely on a green run from an earlier SHA.

- [ ] **Step 3: Merge only when exact head is fully green and review-complete**

Use protected/squash merge and record the resulting merged-main SHA on Issue #69.

- [ ] **Step 4: Verify exact merged-main CI**

No Stage 1 dispatch before complete merged-main CI success.

- [ ] **Step 5: Generate one fresh v0.3 Stage 1 dataset from exact merged source**

The requested historical window is exactly `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`. Do not reuse the v0.2 Stage 1 artifact.

- [ ] **Step 6: Independently verify Stage 1 and record owner approval on Issue #69**

Bind exact source SHA, Stage 1 run ID, artifact identity/hash, dataset ID, inventory root, candle count, closure/exclusion/segment evidence, and independent verification result.

- [ ] **Step 7: Dispatch exactly one governed v0.3 development qualification**

Only after the fresh approval marker exists. Do not dispatch a second run to seek a better result.

- [ ] **Step 8: Apply terminal semantics**

- `QUALIFIED`: independently verify the qualification artifact, then and only then create the v0.3 prospective seal.
- `REJECTED`: terminal v0.3 rejection; no tuning/retry; any redesign is v0.4.
- `INCONCLUSIVE`: investigate only missing/invalid infrastructure or evidence; do not change candidate rules.

No outcome grants trading or capital authority.
