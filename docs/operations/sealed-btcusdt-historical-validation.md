# Sealed BTCUSDT Historical Validation Operations

## Safety and authority

This procedure is `RESEARCH_ONLY`. It uses public Binance Spot market data. It has no credentials and no real-capital authorization. It has no private endpoints, exchange-order submission, paper brokerage, demo or live authority, leverage, futures, shorting, or portfolio allocation.

A historical `PASS` is evidence for a separate paper-trading design review only. It does not prove future profitability and does not promote the Candidate automatically. `REJECTED` and `INCONCLUSIVE` are valid final outcomes.

## Fixed scope

The workflow scope is immutable:

- provider: public Binance Spot;
- instrument: `BTCUSDT`, base `BTC`, quote `USDT`;
- interval: completed `4h` candles;
- window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`;
- Candidate: `candidate.multi_model.v0_1`;
- policy: `candidate-multi-model-v0.1`;
- configuration: `tests/fixtures/strategy/candidate-v0.1-config.json`;
- final untouched test: the last 18 calendar months, accessed once.

Changing any scope, policy, configuration, split, cost, feature, label, model, control, threshold, or gate requires a new written design gate and newly sealed final test.


## Verified exchange-closure and partial-candle evidence

The fixed historical window contains 20 independently verified Binance Spot interruption declarations in `config/market-data/sealed-btcusdt-4h-exchange-closures.json` using `exchange-closure-manifest-v3`.

The immutable fixed identity is:

- 20 structurally valid partial-candle provider rows;
- 16 fully absent canonical opens;
- 36 unavailable canonical `4h` slots in total;
- 20 ordered exact exclusions in `candle-exclusion-manifest-v1`;
- 21 maximal continuous segments in `candle-segment-manifest-v1`;
- 18,582 completed canonical candles in `candle-dataset-v4`;
- first canonical open `2018-01-01T00:00:00Z`;
- last canonical open `2026-06-30T20:00:00Z`;
- segment boundaries `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`.

A closure may contain zero fully missing opens. In that case the partial candle is unavailable, `fully_missing_start` equals `resumed_open`, and `unavailable_candle_count` remains one. Every declaration must satisfy exact timeframe arithmetic and must match exactly one immutable provider row by open time, actual close, expected close, normalized values, page location, row location, and SHA-256.

Raw provider pages and excluded rows remain byte-for-byte immutable. The pipeline never inserts, forward-fills, interpolates, zero-fills, repairs, pads, or otherwise fabricates a candle. Missing, duplicate, changed, reordered, shifted, additional, overlong, undeclared, overlapping, touching, or unused evidence fails closed.

`candle-dataset-v4` binds canonical candle bytes, closure-manifest bytes, exclusion-manifest bytes, and segment-manifest bytes. `sealed-dataset-handoff-v4` additionally binds all ordered `(closure_id, provider_row_sha256)` pairs, the exact counts, all segment boundaries, the first and last opens, replay completion, independent verification, and the sorted artifact inventory root.

Features, labels, folds, strategy schedules, simulator orders, positions, returns, and final-test access cannot cross a segment boundary. Feature warm-up restarts after every interruption. Label outcomes crossing a boundary are omitted. A noncash account or active order at a boundary is a terminal validation failure; no synthetic liquidation is allowed. Every approved interruption precedes the final 18-month test. Any interruption intersecting that final partition requires a new written design gate.

The fixed Stage 1 commands are:

```text
gemini-trading research dataset-ingest --project-root <repo> --output-root <artifact-root>
gemini-trading research dataset-replay --run-id <retrieval-run-id> --output-root <artifact-root>
gemini-trading research dataset-verify --dataset-id <dataset-id> --run-id <retrieval-run-id> --output-root <artifact-root>
```

There is no operator-provided closure or exclusion path, environment override, dispatch input, or remote policy source. Earlier v1-v3 datasets and handoffs are invalid for the revised study. A completely new Stage 1 v4 run is mandatory after protected merge and exact-main verification.

## Workflows

The two manually dispatched workflows are:

1. `Sealed BTCUSDT Dataset`
2. `Sealed BTCUSDT Candidate Study`

The dataset workflow has no operator inputs. It always ingests the fixed scope above.

The study workflow accepts exactly four identity inputs:

- `source_commit` — the approved exact merged-main implementation SHA;
- `dataset_run_id` — the Stage 1 GitHub Actions run ID;
- `dataset_artifact_name` — the exact Stage 1 artifact name;
- `dataset_id` — the verified canonical dataset SHA-256 identity.

It accepts no symbol, interval, date, configuration, command, output path, or strategy-parameter override.

## Required implementation gate

Do not run real history from a feature branch or unverified commit.

1. Merge the implementation through protected `main`.
2. Verify the exact merged-main SHA with frozen dependencies, Ruff, Pyright, the complete pytest suite, package build, dependency audit, tracked-file policy, detect-secrets, workflow-contract tests, CLI help surfaces, Gitleaks, clean tree, and unchanged exact HEAD.
3. Record that exact operational SHA on Issue #22.

Only the recorded SHA may be used for Stage 1. A newer `main` commit requires a new approval record.

## Stage 1 — verified dataset production

In GitHub:

```text
Actions -> Sealed BTCUSDT Dataset -> Run workflow -> main
```

The workflow must complete these steps in order:

1. assert the exact clean checked-out commit;
2. ingest the fixed BTCUSDT history;
3. replay stored raw evidence without network access;
4. independently verify the canonical dataset;
5. build the strict dataset handoff manifest;
6. upload `sealed-btcusdt-dataset-<source-sha>-<run-id>`.

After completion, inspect every job step. Download the artifact immediately and independently verify its inventory and hashes, including `exchange-closures.json`, `candle-exclusions.json`, `candle-segments.json`, `dataset-manifest.json`, canonical candles, retrieval evidence, provenance, and `dataset-handoff.json`. GitHub Actions artifacts are retained for 90 days in these workflows and are not permanent archival storage.

Record the following exact Stage 1 evidence on Issue #22:

- source commit;
- workflow run ID and attempt;
- artifact name and artifact ID;
- retrieval run ID;
- dataset ID and `candle-dataset-v4` schema;
- closure-manifest path, SHA-256, and `exchange-closure-manifest-v3` schema;
- exclusion-manifest path and SHA-256;
- segment-manifest path and SHA-256;
- closure count `20`, exclusion count `20`, and segment count `21`;
- all ordered closure IDs and excluded provider-row SHA-256 identities;
- all segment boundary indices `(18, 227, 1047, 1092, 1733, 1887, 2593, 2975, 3524, 4062, 4133, 4650, 5042, 5425, 6483, 6791, 7198, 7228, 7886, 8168)`;
- unavailable canonical-slot count `36` and fully absent-open count `16`;
- candle count `18,582`;
- first open `2018-01-01T00:00:00Z` and last open `2026-06-30T20:00:00Z`;
- inventory root SHA-256;
- byte-identical replay result;
- independent verification result.

Stage 2 remains prohibited until the repository owner posts an Issue #22 comment containing this exact machine-readable marker:

```text
<!-- sealed-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id> -->
```

The same approval comment must state the artifact name, artifact ID, retrieval run ID, inventory root, candle boundaries, replay outcome, verification outcome, and `RESEARCH_ONLY` boundary. The workflow accepts the marker only when the comment author is the repository owner.

## Stage 2 — one sealed Candidate study

Dispatch `Sealed BTCUSDT Candidate Study` once using the four approved identities.

The workflow barriers are:

1. `validate-dataset` requires the exact owner-authored Issue #22 approval marker, downloads the exact Stage 1 artifact, and recomputes the handoff inventory, source commit, run ID, and dataset ID.
2. `prepare` performs all development folds, baselines, specialists, controls, stresses, sensitivity, and uncertainty work without final-test execution. It publishes immutable pre-final evidence.
3. `authorize-final` rejects workflow attempts other than `1`, checks that no bot-authored repository seal exists for the pre-final ID, posts the repository seal, persists the stable local seal and durable access receipt, and does not load final-test rows.
4. `finalize` requires the matching receipt run and attempt, performs the one authorized final evaluation, then replays and independently verifies the completed study provider-free.

The repository-side one-time seal uses this exact marker:

```text
<!-- sealed-final-access:<pre-final-id> -->
```

The seal is posted by `github-actions[bot]` on Issue #22 before the local receipt is created. Workflow-level concurrency serializes all Stage 2 runs, and every later run checks for this marker. A matching bot-authored marker blocks a fresh final evaluation even though GitHub Actions runners and artifacts use separate filesystems.

The local evidence store also creates a stable run-independent seal keyed by the code commit, dataset, policy, configuration, split, and pre-final identities. Changing only the workflow run ID or attempt cannot create a second local authorization on a shared evidence root.

The repository seal and local seal are intentionally fail-closed. If the repository comment is posted but receipt persistence or later evaluation fails, the seal remains and the result is `INCONCLUSIVE`; deleting or bypassing the seal is not an authorized retry procedure.

The access receipt is written before final-test rows are materialized. After it exists:

- fresh final evaluation is prohibited;
- manual or automatic reruns must not reopen the final partition;
- changed identities fail closed;
- a complete result is final;
- an interrupted or ambiguous result is `INCONCLUSIVE` unless complete immutable final outputs support exact provider-free continuation.

## Exact resume

`strategy-resume` is not permission to evaluate again. It is limited to provider-free verification, packaging, comparison, or upload of already-complete immutable final outputs.

Exact resume requires unchanged code, dataset, policy, configuration, split, pre-final, receipt, run, and attempt identities, plus a complete verified final-output inventory. It must not construct a market-data provider, fit models, regenerate predictions, rerun final cases, or recompute final economic metrics. Otherwise, the result is `INCONCLUSIVE`.

## Immediate evidence preservation

After Stage 2:

1. download the pre-final, final-access, and study artifacts immediately;
2. independently recompute all inventories and SHA-256 hashes;
3. preserve the Issue #22 dataset-approval and repository-seal comments;
4. run provider-free strategy replay;
5. run independent strategy verification;
6. preserve the stable local seal, durable receipt, repository-seal receipt, and all 22 canonical study files;
7. record the study ID, result ID, classification, gate counts, artifact root hashes, and verification checks.

Do not rely on workflow logs or status strings alone. The byte sequences, issue markers, and hashes are the evidence.

## Result semantics

- `PASS`: all locked historical gates passed on complete verified evidence. This permits only a proposal for a separate paper-trading design gate.
- `REJECTED`: one or more mandatory gates failed on complete verified evidence.
- `INCONCLUSIVE`: evidence was incomplete, invalid, ambiguous, interrupted after final access, or insufficient for a defensible decision.

No classification authorizes execution or capital.

## Closure sequence

1. Create a separate compact closure-report pull request containing identities, hashes, workflow references, Issue #22 marker comments, classification, gate outcomes, limitations, and the unchanged safety boundary.
2. Verify the closure report at its exact reviewed head and exact merged-main commit.
3. Close Issue #22 only after the dataset artifact, repository seal, stable local seal, durable receipt, 22-file study, replay, and independent verification all agree.

Until both real workflows complete and their downloaded artifacts verify, the repository has implementation evidence only and no real historical Candidate result.
