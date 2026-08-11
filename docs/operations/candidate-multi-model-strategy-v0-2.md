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

Candidate v0.2 is a prospectively governed research candidate. It is not a broker, execution agent, signal-selling service, or capital allocator. `QUALIFIED` means only that the frozen candidate earned the right to wait for its prospective final era. It does not establish durable profitability and does not create execution authority.

## Provenance and scientific claim boundary

Candidate Multi-Model Strategy is an original project architecture developed through the operator's direction and a ChatGPT-guided design, reasoning, code-generation, testing, and verification process. Repository commits, specifications, policy identities, content-addressed data, deterministic artifacts, replay, and verification establish provenance and authenticity.

Predictive validity is a separate claim. It may be supported only by preregistered out-of-sample evidence and ultimately by the untouched prospective final era. ChatGPT's contribution is part of the model's engineering provenance, but neither authorship nor model provenance is evidence of future profitability.

## What changed from v0.1

Candidate v0.1 reached a terminal pre-final `REJECTED` state because its trend specialist did not converge under the approved v0.1 numerical contract. No v0.1 final-test access occurred.

Candidate v0.2 preserves the v0.1 financial hypothesis, features, labels, mean-reversion specialist, regime logic, arbitration, risk rules, simulated execution economics, controls, baselines, sensitivity family, bootstrap policy, and long/cash scope. The approved numerical change is limited to the trend specialist:

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

The pre-final qualification is deliberately stricter than the old minimum development gate. It requires complete, immutable evidence for:

- verified Stage 1 dataset and handoff identity;
- exactly 12 development folds;
- trend convergence and exact repeated-fit determinism for every fold;
- calibration completeness;
- positive-return and baseline return-to-drawdown fold thresholds;
- profit-concentration and aggregate trade-count limits;
- shuffled-label, delayed-feature, and component-ablation controls;
- 1.5x and 2x execution-cost stress with monotonicity;
- the fixed ten-neighbor sensitivity suite;
- deterministic moving-block bootstrap uncertainty;
- provider-free replay and independent verification.

The only pre-final classifications are:

- `QUALIFIED`: every mandatory pre-final gate passed on complete valid evidence;
- `REJECTED`: at least one mandatory gate explicitly failed on complete valid evidence;
- `INCONCLUSIVE`: evidence is missing, interrupted, invalid, ambiguous, or insufficient.

`REJECTED` is terminal for Candidate v0.2. Performance-driven tuning or numerical rescue is prohibited. `INCONCLUSIVE` may continue only for a pure infrastructure/evidence interruption that does not alter the candidate.

## Prospective final era and bridge quarantine

A prospective seal may be created only after the exact merged source, fresh Stage 1 dataset, qualification artifact, and provider-free verification all agree and the qualification is `QUALIFIED`.

The final start is the **first UTC calendar-month boundary strictly after** the successful frozen-source/pre-final verification milestone. The final end is exactly **18 calendar months** later.

The interval

```text
[2026-07-01T00:00:00Z, prospective_final_start)
```

is the quarantined bridge interval. Bridge candles are used for neither v0.2 development nor the prospective final evaluation.

Example only: if final pre-final verification completes on 2026-08-11, the seal is `[2026-09-01T00:00:00Z, 2028-03-01T00:00:00Z)`.

Seal creation reads no market rows. It only binds exact code/data/qualification identities and computes the future interval.

## Prerequisites

1. Merge the reviewed v0.2 implementation through protected `main`.
2. Require complete CI/security verification on the exact merged-main SHA.
3. Use Python 3.12 and the frozen environment:

```bash
uv sync --all-groups --frozen
```

4. Keep `GEMINI_TRADING_MODE=research`.
5. Produce a fresh Stage 1 dataset from the exact merged v0.2 source. An older v0.1 Stage 1 artifact is not valid because source identity differs.
6. Independently verify the downloaded Stage 1 artifact before approving qualification.

## Stage 1: fresh exact-source dataset

The existing manually dispatched workflow is:

```text
Sealed BTCUSDT Dataset
.github/workflows/sealed-btcusdt-dataset.yml
```

From GitHub CLI:

```bash
gh workflow run sealed-btcusdt-dataset.yml --ref main
```

After the run completes, record all of the following before qualification:

- exact merged-main source SHA;
- Stage 1 GitHub Actions run ID and attempt;
- artifact ID and exact artifact name;
- dataset ID;
- dataset handoff inventory root;
- canonical-candle, closure, exclusion, segment, provenance, and retrieval-manifest hashes;
- first/last candle boundaries and candle count;
- closure/exclusion counts and segment count;
- replay and independent-verification result.

The artifact name has the fixed pattern:

```text
sealed-btcusdt-dataset-<source-sha>-<stage1-run-id>
```

## Owner dataset approval marker

Only after independent Stage 1 verification, add an owner-authored comment to Issue #61 containing the exact marker:

```text
<!-- candidate-v0.2-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

The surrounding comment should record the artifact and inventory identities and explicitly retain the `RESEARCH_ONLY` boundary.

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

Example GitHub CLI dispatch:

```bash
gh workflow run candidate-v0.2-qualification.yml \
  --ref main \
  -f source_commit="$SOURCE_COMMIT" \
  -f dataset_run_id="$DATASET_RUN_ID" \
  -f dataset_artifact_name="$DATASET_ARTIFACT_NAME" \
  -f dataset_id="$DATASET_ID"
```

The workflow checks out the exact source, requires the exact owner approval marker, downloads the specified Stage 1 artifact, verifies the handoff, runs the 12-fold development-only qualification, verifies the qualification provider-free, and uploads:

```text
candidate-v0.2-qualification-<qualification-workflow-run-id>
```

It does **not** run a future-final evaluator, create market evidence after the development cutoff, or authorize execution.

## Provider-free qualification verification

After downloading and extracting the qualification artifact, verify it independently without a provider:

### POSIX

```bash
export GEMINI_TRADING_MODE=research
export OUTPUT_ROOT='<extracted-artifact-root>'
export QUALIFICATION_ID='<64-character-qualification-id>'

uv run gemini-trading research strategy-v0-2-qualification-verify \
  --qualification-id "$QUALIFICATION_ID" \
  --output-root "$OUTPUT_ROOT"
```

### PowerShell

```powershell
$env:GEMINI_TRADING_MODE = 'research'
$OutputRoot = '<extracted-artifact-root>'
$QualificationId = '<64-character-qualification-id>'

uv run gemini-trading research strategy-v0-2-qualification-verify `
  --qualification-id $QualificationId `
  --output-root $OutputRoot
```

Verification must reproduce the exact qualification ID, inventory root, and classification. Any changed byte, missing artifact, changed structural identity, or invalid classification fails closed.

## Prospective seal creation

Only if independently verified evidence is `QUALIFIED`, create one exclusive prospective seal using the successful verification timestamp in UTC.

### POSIX

```bash
export VERIFIED_AT='<ISO-8601-UTC-verification-timestamp>'

uv run gemini-trading research strategy-v0-2-seal-prospective-final \
  --qualification-id "$QUALIFICATION_ID" \
  --verified-at "$VERIFIED_AT" \
  --output-root "$OUTPUT_ROOT"
```

### PowerShell

```powershell
$VerifiedAt = '<ISO-8601-UTC-verification-timestamp>'

uv run gemini-trading research strategy-v0-2-seal-prospective-final `
  --qualification-id $QualificationId `
  --verified-at $VerifiedAt `
  --output-root $OutputRoot
```

The result records `seal_id`, bridge start/end, prospective final start/end, `promotable:false`, and `execution_authorized:false`. A second seal creation fails closed.

If qualification is `REJECTED` or `INCONCLUSIVE`, do not create a seal.

## Evidence retention and reporting

Keep immutable copies of the Stage 1 dataset artifact and qualification artifact. The compact pre-final report must record exact source, workflow, dataset, inventory, qualification, and conditional seal identities plus all failed gates and limitations. Issue #61 remains the governance record for the pre-final milestone and should cross-link any later issue dedicated to the prospective final-era evaluation.

## Claims permitted

- Candidate v0.2 implements the approved prospectively frozen numerical contract.
- Development evidence is limited to the fixed pre-cutoff dataset and 12 mandatory folds.
- Qualification evidence is content-addressed, fail-closed, and provider-free verifiable.
- A `QUALIFIED` result permits only a future prospective test.
- A prospective seal fixes a new 18-month future era without reading future market data.

## Claims not permitted

- Development qualification proves future profitability.
- ChatGPT authorship proves predictive validity.
- The prospective seal itself is a successful market test.
- Bridge data may be inspected to tune or rescue v0.2.
- `QUALIFIED` authorizes paper, demo, live, production, or real-capital execution.
- Any later performance result guarantees durable returns.
