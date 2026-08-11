# Candidate Multi-Model Strategy v0.2 Step Verification

## Completion boundary

This document defines completion of the Candidate v0.2 **pre-final implementation milestone**. It does not claim completion of the future 18-month market test. The prospective final era cannot be evaluated until its sealed future interval actually exists.

The entire sequence remains `RESEARCH_ONLY` and carries no paper, demo, live, or real-capital execution authority.

## Required implementation sequence

1. **Approved design and plan**
   - Issue #61 contains the approved v0.2 design decisions.
   - Strategy identity is `candidate.multi_model.v0_2` and policy identity is `candidate-multi-model-v0.2`.
   - Trend convergence is frozen at `tol=1e-7`, `max_iter=50000` with Elastic-Net + `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, and single-thread execution.
2. **Development-only split contract**
   - Dataset window is exactly `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
   - Exactly 12 complete walk-forward development folds are required.
   - No prospective final rows are constructed or read by qualification.
3. **Determinism and qualification implementation**
   - Every fold requires convergence strictly before 50,000 iterations.
   - Repeated trend model and complete prediction-bundle identities must match exactly.
   - All integrity, calibration, development-stability, controls, cost, sensitivity, bootstrap, replay, and independent-verification gates must be present.
4. **Classification semantics**
   - `QUALIFIED` requires every mandatory pre-final gate to pass.
   - `REJECTED` is terminal for v0.2 and cannot be rescued by tuning.
   - `INCONCLUSIVE` fails closed unless a pure evidence/infrastructure continuation preserves the frozen candidate.
5. **Immutable evidence and seal**
   - Qualification files and structural identities are content-addressed.
   - Only verified `QUALIFIED` evidence can create a prospective seal.
   - The bridge starts at `2026-07-01T00:00:00Z` and ends at the prospective final start.
   - Final start is the first UTC calendar-month boundary strictly after successful frozen-source/pre-final verification.
   - Final end is exactly 18 calendar months later.
6. **Documentation acceptance**
   - README and v0.2 operations documents must state the safety boundary, exact identities, convergence contract, development cutoff, 12 folds, closed classifications, bridge quarantine, 18-month future final era, future-profitability limitation, and no execution authority.
7. **Complete quality/security checkpoint**
   - Ruff formatting and lint, strict Pyright, full pytest, package build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks must pass on the exact PR head.
8. **Exact-head review**
   - Review the cumulative diff against the approved design.
   - Confirm v0.1 behavior and rejection evidence remain valid.
   - Confirm no credentials, private endpoint, broker, order-submission, leverage, short, futures, autonomous allocation, or future-final market-read capability was introduced.
9. **Protected merge**
   - Mark the PR ready only after the exact unchanged head is green and review-complete.
   - Merge through protected `main` with expected-head protection.
10. **Exact merged-main verification**
    - Require the full CI/security suite on the exact merged-main SHA before any real qualification operation.
11. **Fresh Stage 1**
    - Dispatch `Sealed BTCUSDT Dataset` from exact merged `main`.
    - Download the artifact immediately.
    - Independently verify every dataset/handoff identity and hash.
    - Do not reuse an old v0.1 Stage 1 artifact.
12. **Owner approval marker**
    - Add to Issue #61 only after independent Stage 1 verification:

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

13. **One development qualification run**
    - Dispatch `Candidate v0.2 Development Qualification` with only the four fixed identity inputs.
    - Preserve the first complete valid classification.
    - Do not tune or rerun to improve performance.
14. **Independent qualification verification**
    - Download the artifact and recompute qualification identities/hashes provider-free.
    - Confirm the recorded classification and every mandatory gate.
15. **Prospective seal only after `QUALIFIED`**
    - Run `strategy-v0-2-seal-prospective-final` only if independent verification confirms `QUALIFIED`.
    - Record `seal_id`, bridge interval, prospective final interval, qualification identity, and verification timestamp.
    - If `REJECTED` or `INCONCLUSIVE`, no seal is created.
16. **Compact pre-final report**
    - Commit exact source/run/artifact/dataset/qualification/seal identities and limitations through a small report PR.
    - Keep Issue #61 open or cross-link a dedicated future-final issue so the eventual prospective result cannot be confused with pre-final qualification.

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
  tests/unit/strategy/test_prospective_seal.py \
  tests/unit/strategy/test_qualification_execution.py \
  tests/unit/strategy/test_study_plans_v0_2.py \
  tests/integration/test_candidate_v0_2_cli.py \
  tests/acceptance/test_candidate_v0_2_workflow.py \
  tests/acceptance/test_candidate_v0_2_documentation.py -v
```

Also run the legacy v0.1 acceptance and sealed-validation tests to prove that adding v0.2 did not make v0.1 evidence require a v0.2 case.

## Stage 1 operational checkpoint

Dispatch only after the exact merged-main CI is green:

```bash
gh workflow run sealed-btcusdt-dataset.yml --ref main
```

Required Stage 1 report fields:

- merged-main source SHA;
- workflow run ID and attempt;
- artifact ID/name and artifact SHA-256;
- dataset ID and inventory root;
- canonical candle, closure, exclusion, segment, provenance, and retrieval hashes;
- raw page count and provider-row count;
- missing slots, partial exclusions, canonical candle count, and segment count;
- first/last candle open times;
- provider-free replay result;
- independent verification result.

Do not post the Issue #61 approval marker until all required Stage 1 checks agree.

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

The workflow must contain `strategy-v0-2-qualify` and `strategy-v0-2-qualification-verify` but must not contain `strategy-v0-2-seal-prospective-final`, `strategy-authorize-final`, or `strategy-finalize`.

## Provider-free qualification verification

```bash
export GEMINI_TRADING_MODE=research
uv run gemini-trading research strategy-v0-2-qualification-verify \
  --qualification-id "$QUALIFICATION_ID" \
  --output-root "$OUTPUT_ROOT"
```

Required agreement:

- classification;
- qualification ID;
- qualification inventory root;
- exact code commit;
- dataset ID and Stage 1 inventory root;
- workflow run and attempt;
- policy/configuration/development-plan identities;
- all determinism receipts;
- every mandatory qualification gate;
- bootstrap evidence;
- referenced experiment identities.

Any missing or changed byte fails closed.

## Prospective seal checkpoint

Only after independently verified `QUALIFIED` evidence:

```bash
uv run gemini-trading research strategy-v0-2-seal-prospective-final \
  --qualification-id "$QUALIFICATION_ID" \
  --verified-at "$VERIFIED_AT" \
  --output-root "$OUTPUT_ROOT"
```

Verify:

- exactly one active seal exists;
- `development_cutoff` is `2026-07-01T00:00:00Z`;
- `bridge_start` equals the development cutoff;
- `bridge_end` equals `final_start`;
- `final_start` is the first UTC calendar-month boundary strictly after `verified_at`;
- `final_end` is exactly 18 calendar months after `final_start`;
- `execution_authorized` is false;
- no market provider was constructed.

## Pre-final report evidence

Record at minimum:

- exact approved design and implementation plan paths;
- exact PR head SHA and PR CI run;
- exact merged-main SHA and exact-main CI run;
- Stage 1 run/artifact/dataset/inventory identities;
- Issue #61 owner approval marker comment ID;
- qualification run/artifact/qualification identities;
- classification and every failed gate, if any;
- provider-free verification result;
- prospective seal identity and interval only if `QUALIFIED`;
- explicit statement that future profitability is not established;
- explicit statement that no execution authority was introduced.

## Permitted completion claim

After Tasks 1-16 above are satisfied, the permitted claim is:

> Candidate v0.2's pre-final implementation and qualification protocol are complete and independently evidenced. If it qualified, its future 18-month prospective window is sealed. No future profitability or execution readiness is established until the future market test itself is completed under a separate governed operation.

Do not describe a successful implementation, a `QUALIFIED` development result, or a prospective seal as a successful prospective market result.
