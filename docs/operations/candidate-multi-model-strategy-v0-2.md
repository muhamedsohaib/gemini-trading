# Candidate Multi-Model Strategy v0.2 Operations

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Strategy identity: `candidate.multi_model.v0_2`
- Policy identity: `candidate-multi-model-v0.2`
- Market: public Binance Spot `BTCUSDT`
- Decision interval: completed `4h` candles
- Permitted position state: long or cash only
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Leverage, futures, shorting, and autonomous portfolio allocation: excluded
- Future profitability: not established
- Paper, demo, live, and real-capital execution authority: none

Candidate v0.2 is a prospectively governed research candidate. `QUALIFIED` means only that the frozen candidate earned the right to wait for its prospective final era. It does not establish durable profitability and does not create execution authority.

## Provenance and scientific claim boundary

Candidate Multi-Model Strategy is an original project architecture developed through the operator's direction and a ChatGPT-guided design, reasoning, code-generation, testing, and verification process. Committed design lineage, exact Git identities, locked policy identities, content-addressed data/evidence, deterministic replay, and verification establish project provenance and authenticity.

Predictive validity is a separate claim. It may be supported only by preregistered out-of-sample evidence and ultimately by the untouched prospective final era. ChatGPT's contribution is part of the model's engineering provenance; neither authorship nor provenance is evidence of future profitability.

## What changed from v0.1

Candidate v0.1 reached terminal pre-final `REJECTED` because its trend specialist did not converge under the approved v0.1 numerical contract. No v0.1 final-test access occurred.

Candidate v0.2 preserves the v0.1 financial hypothesis, features, labels, mean-reversion specialist, regime logic, arbitration, risk rules, simulated execution economics, controls, baselines, sensitivity family, bootstrap policy, and long/cash scope. The approved trend numerical contract is:

```text
solver      = saga
penalty     = elasticnet
C           = 1.0
l1_ratio    = 0.5
seed        = 1701
tol         = 1e-7
max_iter    = 50000
threads     = 1
```

Canonical compact notation for the two changed numerical controls is `tol=1e-7` and `max_iter=50000`.

Convergence passes only when the solver terminates strictly before `max_iter=50000`. Reaching the ceiling or failing deterministic repetition is a pre-final failure. After v0.2 development evidence is observed, this contract may not be loosened to rescue v0.2; any redesign becomes v0.3.

## Locked development evidence

The v0.2 development dataset is exactly:

```text
[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)
```

No candle at or after `2026-07-01T00:00:00Z` may enter v0.2 training, calibration, development walk-forward evaluation, controls, sensitivity analysis, bootstrap analysis, or model rescue.

The previously untouched v0.1 historical final interval is retired from its old role and may participate in v0.2 development because that reuse was approved before v0.2 development evidence was observed. The genuine v0.2 final test is a new future era.

The fixed calendar produces **12 complete development folds** using 24 months initial training, six months calibration, six months forward development testing, a six-month step, three-candle purge, three-candle embargo, and protected exchange-segment boundaries. All 12 folds are mandatory.

## Development qualification

The strict pre-final suite requires complete, immutable evidence for:

- verified Stage 1 dataset and handoff identity;
- exactly 12 development folds;
- trend convergence and exact repeated-fit determinism for every fold;
- calibration completeness, fold/specialist Platt and return-map artifacts, probability ranges, Brier score, log loss, and ten-bin expected calibration error;
- positive-return and baseline return-to-drawdown fold thresholds;
- profit-concentration and aggregate trade-count limits;
- shuffled-label, delayed-feature, and component-ablation controls;
- 1.5x and 2x execution-cost stress with monotonicity;
- the fixed ten-neighbor sensitivity suite;
- deterministic moving-block bootstrap uncertainty;
- provider-free replay and independent verification.

The closed pre-final classifications are:

- `QUALIFIED`: every mandatory pre-final gate passed on complete valid evidence;
- `REJECTED`: at least one mandatory gate explicitly failed on complete valid evidence;
- `INCONCLUSIVE`: evidence is missing, interrupted, invalid, ambiguous, or insufficient.

`REJECTED` is terminal for Candidate v0.2. Performance-driven tuning or numerical rescue is prohibited. `INCONCLUSIVE` may continue only for a pure infrastructure/evidence interruption that preserves the frozen candidate.

## Content-addressed qualification evidence

The qualification result is portable and content-addressed. Its immutable core includes, among other evidence:

```text
policy.json
configuration.json
development-plan.json
calibration-diagnostics.jsonl
bootstrap.json
case-evidence.jsonl
determinism-receipts.jsonl
qualification-gates.jsonl
qualification-manifest.json
limitations.json
qualification-result.json
```

`calibration-diagnostics.jsonl` contains exactly 24 rows: trend and mean-reversion calibration evidence for each of the 12 folds. Each row persists the Platt artifact, expected-return map, class counts, probability ranges, Brier score, log loss, ten-bin expected calibration error, and a content identity for its ordered calibration population.

`policy.json`, `configuration.json`, and `development-plan.json` are stored as canonical bytes. Their SHA-256 identities are bound into the manifest. The core artifact inventory root is bound into the `qualification_id`, so a change to qualification evidence changes the qualification identity rather than leaving a structurally identical ID behind.

The qualification workflow also packages the referenced `data/research` experiment artifacts with the v0.2 qualification directory. The Stage 1 dataset remains a separate retained artifact; full independent verification requires rehydrating the exact Stage 1 artifact and the qualification bundle into the same `OUTPUT_ROOT`.

## Prospective final era and bridge quarantine

A prospective seal may be created only after the exact merged source, fresh Stage 1 dataset, qualification artifact, and full provider-free verification all agree and the qualification is `QUALIFIED`.

The final start is the **first UTC calendar-month boundary strictly after** the successful frozen-source/pre-final verification milestone. The final end is exactly **18 calendar months** later.

The **bridge interval** is:

```text
[2026-07-01T00:00:00Z, prospective_final_start)
```

Bridge candles are used for neither v0.2 development nor prospective final evaluation. Example only: if final pre-final verification completes on 2026-08-11, the seal is `[2026-09-01T00:00:00Z, 2028-03-01T00:00:00Z)`.

Seal creation reruns full verification and then derives `verified_at` from the operation clock. There is no user-supplied verification timestamp, so an operator cannot backdate the final boundary. The seal reads no future market rows and explicitly binds `candidate.multi_model.v0_2`, `candidate-multi-model-v0.2`, exact code/data/qualification identities, and the computed future interval.

## Prerequisites

1. Merge the reviewed v0.2 implementation through protected `main`.
2. Require complete CI/security verification on the exact merged-main SHA.
3. Use Python 3.12 and the frozen environment:

```bash
uv sync --all-groups --frozen
```

4. Keep `GEMINI_TRADING_MODE=research`.
5. Produce a fresh Stage 1 dataset from the exact merged v0.2 source. An older v0.1 Stage 1 artifact is invalid because its source identity differs.
6. Independently verify the downloaded Stage 1 artifact before approving qualification.

## Stage 1: fresh exact-source dataset

The manually dispatched workflow is:

```text
Sealed BTCUSDT Dataset
.github/workflows/sealed-btcusdt-dataset.yml
```

Dispatch:

```bash
gh workflow run sealed-btcusdt-dataset.yml --ref main
```

Record the exact merged-main source SHA, run ID/attempt, artifact ID/name and artifact SHA-256, dataset ID, dataset handoff inventory root, support hashes, candle boundaries/counts, closure/exclusion/segment counts, replay result, and independent-verification result.

The artifact name has the fixed pattern:

```text
sealed-btcusdt-dataset-<source-sha>-<stage1-run-id>
```

## Owner dataset approval marker

Only after independent Stage 1 verification, add an owner-authored Issue #61 comment containing:

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

The surrounding comment should record artifact and inventory identities and retain the `RESEARCH_ONLY` boundary.

## Stage 2: strict development qualification

The manual workflow is:

```text
Candidate v0.2 Development Qualification
.github/workflows/candidate-v0.2-qualification.yml
```

It accepts exactly four operational identities:

```text
source_commit
dataset_run_id
dataset_artifact_name
dataset_id
```

Dispatch:

```bash
gh workflow run candidate-v0.2-qualification.yml \
  --ref main \
  -f source_commit="$SOURCE_COMMIT" \
  -f dataset_run_id="$DATASET_RUN_ID" \
  -f dataset_artifact_name="$DATASET_ARTIFACT_NAME" \
  -f dataset_id="$DATASET_ID"
```

The workflow checks out the exact merged-main source, requires the exact owner approval marker, downloads and verifies the Stage 1 handoff, runs the 12-fold development-only qualification, verifies the qualification provider-free inside the complete workspace, and uploads:

```text
candidate-v0.2-qualification-<qualification-workflow-run-id>
```

That qualification bundle contains `data/research` and `data/historical-validation/v0-2-qualification`. It does not duplicate the separately retained Stage 1 artifact. The workflow does **not** evaluate future-final rows or authorize execution.

The workflow invokes the fixed direct qualification CLI surface:

```bash
uv run gemini-trading research strategy-v0-2-qualify \
  --handoff "$OUTPUT_ROOT/data/historical-validation/handoff/$DATASET_ID/dataset-handoff.json" \
  --config "$PROJECT_ROOT/tests/fixtures/strategy/candidate-v0.2-config.json" \
  --workflow-run-id "$GITHUB_RUN_ID" \
  --workflow-run-attempt "$GITHUB_RUN_ATTEMPT" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

This command is not an alternative route around the workflow gate; the governed operation must still use the exact merged source, approved Stage 1 identities, and Issue #61 approval marker.

## Rehydrate evidence for independent verification

Use a clean checkout at the exact qualification source commit. Extract the exact Stage 1 artifact and the qualification bundle into the same output root, preserving their `data/...` layouts.

Conceptually the resulting root must contain both:

```text
$OUTPUT_ROOT/data/historical-validation/handoff/<dataset-id>/dataset-handoff.json
$OUTPUT_ROOT/data/research/<experiment-id>/...
$OUTPUT_ROOT/data/historical-validation/v0-2-qualification/<qualification-id>/...
```

The Stage 1 artifact also contains the canonical dataset, raw/provenance/support evidence required by handoff and referenced-experiment verification.

## Provider-free qualification verification

### POSIX

```bash
export GEMINI_TRADING_MODE=research
export PROJECT_ROOT='<clean-checkout-at-exact-source-commit>'
export OUTPUT_ROOT='<rehydrated-evidence-root>'
export QUALIFICATION_ID='<64-character-qualification-id>'

uv run gemini-trading research strategy-v0-2-qualification-verify \
  --qualification-id "$QUALIFICATION_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

### PowerShell

```powershell
$env:GEMINI_TRADING_MODE = 'research'
$ProjectRoot = '<clean-checkout-at-exact-source-commit>'
$OutputRoot = '<rehydrated-evidence-root>'
$QualificationId = '<64-character-qualification-id>'

uv run gemini-trading research strategy-v0-2-qualification-verify `
  --qualification-id $QualificationId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot
```

Full verification checks the exact clean Git commit, qualification core inventory/identity, canonical policy/configuration/development-plan hashes, all 24 calibration receipts, Stage 1 handoff and inventory identity, exact 12-fold case set, and every referenced research experiment/result identity. Any changed byte, missing evidence, source mismatch, incomplete case set, or invalid classification fails closed.

## Prospective seal creation

Only if the fully rehydrated independent verification is `QUALIFIED`, create one exclusive prospective seal. The command reruns the same full bundle verification and captures its own UTC verification milestone; it accepts no timestamp argument.

### POSIX

```bash
uv run gemini-trading research strategy-v0-2-seal-prospective-final \
  --qualification-id "$QUALIFICATION_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

### PowerShell

```powershell
uv run gemini-trading research strategy-v0-2-seal-prospective-final `
  --qualification-id $QualificationId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot
```

The result records `seal_id`, `verified_at`, bridge start/end, prospective final start/end, `promotable:false`, and `execution_authorized:false`. A second seal creation fails closed. If qualification is `REJECTED` or `INCONCLUSIVE`, do not create a seal.

## Evidence retention and reporting

Keep immutable copies of both the Stage 1 artifact and qualification bundle. The compact pre-final report must record exact source, workflow, dataset, inventory, qualification, verification, and conditional seal identities plus failed gates and limitations. Issue #61 remains the governance record for the pre-final milestone and should cross-link any later issue dedicated to the prospective final-era evaluation.

## Claims permitted

- Candidate v0.2 implements the approved prospectively frozen numerical contract.
- Development evidence is limited to the fixed pre-cutoff dataset and 12 mandatory folds.
- Qualification evidence is content-addressed, fail-closed, portable, and provider-free verifiable when rehydrated with exact Stage 1 evidence.
- A `QUALIFIED` result permits only a future prospective test.
- A prospective seal fixes a new 18-month future era without reading future market data.

## Claims not permitted

- Development qualification proves future profitability.
- ChatGPT authorship proves predictive validity.
- The prospective seal itself is a successful market test.
- Bridge data may be inspected to tune or rescue v0.2.
- `QUALIFIED` authorizes paper, demo, live, production, or real-capital execution.
- Any later performance result guarantees durable returns.
