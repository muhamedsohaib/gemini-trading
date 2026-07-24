# Candidate Multi-Model Strategy v0.1 Operations

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Market scope: `BTC/USDT` Binance Spot
- Decision interval: completed `4h` candles
- Permitted position state: long or cash only
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Leverage, futures, shorting, and portfolio allocation: excluded
- Profitability and real-capital readiness: not established

Candidate v0.1 is a deterministic research candidate, not a broker, signal-selling service, or autonomous capital allocator. It consumes verified canonical candle evidence and may enter long, remain long, exit to cash, or abstain only inside the existing simulation engine. It has no paper, demo, live, or production order authority.

## Historical evaluation protocol

A promotable historical study requires at least **seven years** of continuous verified BTC/USDT 4h history. Development uses expanding chronological folds with a minimum 24-month training window, six-month calibration, six-month forward development test, six-month step, three-candle purge, three-candle embargo, and at least five development folds.

The final untouched test is the last **18 calendar months**. It is sealed during development and may be evaluated exactly once for the locked Candidate v0.1 policy and configuration identities. Missing history, incomplete folds, insufficient calibration classes, missing controls, changed identities, or a second final-test access fails closed.

Official execution evidence uses completed candles, next-candle timing, conservative fills, explicit fees, half-spread, slippage, latency, tick and quantity precision, minimum order constraints, liquidity participation, and deterministic accounting. Same-close timing, optimistic fills, zero-cost assumptions, or altered policy identities are rejected.

## Candidate architecture

The locked research pipeline contains:

1. a point-in-time 42-candle feature registry;
2. conservative cost-aware labels;
3. deterministic trend and mean-reversion specialist models;
4. fold-local probability calibration and expected-return mapping;
5. completed-candle regime classification;
6. deterministic long-or-cash arbitration with abstention, hysteresis, cooldown, maximum hold, and ATR protection;
7. cash, buy-and-hold, EMA 20/50, Donchian 20/10, and z-score mean-reversion comparators;
8. ablations, delayed-feature and shuffled-label controls, cost stress, parameter sensitivity, bootstrap uncertainty, and mandatory promotion gates;
9. immutable 22-file strategy-study evidence;
10. provider-free replay and independent verification.

Model artifacts are canonical, non-executable evidence. The existing research engine remains the sole authority for orders, fills, precision, liquidity, accounting, and economic metrics.

## Prerequisites

1. Use Python 3.12 and install the locked environment:

```bash
uv sync --all-groups --frozen
```

2. Keep the repository worktree clean. Study and referenced experiment evidence is bound to the exact Git commit.
3. Set `GEMINI_TRADING_MODE=research`. Demo, live, production, and unknown modes fail before configuration, dataset, provider, or model work.
4. Ingest and independently verify a canonical BTCUSDT 4h dataset.
5. Use the locked configuration:

```text
tests/fixtures/strategy/candidate-v0.1-config.json
```

6. Use an output root where immutable canonical, research-experiment, and strategy-study evidence may be written.

## Command surface

The three Candidate commands are:

```text
research strategy-evaluate
research strategy-replay
research strategy-verify
```

### POSIX

```bash
export GEMINI_TRADING_MODE=research
export DATASET_ID='<64-character-lowercase-dataset-id>'
export PROJECT_ROOT="$PWD"
export OUTPUT_ROOT="$PWD"
export CONFIG='tests/fixtures/strategy/candidate-v0.1-config.json'

uv run gemini-trading research strategy-evaluate \
  --dataset-id "$DATASET_ID" \
  --config "$CONFIG" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

Copy the returned study identity, then replay and verify local evidence:

```bash
export STUDY_ID='<returned-study-id>'

uv run gemini-trading research strategy-replay \
  --study-id "$STUDY_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"

uv run gemini-trading research strategy-verify \
  --study-id "$STUDY_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

### PowerShell

```powershell
$env:GEMINI_TRADING_MODE = 'research'
$DatasetId = '<64-character-lowercase-dataset-id>'
$ProjectRoot = (Get-Location).Path
$OutputRoot = (Get-Location).Path
$Config = 'tests/fixtures/strategy/candidate-v0.1-config.json'

uv run gemini-trading research strategy-evaluate `
  --dataset-id $DatasetId `
  --config $Config `
  --project-root $ProjectRoot `
  --output-root $OutputRoot

$StudyId = '<returned-study-id>'

uv run gemini-trading research strategy-replay `
  --study-id $StudyId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot

uv run gemini-trading research strategy-verify `
  --study-id $StudyId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot
```

## Output interpretation

`strategy-evaluate` and `strategy-replay` emit one compact sorted JSON object containing exactly:

- `classification`;
- `promotable`;
- `status`;
- `study_id`;
- `study_result_id`.

`strategy-verify` additionally returns safe sorted check names. It does not emit raw arrays, provider responses, environment dumps, credentials, tracebacks, or absolute paths.

The CLI always reports `promotable:false`. Promotion remains a separate evidence-review decision, and **rejection is a valid outcome**. `INCONCLUSIVE` means the available study cannot support promotion. `REJECTED` means one or more mandatory conditions failed. Neither classification authorizes execution.

A deterministic synthetic acceptance run checks architecture and reproducibility only. It **does not establish durable profitability**. A passed historical study would still not prove future returns, eliminate model risk, or authorize capital.

## Immutable evidence and replay

Completed studies are stored below:

```text
data/strategy-studies/<study-id>/
```

The exact set contains 22 canonical files covering the study manifest, locked policy, feature registry and matrix, labels, split plan, folds, model and calibration evidence, predictions, regimes, arbitration decisions, referenced experiments, baselines, ablations, controls, cost stress, sensitivity, bootstrap, promotion gates, limitations, and result manifest.

Replay reads only immutable local evidence. It reconstructs the closed supported strategy registry, verifies the exact clean Git commit, regenerates canonical bytes, and requires byte-for-byte equivalence. No exchange provider or network endpoint is constructed.

Verification independently checks dataset and provenance references, artifact hashes, component, study, experiment, and result identities, final-test single-use receipt, complete mandatory gates, referenced research experiments, exact replay equivalence, and exact code commit. Missing, malformed, tampered, incomplete, or commit-mismatched evidence fails closed.

## Current milestone limitation

The CLI, immutable storage, replay, and verification surfaces are implemented. Until the concrete dataset-to-study evaluator and Task 12 end-to-end acceptance are complete, `strategy-evaluate` deliberately fails closed rather than creating synthetic economic evidence. This limitation must be removed only by a tested real pipeline, never by fabricated hashes or placeholder results.

No real seven-year Candidate v0.1 historical study has been claimed at this stage.

## Modelling limitations

OHLCV candles do not reveal exact intrabar path, historical bid/ask sequence, queue priority, hidden liquidity, adverse selection, or nonlinear market impact. Regime labels and specialist models can be structurally correct while being economically ineffective. Multiple comparisons, non-stationarity, exchange changes, data gaps, and future cost changes remain material risks.

Even a complete and verified study remains historical research. Any later paper, demo, or real-capital phase requires a separate written gate, independent review, explicit human authorization, and newly defined failure conditions.
