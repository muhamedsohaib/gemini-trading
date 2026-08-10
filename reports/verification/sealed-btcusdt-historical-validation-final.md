# Sealed BTCUSDT Historical Validation — Final Verification Report

## Classification

`REJECTED`

Candidate Multi-Model Strategy v0.1 failed a mandatory pre-final model-determinism/reproducibility gate. The sealed final 18-month partition was not accessed.

Safety boundary: `RESEARCH_ONLY`.

## Governing gate

- Issue: #22 — sealed BTCUSDT historical validation
- Strategy: `candidate.multi_model.v0_1`
- Fixed historical window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`
- Instrument/timeframe: BTCUSDT Binance Spot, completed 4h candles
- Execution authority: none

The governing design permits `PASS`, `REJECTED`, or `INCONCLUSIVE` and prohibits post-evidence model rescue or final-test leakage.

## Exact source verification

The last strategy-code correction was PR #57, which restored the approved trend solver iteration budget from the incorrect implementation value `5000` to `10000`.

- Reviewed PR #57 head: `bc8d6d8f5f2cfd53056aeac9ffabcd74b4285b79`
- Squash-merged `main`: `c4c9ce9d62a4fba8aab3795598be9b54cb50aa5d`
- Exact-main CI run: `31378647321`
- Exact-main CI conclusion: success

The exact-main run passed frozen dependency sync, Ruff format, Ruff lint, strict Pyright, full pytest, package build, pip-audit, tracked-file policy, detect-secrets, and Gitleaks.

## Fresh Stage 1 evidence

A completely new Stage 1 dataset was produced after the PR #57 merge and exact-main verification.

- Stage 1 run: `31383925467`
- Source commit: `c4c9ce9d62a4fba8aab3795598be9b54cb50aa5d`
- Retrieval run ID: `2ddc3e59c1404883a74b4e5782cad4f6`
- Dataset ID: `33cdaecbec6b1d90db46fde0e0ad1164b3dca2e6bd2fb858d73a1b177f6a007b`
- Artifact name: `sealed-btcusdt-dataset-c4c9ce9d62a4fba8aab3795598be9b54cb50aa5d-31383925467`
- Artifact ID: `9060952648`
- Artifact SHA-256: `7f690f5b90f12ed4f7bf19e419f4ebc0d9adaa2caa40e69e9f43bd4b73525cd8`
- Inventory root: `ffa498a35b23d11baf5a4b2c135f37b3fd91603002390a868ef52f91bf20b445`
- Closure / exclusion / segment counts: `20 / 20 / 21`
- Unavailable canonical 4h slots: `36`
- Raw provider rows: `18,602`
- Canonical candles: `18,582`
- First open: `2018-01-01T00:00:00Z`
- Last open: `2026-06-30T20:00:00Z`
- Replay: `completed`
- Independent repository verification: `verified`

The downloaded artifact was independently inspected outside the producing workflow. All 417 explicit checks passed, including ZIP digest, complete inventory hashes and sizes, inventory-root recomputation, raw-page hashes, provenance linkage, exact unavailable-slot set, all 20 partial-row hashes and locations, canonical grid, v4 dataset-ID recomputation, segment boundaries, and source/run/dataset identities.

The exact owner Stage 1 approval marker was recorded in Issue #22 before Stage 2 dispatch.

## Stage 2 execution

Fresh sealed Stage 2 run:

- Workflow run: `31384416060`
- Event: `workflow_dispatch`
- Source commit: `c4c9ce9d62a4fba8aab3795598be9b54cb50aa5d`
- Stage 1 run input: `31383925467`
- Dataset input: `33cdaecbec6b1d90db46fde0e0ad1164b3dca2e6bd2fb858d73a1b177f6a007b`

Job outcomes:

- `validate-dataset`: success
- `prepare`: failure
- `authorize-final`: skipped
- `finalize`: skipped

`validate-dataset` successfully checked the exact source commit, exact Issue #22 owner approval, Stage 1 artifact, and exact dataset handoff.

The development-only `prepare` phase then terminated with:

```text
ModelDeterminismError: trend specialist did not converge before max_iter
```

The run emitted a scikit-learn convergence warning that the maximum iteration count was reached before the coefficient solution converged.

## Locked trend-model contract at failure

The failing run used the approved Candidate v0.1 trend specialist contract:

- model family: elastic-net logistic regression
- library: scikit-learn `1.9.0`
- fold-local standardization
- solver: `saga`
- `C = 1.0`
- `l1_ratio = 0.5`
- `max_iter = 10000`
- tolerance: `1e-8`
- fixed seed: `1701`
- single-thread execution
- inverse-frequency class weighting only outside the approved positive-fraction range

The prior `5000` implementation value was a code defect because it did not match the approved design. PR #57 corrected that defect. The fresh Stage 2 failure occurred after the implementation matched the approved `10000`-iteration contract, so increasing the budget further is not a defect correction.

## Final-test isolation

The final-test access boundary was not crossed.

- `authorize-final` was skipped.
- `finalize` was skipped.
- No Issue #22 `sealed-final-access` marker exists for this run.
- No final-test receipt was created.
- No final-test predictions, decisions, orders, fills, or economic metrics were produced.

The last 18-month final partition therefore remains untouched by Candidate v0.1 Stage 2.

## Why the result is `REJECTED`

Candidate v0.1 is deliberately frozen before evidence is observed. Its design requires deterministic specialist evidence before final access and states that failure is preserved rather than repaired through post-hoc model expansion or threshold adjustment.

The trend specialist could not produce a converged model within its exact approved numerical contract on the valid development evidence. That is a mandatory pre-final model-determinism/reproducibility failure. Continuing by changing `max_iter`, tolerance, solver, regularization, features, thresholds, or another model property would change the Candidate policy after observing development evidence and would no longer be Candidate v0.1.

Accordingly:

1. Candidate v0.1 is rejected at the pre-final gate.
2. The sealed final partition remains unopened.
3. Stage 2 must not be rerun as a rescue attempt for Candidate v0.1.
4. Any numerical or model redesign requires a separately governed Candidate v0.2 or independent-replication design gate.

## Independent advisory review

The evidence supports the rejection classification:

- data acquisition and handoff integrity passed;
- the exact approved code and Stage 1 identities were used;
- the observed failure is deterministic and occurs before final access;
- the failing numerical budget is itself a locked model parameter;
- modifying that parameter now would weaken the predeclared model-selection boundary;
- preserving the failure protects the untouched final test and the credibility of subsequent research.

No profitability conclusion can be drawn because the final partition was never evaluated.

## Limitations and authority

This report documents one historical research candidate and does not establish future performance. `REJECTED` does not imply that all related model families are invalid; it means this exact Candidate v0.1 contract did not satisfy its own mandatory pre-final requirements.

No paper, demo, live, private-exchange, credential, leverage, futures, shorting, portfolio-allocation, order-submission, or real-capital authority is granted by this work.
