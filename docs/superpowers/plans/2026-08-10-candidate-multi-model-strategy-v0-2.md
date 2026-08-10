# Candidate Multi-Model Strategy v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Candidate v0.2 numerical contract, strict development-only qualification, immutable qualification evidence, and prospective 18-month final-window seal without accessing future-final rows.

**Architecture:** Preserve Candidate v0.1 unchanged and add versioned v0.2 policy and qualification surfaces beside it. A dedicated development-only split plan consumes the fixed `[2018-01-01, 2026-07-01)` dataset, a qualification evaluator applies all pre-final convergence/stability/control/robustness/uncertainty gates, and an immutable operational seal calculates the future 18-month window only after a verified `QUALIFIED` result. Existing market-data, simulator, research-artifact, replay, and safety boundaries remain authoritative.

**Tech Stack:** Python 3.12, `Decimal`, NumPy, scikit-learn 1.9.0, threadpoolctl, pytest, Ruff, strict Pyright, canonical JSON/JSONL, immutable local storage, GitHub Actions.

## Global Constraints

- Runtime and workflow authority remain `RESEARCH_ONLY`.
- No credentials, private exchange endpoints, order submission, leverage, futures, shorting, portfolio allocation, or real-capital authority.
- v0.1 behavior and immutable rejection evidence must remain unchanged.
- v0.2 strategy identity is `candidate.multi_model.v0_2`; policy identity is `candidate-multi-model-v0.2`.
- v0.2 trend model keeps elastic-net logistic regression, scikit-learn 1.9.0, `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, and single-thread execution.
- v0.2 convergence contract is exactly `tol=1e-7`, `max_iter=50000`, and convergence only strictly before the ceiling.
- Development data is exactly `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
- The fixed development calendar must produce all 12 complete expanding walk-forward folds; no fold may be omitted.
- The prospective final era starts at the first UTC calendar-month boundary strictly after successful frozen-source/pre-final verification and lasts exactly 18 calendar months.
- `[2026-07-01T00:00:00Z, prospective_final_start)` is quarantined bridge data.
- Once development evidence is observed, no performance-driven v0.2 rescue is permitted; redesign creates v0.3.
- Every implementation task follows RED -> GREEN -> focused verification -> commit.

---

### Task 1: Versioned Candidate v0.2 Policy and CLI Identity

**Files:**
- Modify: `src/gemini_trading/strategy/policy.py`
- Modify: `src/gemini_trading/cli/strategy.py`
- Create: `tests/fixtures/strategy/candidate-v0.2-config.json`
- Modify: `tests/unit/strategy/test_policy.py`
- Test: `tests/unit/cli/test_candidate_strategy_cli.py`

**Interfaces:**
- Produces: `CandidatePolicy.locked_v0_2() -> CandidatePolicy`
- Produces: `approved_candidate_policy(strategy_id: str, policy_version: str) -> CandidatePolicy`
- Consumes later: exact `strategy_id`, `policy_version`, `trend_max_iterations`, and `trend_tolerance`.

- [ ] **Step 1: Add RED policy assertions**

```python
def test_locked_v0_2_changes_only_approved_identity_and_convergence() -> None:
    old = CandidatePolicy.locked_v0_1()
    new = CandidatePolicy.locked_v0_2()
    assert new.strategy_id == "candidate.multi_model.v0_2"
    assert new.policy_version == "candidate-multi-model-v0.2"
    assert new.schema_version == "candidate-strategy-policy-v2"
    assert new.trend_max_iterations == 50_000
    assert new.trend_tolerance == Decimal("0.0000001")
    differing = {
        name
        for name in old.__dataclass_fields__
        if getattr(old, name) != getattr(new, name)
    }
    assert differing == {
        "schema_version",
        "strategy_id",
        "policy_version",
        "trend_max_iterations",
        "trend_tolerance",
    }
```

Run: `uv run pytest tests/unit/strategy/test_policy.py -v`
Expected: FAIL because `locked_v0_2` is absent.

- [ ] **Step 2: Implement the standalone v0.2 policy**

Use `dataclasses.replace` over `locked_v0_1()` only to prevent silent drift:

```python
@classmethod
def locked_v0_2(cls) -> "CandidatePolicy":
    return replace(
        cls.locked_v0_1(),
        schema_version="candidate-strategy-policy-v2",
        strategy_id="candidate.multi_model.v0_2",
        policy_version="candidate-multi-model-v0.2",
        trend_max_iterations=50_000,
        trend_tolerance=Decimal("0.0000001"),
    )
```

Add `approved_candidate_policy()` that accepts only the exact v0.1 or v0.2 identity pair and fails closed otherwise.

- [ ] **Step 3: Add v0.2 locked CLI fixture and parser coverage**

Create `candidate-v0.2-config.json` by copying the official simulation block unchanged and replacing only:

```json
"strategy": {
  "id": "candidate.multi_model.v0_2",
  "policy_version": "candidate-multi-model-v0.2"
}
```

Refactor `load_candidate_strategy_config()` to validate either approved exact pair rather than hardcoding v0.1. Do not permit arbitrary versions.

- [ ] **Step 4: Verify GREEN and v0.1 compatibility**

Run:

```bash
uv run pytest tests/unit/strategy/test_policy.py tests/unit/cli/test_candidate_strategy_cli.py -v
uv run pyright src/gemini_trading/strategy/policy.py src/gemini_trading/cli/strategy.py tests/unit/strategy/test_policy.py
```

Expected: PASS; existing v0.1 tests remain unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/strategy/policy.py src/gemini_trading/cli/strategy.py tests/fixtures/strategy/candidate-v0.2-config.json tests/unit/strategy/test_policy.py tests/unit/cli/test_candidate_strategy_cli.py
git commit -m "feat: define Candidate v0.2 policy identity"
```

---

### Task 2: Development-Only Qualification Split and Prospective Window Contract

**Files:**
- Modify: `src/gemini_trading/strategy/splits.py`
- Create: `src/gemini_trading/strategy/prospective_final.py`
- Create: `tests/unit/strategy/test_v0_2_development_splits.py`
- Create: `tests/unit/strategy/test_prospective_final.py`

**Interfaces:**
- Produces: `DevelopmentQualificationPlan.build(...) -> DevelopmentQualificationPlan`
- Produces: `ProspectiveFinalWindow.from_verified_at(development_cutoff, verified_at) -> ProspectiveFinalWindow`
- Consumes later: qualification evaluator and seal store.

- [ ] **Step 1: Write RED development-plan tests**

Use deterministic 4h candles covering exactly `[2018-01-01, 2026-07-01)` and the existing segment-manifest fixture. Assert:

```python
plan = DevelopmentQualificationPlan.build(candles, eligible, CandidatePolicy.locked_v0_2(), segments)
assert len(plan.folds) == 12
assert plan.dataset_end_exclusive == datetime(2026, 7, 1, tzinfo=UTC)
assert plan.folds[0].development_test.start_inclusive < plan.folds[-1].development_test.start_inclusive
assert plan.used_label_indices == tuple(sorted(set(plan.used_label_indices)))
```

Also assert labels never cross fold or segment boundaries.

Run: `uv run pytest tests/unit/strategy/test_v0_2_development_splits.py -v`
Expected: FAIL because the type does not exist.

- [ ] **Step 2: Implement `DevelopmentQualificationPlan`**

Reuse the existing split validation, month arithmetic, `_safe_indices`, purge, embargo, and segment-boundary logic. Unlike `ChronologicalSplitPlan`, stop only when the next complete six-month development-test window would exceed the dataset end. Include all resulting folds and require exactly 12 for the fixed v0.2 cutoff.

The plan schema is `candidate-development-qualification-plan-v1` and contains no final-test fields.

- [ ] **Step 3: Write RED prospective-window tests**

```python
def test_august_verification_starts_september_and_seals_18_months() -> None:
    window = ProspectiveFinalWindow.from_verified_at(
        development_cutoff=datetime(2026, 7, 1, tzinfo=UTC),
        verified_at=datetime(2026, 8, 10, 15, 52, tzinfo=UTC),
    )
    assert window.bridge_start == datetime(2026, 7, 1, tzinfo=UTC)
    assert window.final_start == datetime(2026, 9, 1, tzinfo=UTC)
    assert window.final_end == datetime(2028, 3, 1, tzinfo=UTC)
    assert window.bridge_end == window.final_start
```

Also test verification exactly at a month boundary: the final start must be the *next* month boundary because the rule says strictly after.

- [ ] **Step 4: Implement prospective window calculation**

Require UTC-aware timestamps, exact fixed development cutoff, first-of-month `00:00:00Z` boundary, and exactly 18 calendar months. Reject a verification timestamp before the development cutoff.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_v0_2_development_splits.py tests/unit/strategy/test_prospective_final.py -v
uv run ruff check src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/prospective_final.py tests/unit/strategy/test_v0_2_development_splits.py tests/unit/strategy/test_prospective_final.py
uv run pyright src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/prospective_final.py tests/unit/strategy/test_v0_2_development_splits.py tests/unit/strategy/test_prospective_final.py
git add src/gemini_trading/strategy/splits.py src/gemini_trading/strategy/prospective_final.py tests/unit/strategy/test_v0_2_development_splits.py tests/unit/strategy/test_prospective_final.py
git commit -m "feat: add v0.2 development and prospective windows"
```

---

### Task 3: Exact Repeated-Fit Determinism Evidence

**Files:**
- Modify: `src/gemini_trading/strategy/study_predictions.py`
- Create: `src/gemini_trading/strategy/determinism.py`
- Modify: `tests/unit/strategy/test_models.py`
- Create: `tests/unit/strategy/test_determinism.py`

**Interfaces:**
- Produces: `prediction_bundle_sha256(bundle: PredictionBundle) -> str`
- Produces: `TrendDeterminismReceipt`
- Produces: `fit_verified_prediction_bundle(...) -> tuple[PredictionBundle, TrendDeterminismReceipt]`

- [ ] **Step 1: Write RED determinism tests**

Assert two v0.2 fits from identical fixture inputs produce:

```python
assert first_receipt.exact_match is True
assert first_receipt.first_model_sha256 == first_receipt.second_model_sha256
assert first_receipt.first_bundle_sha256 == first_receipt.second_bundle_sha256
assert first_receipt.iteration_count < 50_000
```

Add a tamper/unit helper case proving a mismatched second digest raises `ModelDeterminismError`.

- [ ] **Step 2: Implement canonical bundle identity**

Build a digest only from existing canonical, non-executable evidence: serialized trend/mean-reversion model artifacts, serialized Platt artifacts, canonical expected-return maps, and canonical prediction/regime rows. Do not pickle estimators.

- [ ] **Step 3: Implement repeated-fit verification**

`fit_verified_prediction_bundle()` calls the existing deterministic bundle fit twice for v0.2 development folds, compares complete bundle digests and trend model bytes, checks the first iteration count is strictly below the locked ceiling, and returns the first bundle plus immutable receipt.

The receipt schema is `candidate-v0.2-trend-determinism-v1`.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_models.py tests/unit/strategy/test_determinism.py -v
uv run pyright src/gemini_trading/strategy/study_predictions.py src/gemini_trading/strategy/determinism.py
uv run ruff check src/gemini_trading/strategy/study_predictions.py src/gemini_trading/strategy/determinism.py tests/unit/strategy/test_determinism.py
git add src/gemini_trading/strategy/study_predictions.py src/gemini_trading/strategy/determinism.py tests/unit/strategy/test_models.py tests/unit/strategy/test_determinism.py
git commit -m "feat: verify v0.2 repeated-fit determinism"
```

---

### Task 4: Development Qualification Cases and Gate Evaluator

**Files:**
- Modify: `src/gemini_trading/strategy/study_plans.py`
- Modify: `src/gemini_trading/strategy/study_execution.py`
- Create: `src/gemini_trading/strategy/qualification.py`
- Create: `tests/unit/strategy/test_qualification.py`
- Create: `tests/integration/test_candidate_v0_2_qualification.py`

**Interfaces:**
- Produces: `QualificationClassification` with `QUALIFIED`, `REJECTED`, `INCONCLUSIVE`
- Produces: `QualificationReport`
- Produces: `evaluate_development_qualification(...) -> QualificationReport`
- Consumes: 12 development folds, determinism receipts, existing research-engine evidence.

- [ ] **Step 1: Write RED gate-order and classification tests**

Create complete synthetic `QualificationEvidence` and assert every gate ID is emitted in a fixed order. Explicit failure must classify `REJECTED`; missing evidence with no explicit failure must classify `INCONCLUSIVE`; every gate passing must classify `QUALIFIED`.

Mandatory groups: integrity, convergence/determinism, calibration, fold stability, controls, cost robustness, sensitivity robustness, bootstrap uncertainty, replay/verification readiness.

- [ ] **Step 2: Add v0.2 development robustness plans**

Extend case-plan construction through an explicit `include_qualification_robustness=True` option. It adds the already preregistered `cost.1_5x`, `cost.2x`, ten sensitivity variants, delayed/shuffled controls, and ablations to each development fold without changing primary candidate decisions.

The primary case ID comes from `policy.strategy_id`; v0.1 continues to use `candidate.multi_model.v0_1` and its existing case set.

- [ ] **Step 3: Implement aggregate development path metrics**

Concatenate only non-overlapping out-of-sample development-test account-return paths in fold order. Recompute compounded net return and maximum drawdown from that concatenated path. Do not average fold drawdowns.

- [ ] **Step 4: Implement strict qualification gates**

Apply the exact thresholds from the approved spec: 12 folds; 60% positive; 60% baseline RTD wins; <=50% profit concentration; >=60 trades; negative/control conditions; cost 1.5x/2x thresholds and monotonicity; 7/10 positive neighbors, positive median, <=35% drawdown, primary stability; deterministic 1,000-replicate/42-candle/seed-1788 bootstrap with positive median and p05 > -0.02.

- [ ] **Step 5: Integration-test a bounded final-row-free qualification**

Patch only row counts for runtime, not policy values. Assert every executed record is development phase, no prospective-final provider exists, every receipt verifies, and an explicit failed mandatory gate returns `REJECTED`.

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification.py tests/integration/test_candidate_v0_2_qualification.py -v
uv run ruff check src/gemini_trading/strategy/study_plans.py src/gemini_trading/strategy/study_execution.py src/gemini_trading/strategy/qualification.py tests/unit/strategy/test_qualification.py tests/integration/test_candidate_v0_2_qualification.py
uv run pyright src/gemini_trading/strategy/study_plans.py src/gemini_trading/strategy/study_execution.py src/gemini_trading/strategy/qualification.py tests/unit/strategy/test_qualification.py tests/integration/test_candidate_v0_2_qualification.py
git add src/gemini_trading/strategy/study_plans.py src/gemini_trading/strategy/study_execution.py src/gemini_trading/strategy/qualification.py tests/unit/strategy/test_qualification.py tests/integration/test_candidate_v0_2_qualification.py
git commit -m "feat: add strict v0.2 development qualification"
```

---

### Task 5: Immutable Qualification Artifacts and Prospective Seal

**Files:**
- Create: `src/gemini_trading/strategy/qualification_artifacts.py`
- Create: `src/gemini_trading/strategy/prospective_seal.py`
- Create: `tests/unit/strategy/test_qualification_artifacts.py`
- Create: `tests/unit/strategy/test_prospective_seal.py`

**Interfaces:**
- Produces: `QualificationArtifacts`, `LocalQualificationStore`, `verify_qualification_artifacts()`
- Produces: `ProspectiveFinalSeal`, `LocalProspectiveFinalSealStore`

- [ ] **Step 1: Write RED artifact-contract tests**

Require canonical files for policy, configuration, development plan, experiment references, determinism receipts, qualification gates, bootstrap evidence, manifest, result manifest, and limitations. The qualification ID is SHA-256 over the complete structural identity and core hashes.

Test missing file, changed byte, changed code commit, changed dataset ID, and reordered experiment evidence rejection.

- [ ] **Step 2: Implement immutable qualification store and verifier**

Use the repository's existing `write_immutable` and canonical serialization patterns. Generated evidence path:

```text
data/historical-validation/v0-2-qualification/<qualification-id>/
```

Verification must require no provider/network.

- [ ] **Step 3: Write RED prospective-seal tests**

A seal may be created only for verified `QUALIFIED` evidence. Test that `REJECTED`, `INCONCLUSIVE`, second creation, changed identity, non-UTC time, and bridge overlap fail closed.

- [ ] **Step 4: Implement seal identity and exclusive store**

The seal binds exact code SHA, dataset ID, Stage 1 inventory root, qualification ID/root, workflow run/attempt, verified-at timestamp, development cutoff, bridge interval, and prospective final start/end. The computed schedule must use the Task 2 boundary helper and exactly 18 months.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/unit/strategy/test_qualification_artifacts.py tests/unit/strategy/test_prospective_seal.py -v
uv run pyright src/gemini_trading/strategy/qualification_artifacts.py src/gemini_trading/strategy/prospective_seal.py
uv run ruff check src/gemini_trading/strategy/qualification_artifacts.py src/gemini_trading/strategy/prospective_seal.py tests/unit/strategy/test_qualification_artifacts.py tests/unit/strategy/test_prospective_seal.py
git add src/gemini_trading/strategy/qualification_artifacts.py src/gemini_trading/strategy/prospective_seal.py tests/unit/strategy/test_qualification_artifacts.py tests/unit/strategy/test_prospective_seal.py
git commit -m "feat: persist v0.2 qualification and prospective seal"
```

---

### Task 6: Safe CLI and GitHub Qualification Workflow

**Files:**
- Modify: `src/gemini_trading/cli/historical_validation.py`
- Modify: `src/gemini_trading/cli/research.py`
- Create: `.github/workflows/candidate-v0.2-qualification.yml`
- Create: `tests/acceptance/test_candidate_v0_2_workflow.py`
- Create: `tests/integration/test_candidate_v0_2_cli.py`

**Interfaces:**
- Produces CLI: `research strategy-v0-2-qualify`
- Produces CLI: `research strategy-v0-2-qualification-verify`
- Produces CLI: `research strategy-v0-2-seal-prospective-final`

- [ ] **Step 1: Write RED CLI tests**

Require the exact v0.2 config path, exact v4 handoff, exact source commit, fixed development cutoff, safe JSON output, `GEMINI_TRADING_MODE=research`, and no provider construction for verify/seal commands.

- [ ] **Step 2: Implement qualification and verification commands**

`strategy-v0-2-qualify` loads the verified handoff/dataset, requires `candidate-v0.2-config.json`, runs the strict development-only qualifier, writes immutable artifacts, and emits only status/classification/qualification ID.

`strategy-v0-2-qualification-verify` is provider-free and recomputes identities/hashes.

`strategy-v0-2-seal-prospective-final` consumes verified `QUALIFIED` evidence plus workflow identity and a supplied UTC verification timestamp from the workflow environment; it performs no market-data read.

- [ ] **Step 3: Write RED workflow-contract test**

Require exactly four identity inputs: `source_commit`, `dataset_run_id`, `dataset_artifact_name`, `dataset_id`. Require manual dispatch only, Issue #61 owner approval marker, least privilege, exact source checkout, exact Stage 1 artifact verification, qualification, provider-free independent verification, artifact upload, and no `strategy-finalize` or final-row access command.

- [ ] **Step 4: Implement workflow**

Workflow name: `Candidate v0.2 Development Qualification`.

Use the repository's pinned action versions and frozen `uv` environment. Require an owner-authored Issue #61 marker:

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

Upload `candidate-v0.2-qualification-${{ github.run_id }}` with 90-day retention. Do not create the prospective seal automatically until the artifact has been independently checked; seal creation is a separate explicit repository operation after verification.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/acceptance/test_candidate_v0_2_workflow.py tests/integration/test_candidate_v0_2_cli.py -v
uv run pyright src/gemini_trading/cli/historical_validation.py src/gemini_trading/cli/research.py
uv run ruff check src/gemini_trading/cli/historical_validation.py src/gemini_trading/cli/research.py tests/acceptance/test_candidate_v0_2_workflow.py tests/integration/test_candidate_v0_2_cli.py
git add src/gemini_trading/cli/historical_validation.py src/gemini_trading/cli/research.py .github/workflows/candidate-v0.2-qualification.yml tests/acceptance/test_candidate_v0_2_workflow.py tests/integration/test_candidate_v0_2_cli.py
git commit -m "feat: add Candidate v0.2 qualification workflow"
```

---

### Task 7: Documentation, Full Regression, and Exact-Head Review

**Files:**
- Modify: `README.md`
- Create: `docs/operations/candidate-multi-model-strategy-v0-2.md`
- Create: `docs/operations/candidate-multi-model-strategy-v0-2-step-verification.md`
- Create: `tests/acceptance/test_candidate_v0_2_documentation.py`

**Interfaces:**
- Produces the operator contract for post-merge Stage 1, qualification, independent verification, Issue #61 approval marker, and prospective seal.

- [ ] **Step 1: Add RED documentation assertions**

Require the docs to state `RESEARCH_ONLY`, exact v0.2 identity, `tol=1e-7`, `max_iter=50000`, fixed development cutoff, 12 folds, `QUALIFIED/REJECTED/INCONCLUSIVE`, bridge quarantine, dynamic prospective start, exactly 18 months, no future profitability claim, and no execution authority.

- [ ] **Step 2: Write operations and verification docs**

Document exact POSIX/PowerShell commands, workflow inputs, approval marker, artifact names, independent hash verification, seal fields, failure semantics, and future final-era limitation.

- [ ] **Step 3: Run focused and complete quality gates**

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run pre-commit run --all-files
git diff --check
git status --short
```

Review the exact diff for accidental v0.1 policy changes, any executable/live capability, generated evidence, credentials, private endpoints, unbounded inputs, or final-row access.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md docs/operations/candidate-multi-model-strategy-v0-2.md docs/operations/candidate-multi-model-strategy-v0-2-step-verification.md tests/acceptance/test_candidate_v0_2_documentation.py
git commit -m "docs: document Candidate v0.2 prospective qualification"
```

---

### Task 8: Protected Merge, Fresh Stage 1, Qualification, and Prospective Seal

**Files:**
- No production-code change unless verification finds a genuine implementation defect that restores the written contract.
- Create after operation: `reports/verification/candidate-multi-model-strategy-v0-2-prefinal.md` through a separate compact report PR.

**Interfaces:**
- Consumes exact reviewed PR head and exact merged-main SHA.
- Produces Stage 1 dataset identity, qualification identity/classification, and conditional prospective seal.

- [ ] **Step 1: Verify exact PR head**

Require ordinary CI and all v0.2 focused tests on the unchanged reviewed head. Resolve all review threads. Confirm branch diff is in scope.

- [ ] **Step 2: Merge through protected `main`**

Use expected-head protection. Do not direct-push. Record the exact merged-main SHA.

- [ ] **Step 3: Verify exact merged-main SHA**

Require the complete CI/security suite to pass on that exact SHA before any real qualification operation.

- [ ] **Step 4: Run fresh Stage 1 from exact v0.2 main**

Dispatch the existing sealed dataset workflow on exact main. Download and independently verify the complete v4 artifact. Record the new source commit, run ID, artifact ID/name, dataset ID, inventory root, canonical hashes, candle boundaries, closure/exclusion/segment identities, replay, and verification on Issue #61.

- [ ] **Step 5: Post exact owner dataset approval marker**

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

The comment must include the artifact/inventory identities and `RESEARCH_ONLY` boundary.

- [ ] **Step 6: Dispatch one v0.2 qualification run**

Use only the four approved identities. Download the qualification artifact immediately and independently recompute every file hash, qualification ID, determinism receipt, gate, and provider-free verification result.

If classification is `REJECTED`, preserve it and stop. If `INCONCLUSIVE`, preserve it and stop unless immutable evidence supports a pure infrastructure continuation under the written contract. Do not tune v0.2.

- [ ] **Step 7: Create prospective seal only if `QUALIFIED`**

Use the exact successful verification timestamp. The seal computes the first UTC month boundary strictly after verification and an end exactly 18 months later. Record bridge and final intervals on Issue #61. Seal creation performs no market-data read.

- [ ] **Step 8: Commit compact pre-final report and close the implementation milestone**

The report records source/run/artifact/qualification/seal identities, gate outcome, limitations, and unchanged authority boundary. Keep Issue #61 open if it is also being used to track the eventual prospective-final result; otherwise open a dedicated final-era issue and close #61 only after the pre-final milestone is independently verified and cross-linked.

---

## Plan Self-Review

- Spec coverage: every approved Issue #61 design decision is implemented by Tasks 1-8.
- Placeholder scan: no `TBD`, `TODO`, deferred code stub, or unspecified error-handling step remains.
- Type consistency: v0.2 policy -> development plan -> repeated-fit receipt -> qualification report -> immutable qualification artifact -> prospective seal is the single forward dependency chain.
- Scope: no broker/live/execution functionality is introduced; future market evidence remains an operational dependency, not a synthetic implementation assumption.
