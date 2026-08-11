# Candidate Multi-Model Strategy v0.2 Step Verification

## Completion boundary

This document defines completion of the Candidate v0.2 **pre-final implementation milestone**. It does not claim completion of the future 18-month market test. The prospective final era cannot be evaluated until its sealed future interval exists.

The entire sequence remains `RESEARCH_ONLY`, with **no execution authority** for paper, demo, live, production, or real capital. Future profitability is not established.

## Required implementation sequence

1. **Approved design and plan**
   - Issue #61 contains the approved v0.2 decisions.
   - Strategy identity is `candidate.multi_model.v0_2`; policy identity is `candidate-multi-model-v0.2`.
   - Trend convergence is frozen at `tol=1e-7`, `max_iter=50000`, Elastic-Net + `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, single thread.
2. **Development-only split contract**
   - Dataset window is exactly `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
   - Exactly 12 complete walk-forward development folds are mandatory.
   - Qualification constructs or reads no prospective-final rows.
3. **Determinism and qualification implementation**
   - Every fold must converge strictly before 50,000 iterations.
   - Repeated trend-model and complete prediction-bundle identities must match exactly.
   - Integrity, calibration, stability, controls, cost, sensitivity, bootstrap, replay, and independent-verification gates must all exist.
4. **Classification semantics**
   - `QUALIFIED` requires every mandatory pre-final gate to pass.
   - `REJECTED` is terminal for v0.2 and cannot be rescued by tuning.
   - `INCONCLUSIVE` fails closed unless a pure evidence/infrastructure continuation preserves the frozen candidate.
5. **Immutable evidence and seal**
   - Qualification evidence contains canonical `policy.json`, `configuration.json`, and `development-plan.json` plus the complete result inventory.
   - Qualification identity binds the core artifact inventory root.
   - Only fully verified `QUALIFIED` evidence can create a prospective seal.
   - The bridge starts at `2026-07-01T00:00:00Z` and ends at prospective final start.
   - Final start is the first UTC calendar-month boundary strictly after successful frozen-source/pre-final verification.
   - Final end is exactly 18 calendar months later.
6. **Portable verification contract**
   - The qualification artifact must include referenced `data/research` experiments and v0.2 qualification evidence.
   - The separately retained Stage 1 artifact must be rehydrated into the same output root for independent verification.
   - Verification and seal creation require `--project-root` pointing at a clean checkout of the exact source commit.
   - Every referenced experiment/result and the exact Stage 1 handoff must independently reverify provider-free.
7. **Documentation acceptance**
   - README and v0.2 operations docs state the safety boundary, identities, convergence contract, development cutoff, 12 folds, classifications, bridge quarantine, future final era, rehydration protocol, future-profitability limitation, and no execution authority.
8. **Complete quality/security checkpoint**
   - Ruff formatting/lint, strict Pyright, full pytest, package build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks pass on the exact PR head.
9. **Exact-head review**
   - Review the cumulative diff against the approved design.
   - Confirm v0.1 behavior and rejection evidence remain valid.
   - Confirm no credentials, private endpoint, broker/order submission, leverage, shorting, futures, autonomous allocation, or future-final market-read capability was introduced.
10. **Protected merge**
    - Mark the PR ready only after the exact unchanged head is green and review-complete.
    - Merge through protected `main` with expected-head protection.
11. **Exact merged-main verification**
    - Require the complete CI/security suite on the exact merged-main SHA before real qualification operations.
12. **Fresh Stage 1**
    - Dispatch `Sealed BTCUSDT Dataset` from exact merged `main`.
    - Download the artifact immediately and independently verify all dataset/handoff identities and hashes.
    - Do not reuse a v0.1 Stage 1 artifact.
13. **Owner approval marker**
    - Only after independent Stage 1 verification, add to Issue #61:

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

14. **One development qualification run**
    - Dispatch `Candidate v0.2 Development Qualification` using only the four fixed identity inputs.
    - Preserve the first complete valid classification; do not tune or rerun to improve performance.
15. **Independent qualification verification**
    - Rehydrate exact Stage 1 and qualification bundle evidence into one output root.
    - Verify from a clean checkout at the exact qualification source commit.
    - Confirm classification, core inventory/qualification identity, Stage 1 identity, all mandatory evidence, and every referenced experiment result.
16. **Prospective seal only after `QUALIFIED`**
    - Run `strategy-v0-2-seal-prospective-final` only after independent verification confirms `QUALIFIED`.
    - Seal creation reruns full bundle verification and binds the candidate identity and future interval.
    - If `REJECTED` or `INCONCLUSIVE`, create no seal.
17. **Compact pre-final report**
    - Commit exact source/run/artifact/dataset/qualification/verification/seal identities and limitations through a small report PR.
    - Keep Issue #61 open or cross-link a dedicated future-final issue so pre-final qualification cannot be confused with the future market result.

## Exact implementation checkpoint

Run on the unchanged PR head:

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

Repository CI additionally validates tracked-file policy, tracked-file secret scanning, and Gitleaks.

## Focused Candidate v0.2 checkpoint

```bash
uv run pytest \
  tests/unit/strategy/test_policy.py \
  tests/unit/strategy/test_v0_2_development_splits.py \
  tests/unit/strategy/test_prospective_final.py \
  tests/unit/strategy/test_determinism.py \
  tests/unit/strategy/test_qualification.py \
  tests/unit/strategy/test_qualification_artifacts.py \
  tests/unit/strategy/test_qualification_execution.py \
  tests/unit/strategy/test_qualification_verification.py \
  tests/unit/strategy/test_prospective_seal.py \
  tests/unit/strategy/test_study_plans_v0_2.py \
  tests/integration/test_candidate_v0_2_cli.py \
  tests/acceptance/test_candidate_v0_2_workflow.py \
  tests/acceptance/test_candidate_v0_2_documentation.py -v
```

Also run legacy v0.1 acceptance and sealed-validation tests to prove that adding v0.2 did not make v0.1 evidence require a v0.2 case.

## Stage 1 operational checkpoint

Dispatch only after exact merged-main CI is green:

```bash
gh workflow run sealed-btcusdt-dataset.yml --ref main
```

Record merged-main source SHA, workflow run/attempt, artifact ID/name/SHA-256, dataset ID/inventory root, support hashes, raw/provider counts, unavailable/excluded counts, canonical candle count, segment count, first/last candle boundaries, replay, and independent-verification results.

Do not post the Issue #61 approval marker until all Stage 1 checks agree.

## Qualification operational checkpoint

Dispatch only after the owner marker exists:

```bash
gh workflow run candidate-v0.2-qualification.yml \
  --ref main \
  -f source_commit="$SOURCE_COMMIT" \
  -f dataset_run_id="$DATASET_RUN_ID" \
  -f dataset_artifact_name="$DATASET_ARTIFACT_NAME" \
  -f dataset_id="$DATASET_ID"
```

The artifact must be named:

```text
candidate-v0.2-qualification-<workflow-run-id>
```

The workflow contains `strategy-v0-2-qualify` and `strategy-v0-2-qualification-verify`, but not `strategy-v0-2-seal-prospective-final`, `strategy-authorize-final`, or `strategy-finalize`.

The qualification bundle must contain referenced `data/research` experiments and `data/historical-validation/v0-2-qualification`. Stage 1 remains a separately retained artifact.

## Rehydrate provider-free evidence

Extract the exact Stage 1 artifact and exact qualification bundle into the same `$OUTPUT_ROOT`. The resulting root must contain the Stage 1 handoff/canonical dataset plus the qualification bundle's research experiments and qualification directory.

Use a clean checkout at the exact source commit:

```bash
export GEMINI_TRADING_MODE=research
export PROJECT_ROOT='<clean-checkout-at-exact-source-commit>'
export OUTPUT_ROOT='<rehydrated-evidence-root>'
```

## Provider-free qualification verification

```bash
uv run gemini-trading research strategy-v0-2-qualification-verify \
  --qualification-id "$QUALIFICATION_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

Required agreement includes:

- exact clean code commit;
- classification and qualification ID;
- qualification core inventory root;
- `policy.json`, `configuration.json`, and `development-plan.json` identities;
- dataset ID and Stage 1 handoff inventory root;
- Stage 1 run identity;
- workflow run/attempt;
- all determinism receipts and mandatory gates;
- bootstrap evidence;
- exact complete 12-fold case set;
- every referenced experiment/result identity.

Any missing or changed byte fails closed.

## Prospective seal checkpoint

Only after independently verified `QUALIFIED` evidence:

```bash
uv run gemini-trading research strategy-v0-2-seal-prospective-final \
  --qualification-id "$QUALIFICATION_ID" \
  --verified-at "$VERIFIED_AT" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

Verify exactly one active seal exists; candidate identity remains v0.2; `development_cutoff` is `2026-07-01T00:00:00Z`; `bridge_start` equals the cutoff; `bridge_end` equals `final_start`; `final_start` is the first UTC calendar-month boundary strictly after `verified_at`; `final_end` is exactly 18 calendar months later; and `execution_authorized` remains false.

## Pre-final report evidence

Record the approved design/plan paths, exact PR head/CI, exact merged-main SHA/CI, Stage 1 identities, Issue #61 approval comment, qualification identities/classification/gates, provider-free verification result, and prospective seal identity/interval only if `QUALIFIED`. Explicitly state that future profitability is not established and that the milestone grants no execution authority.

## Permitted completion claim

After the steps above are satisfied, the permitted claim is:

> Candidate v0.2's pre-final implementation and qualification protocol are complete and independently evidenced. If it qualified, its future 18-month prospective window is sealed. No future profitability or execution readiness is established until the future market test itself is completed under a separate governed operation.

Do not describe a successful implementation, a `QUALIFIED` development result, or a prospective seal as a successful prospective market result.
