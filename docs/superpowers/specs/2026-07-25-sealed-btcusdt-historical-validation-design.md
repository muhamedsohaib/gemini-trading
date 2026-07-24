# Sealed BTCUSDT Historical Validation Design

## Status

- Design gate: GitHub Issue #22
- Repository: `muhamedsohaib/gemini-trading`
- Branch: `research/sealed-btcusdt-historical-validation`
- Safety level: `RESEARCH_ONLY`
- Strategy: `candidate.multi_model.v0_1`
- Execution authority: none

## Objective

Implement and operate a two-stage, fail-closed GitHub Actions milestone that produces a verified public Binance Spot BTCUSDT dataset and then runs one sealed Candidate Multi-Model Strategy v0.1 historical study.

The milestone may classify the locked historical evidence as `PASS`, `REJECTED`, or `INCONCLUSIVE`. It must not claim future profitability and must not authorize paper, demo, live, production, exchange-order, credential, leverage, futures, shorting, portfolio-allocation, or real-capital activity.

## Fixed historical scope

- Provider: public Binance Spot endpoints only
- Instrument: `BTCUSDT`
- Base asset: `BTC`
- Quote asset: `USDT`
- Interval: `4h`
- Start, inclusive: `2018-01-01T00:00:00Z`
- End, exclusive: `2026-07-01T00:00:00Z`
- Required candle state: completed only
- Position states: long or cash only
- Runtime mode: `GEMINI_TRADING_MODE=research`
- Locked configuration: `tests/fixtures/strategy/candidate-v0.1-config.json`
- Final untouched test: last 18 calendar months

The historical window and policy identities are immutable for this milestone. Any later change requires a new design gate and a newly sealed final-test partition.

## Design principles

1. **Separate acquisition from evaluation.** Dataset production and final strategy evaluation run as distinct workflows with an explicit artifact contract.
2. **Fail closed.** Missing, malformed, inconsistent, ambiguous, or tampered evidence is rejected.
3. **Bind every result to exact identities.** Code commit, workflow run, configuration, dataset, study, result, and file hashes are recorded.
4. **Prevent final-test leakage.** Development controls must finish before the final partition can be accessed.
5. **Permit no silent retries after final access.** A second evaluation of the sealed final test is rejected.
6. **Keep generated evidence outside Git.** Raw responses, canonical market data, and full study artifacts are workflow artifacts, not tracked repository files.
7. **Preserve compact permanent evidence.** Source-controlled reports retain identities, hashes, run references, classifications, and limitations.

## Architecture

### Component 1: Dataset workflow

A manually dispatched GitHub Actions workflow creates the authoritative dataset evidence.

Responsibilities:

1. Check out one exact commit with full Git history.
2. Assert that the workflow is running from the dedicated research branch or an explicitly approved immutable commit.
3. Install Python 3.12 and the frozen `uv` environment.
4. set `GEMINI_TRADING_MODE=research`.
5. Run the existing public Binance Spot market-data ingestion command for the fixed BTCUSDT window.
6. Persist raw response bytes, page metadata, retrieval manifest, canonical JSONL, dataset manifest, and provenance receipt.
7. Reject incomplete candles and invalid sequences.
8. Run provider-free replay from stored raw evidence.
9. Run independent dataset verification.
10. Build a deterministic handoff manifest.
11. Upload one versioned dataset artifact with maximum supported retention.

The workflow has no credentials and no private exchange access.

### Component 2: Dataset handoff manifest

The handoff manifest is the only supported input to the sealed study workflow.

Required fields:

- schema version;
- repository full name;
- exact source commit SHA;
- source workflow name;
- source workflow run ID and attempt;
- source job identity;
- provider and market type;
- symbol, base asset, quote asset, and interval;
- inclusive start and exclusive end timestamps;
- run ID;
- deterministic dataset ID;
- candle count;
- first and last candle timestamps;
- canonical file path and SHA-256;
- dataset manifest path and SHA-256;
- retrieval manifest path and SHA-256;
- provenance receipt path and SHA-256;
- complete inventory of artifact-relative files and SHA-256 hashes;
- replay classification;
- independent verification classification;
- creation timestamp used only as informational metadata.

The manifest must use canonical encoding and deterministic ordering. Stage 2 rejects missing fields, extra unsupported fields, invalid paths, absolute paths, duplicate paths, hash mismatches, identity mismatches, or an unverified classification.

### Component 3: Sealed study workflow

A second manually dispatched GitHub Actions workflow consumes one verified dataset artifact.

Responsibilities:

1. Check out the exact approved source commit.
2. Download the selected Stage 1 artifact by explicit workflow-run identity.
3. Verify the complete file inventory and handoff manifest.
4. Confirm that code SHA, dataset ID, configuration hash, instrument, interval, and historical window match the approved design.
5. Run every required development fold and control without exposing the final partition.
6. Persist immutable pre-final evidence.
7. Create a final-test access receipt immediately before the final partition is read.
8. Evaluate the final 18 calendar months once.
9. Produce the complete 22-file Candidate study evidence.
10. Run provider-free strategy replay.
11. Run independent strategy verification.
12. Create a compact final workflow report.
13. Upload the study artifact and final report with maximum supported retention.

### Component 4: Final-test access guard

The final-test access guard is a small, independently testable boundary around final-partition access.

It must:

- require verified pre-final evidence;
- bind access to exact code SHA, configuration hash, dataset ID, strategy identity, split identity, workflow run, and attempt;
- write the receipt before returning final-test rows;
- use exclusive creation semantics so an existing receipt cannot be overwritten;
- reject a second access request;
- reject changed identities;
- expose no final-test values before successful receipt persistence;
- provide an exact-resume decision based only on immutable evidence already produced.

The access receipt is evidence of access, not evidence that the study completed.

### Component 5: Compact permanent report

After successful operation, a separate closure change may commit a compact report under `reports/verification/` containing:

- issue and pull-request references;
- exact source commit;
- Stage 1 and Stage 2 workflow identities;
- dataset ID;
- configuration hash;
- study ID and study-result ID;
- final-test access receipt hash;
- artifact inventory root hashes;
- replay and verification outcomes;
- gate counts and final classification;
- explicit limitations and safety boundary.

The report must not contain raw market data, model arrays, predictions, environment dumps, credentials, absolute local paths, or generated evidence copied wholesale.

## Data flow

```text
Public Binance Spot endpoints
        |
        v
Raw immutable response evidence
        |
        v
Canonical normalization and completed-candle filtering
        |
        v
Sequence, continuity, and provenance validation
        |
        v
Provider-free replay
        |
        v
Independent dataset verification
        |
        v
Canonical dataset handoff artifact
        |
        v
Development folds, controls, and pre-final evidence
        |
        v
Final-test access receipt persisted
        |
        v
Single final-test evaluation
        |
        v
22-file strategy-study evidence
        |
        v
Provider-free replay and independent verification
        |
        v
Compact classification and verification report
```

## Development and final-test isolation

The strategy evaluator must expose an explicit pre-final phase or equivalent internal boundary that can complete all development folds and controls without reading final-test candles.

Before final-test access, require:

1. verified dataset and provenance;
2. exact clean code commit;
3. locked configuration hash;
4. complete expanding chronological folds;
5. minimum training and calibration requirements;
6. trend and mean-reversion specialist evidence;
7. regime and arbitration evidence;
8. cash, buy-and-hold, EMA, Donchian, and z-score comparators;
9. component ablations;
10. shuffled-label control;
11. delayed-feature control;
12. cost stress;
13. parameter sensitivity;
14. bootstrap uncertainty;
15. immutable pre-final evidence inventory.

The access guard must make it impossible for ordinary pre-final code paths to materialize the final-test rows.

## Failure handling

### Failures before final-test access

Correctable failures may be fixed and rerun on a new commit. Examples include:

- public provider unavailability or rate limiting;
- dependency installation failure;
- workflow or artifact-service failure;
- ingestion defects;
- invalid, missing, duplicated, reversed, or gapped candles;
- replay or verification defects;
- pre-final implementation defects.

Any correction that changes source code, dependencies, workflow definitions, or configuration requires a new exact commit and complete repetition of Stage 1 verification before Stage 2.

### Failures after final-test access

After the access receipt exists:

- no feature, label, model, calibration, regime, arbitration, threshold, split, cost, stress, control, or gate may change;
- a completed result is final;
- a strategy or gate failure is final;
- a new evaluation using the same sealed final partition is prohibited;
- an infrastructure failure yields `INCONCLUSIVE` unless immutable completed evidence supports exact provider-free continuation without recomputing the accessed final evaluation;
- missing or ambiguous evidence fails closed.

Automatic or manual workflow reruns must not bypass the access receipt. A new workflow attempt that detects an existing receipt rejects fresh final-test evaluation.

## Exact-resume policy

Exact resume is permitted only when all of the following hold:

- code SHA, dataset ID, configuration hash, policy identity, split identity, and receipt identity are unchanged;
- final evaluation outputs required for continuation already exist as immutable files;
- every required file hash verifies;
- continuation performs no provider request and no recalculation of final predictions, decisions, orders, fills, or metrics;
- continuation is limited to deterministic packaging, replay, verification, or artifact upload;
- the verifier explicitly classifies the resume as safe.

Otherwise, the outcome is `INCONCLUSIVE`.

## Result semantics

### `PASS`

All locked historical gates pass and the evidence verifies. This permits only a proposal for a separate paper-trading design gate. It does not promote the strategy automatically.

### `REJECTED`

One or more mandatory gates fail on complete valid evidence. Rejection is a valid final outcome and must be preserved.

### `INCONCLUSIVE`

The evidence is incomplete, invalid, ambiguous, interrupted after final access, or insufficient for a defensible result.

No classification proves future profitability.

## Repository changes

Implementation is expected to add or modify only the focused surfaces required by this design:

- two manually dispatched GitHub Actions workflows;
- a deterministic dataset handoff-manifest module;
- a final-test access-receipt and access-guard module;
- minimal evaluator refactoring required to enforce pre-final isolation;
- compact safe workflow-report generation;
- operator documentation;
- unit, integration, tamper, and workflow-contract tests.

Unrelated strategy changes and broad refactoring are out of scope.

## Workflow security and permissions

- Default workflow permissions are `contents: read`.
- No repository secret is required for Binance public data.
- No private endpoint or authenticated exchange request is permitted.
- Artifact upload and download use GitHub-provided workflow identity only.
- Workflow dispatch inputs are narrow, validated, and identity-based; they do not permit arbitrary symbols, windows, commands, paths, or configuration overrides.
- Shell commands use fixed arguments and quoted variables.
- Third-party actions are pinned to immutable versions or commit SHAs according to repository policy.
- Logs emit safe identifiers and relative paths only.

## Artifact policy

Generated evidence remains excluded from Git:

- `data/raw/`;
- `data/canonical/`;
- `data/research/`;
- `data/strategy-studies/` when generated locally or in CI.

Each workflow artifact includes a canonical inventory and root hash. Retention uses the maximum duration supported by repository settings. Successful artifacts must be downloaded promptly and verified independently because GitHub artifact storage is not permanent archival storage.

## Testing strategy

### Unit tests

Cover:

- canonical handoff-manifest encoding;
- artifact-relative path validation;
- duplicate and traversal-path rejection;
- inventory hashing;
- commit, dataset, configuration, strategy, window, and workflow identity mismatches;
- access-receipt canonical encoding and exclusive creation;
- second-access rejection;
- final rows unavailable before receipt persistence;
- exact-resume eligibility and rejection reasons;
- safe report output.

### Integration tests

Use synthetic fixtures to prove:

- Stage 1-like evidence can be replayed, verified, packed, unpacked, and reverified;
- Stage 2 accepts only the verified handoff contract;
- pre-final evaluation does not access final rows;
- one final access produces one receipt;
- study evidence replays and verifies provider-free;
- tampering or missing files fail closed.

Synthetic tests verify architecture and reproducibility only; they do not establish profitability.

### Workflow-contract tests

Validate:

- YAML syntax;
- manual-dispatch-only operation for sealed workflows;
- least-privilege permissions;
- pinned actions;
- fixed historical scope;
- no arbitrary command or path inputs;
- explicit artifact retention;
- complete checks before final access;
- safe behavior across workflow attempts.

### Existing repository gates

The implementation pull request must pass:

- `uv sync --all-groups --frozen`;
- Ruff format check;
- Ruff lint;
- strict Pyright;
- complete pytest suite;
- package build;
- pip-audit;
- tracked-file policy;
- detect-secrets;
- Gitleaks.

## Acceptance criteria

Implementation is accepted only when:

1. both workflow definitions and all supporting code are reviewed through a protected pull request;
2. existing CI passes at the exact reviewed head;
3. manifest, access-boundary, exact-resume, tamper, and workflow-contract tests pass;
4. a bounded synthetic or fixture-based dry run proves the two-stage architecture without claiming historical performance;
5. the workflows remain manual and no real final-test evaluation occurs during implementation acceptance;
6. generated data and studies are absent from tracked files;
7. documentation includes exact operator and verification procedures;
8. merged-main verification passes at the exact merge commit;
9. Issue #22 remains open until the real Stage 1 and Stage 2 operation is complete and independently verified.

## Operational sequence after implementation merge

1. Dispatch Stage 1 against the exact merged-main implementation commit.
2. Inspect the Stage 1 result and independently verify the dataset artifact.
3. Record and approve the exact dataset ID and Stage 1 workflow identity in Issue #22.
4. Dispatch Stage 2 once with only those approved identities.
5. Preserve the final-test access receipt and study artifact.
6. Independently replay and verify the completed study.
7. Commit a compact closure report through a separate pull request.
8. Close Issue #22 only after exact merged-main and artifact verification.

## Non-goals

This design does not:

- alter Candidate strategy policy or thresholds;
- tune the strategy after observing final results;
- add exchange credentials or private APIs;
- place paper, demo, or live orders;
- support leverage, futures, shorting, or multiple instruments;
- establish future profitability;
- approve capital allocation;
- create permanent artifact storage outside the existing GitHub workflow mechanism.

## Safety statement

This milestone remains `RESEARCH_ONLY`. The system has no exchange-order submission authority. A historical `PASS` is evidence for review, not execution authorization. Every later paper, demo, live, or real-capital phase requires a separate written design gate, independent verification, and explicit human approval.
