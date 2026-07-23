# Deterministic Backtesting Operations

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Supported runtime modes: `research` and `paper`
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Included strategy: synthetic fixture only; not a production strategy
- Profitability and real-capital readiness: not established

The official evidence policy uses completed candles, next-candle timing, conservative strict-cross limit fills, explicit costs, deterministic partial fills, and Decimal accounting. Same-close timing or optimistic-touch fills are diagnostic and always non-promotable.

## Prerequisites

1. Use Python 3.12 and install the locked environment:

```bash
uv sync --all-groups --frozen
```

2. Keep the repository worktree clean. Experiment identity records the exact Git commit.
3. Ingest and verify a canonical dataset with the Market Data Core.
4. Select an output root containing `data/canonical/<dataset-id>/` and where research artifacts may be written.
5. Set `GEMINI_TRADING_MODE=research` or `paper`. Live, demo, production, and unknown modes fail closed.

## Configuration

The checked-in acceptance fixture is:

```text
tests/fixtures/research/official-fixture-config.json
```

It contains:

- `initial_cash` and `random_seed`;
- fee, spread, slippage, latency, precision, minimum, liquidity-participation, and order-lifetime assumptions;
- official timing and fill-policy identifiers;
- a scripted synthetic strategy used only to verify engine behavior.

The diagnostic fixture demonstrates non-promotable timing/fill policies:

```text
tests/fixtures/research/diagnostic-fixture-config.json
```

Do not treat either fixture as a trading recommendation or evidence of strategy edge.

## POSIX commands

Set reusable values:

```bash
export GEMINI_TRADING_MODE=research
export DATASET_ID='<64-character-lowercase-dataset-id>'
export OUTPUT_ROOT="$PWD"
export PROJECT_ROOT="$PWD"
export CONFIG='tests/fixtures/research/official-fixture-config.json'
```

Run a deterministic backtest:

```bash
uv run gemini-trading research backtest \
  --dataset-id "$DATASET_ID" \
  --config "$CONFIG" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

Copy the returned `experiment_id`, then replay without a provider or network:

```bash
export EXPERIMENT_ID='<returned-experiment-id>'
uv run gemini-trading research replay \
  --experiment-id "$EXPERIMENT_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

Independently verify stored evidence:

```bash
uv run gemini-trading research verify \
  --experiment-id "$EXPERIMENT_ID" \
  --project-root "$PROJECT_ROOT" \
  --output-root "$OUTPUT_ROOT"
```

## PowerShell commands

```powershell
$env:GEMINI_TRADING_MODE = 'research'
$DatasetId = '<64-character-lowercase-dataset-id>'
$OutputRoot = (Get-Location).Path
$ProjectRoot = (Get-Location).Path
$Config = 'tests/fixtures/research/official-fixture-config.json'

uv run gemini-trading research backtest `
  --dataset-id $DatasetId `
  --config $Config `
  --project-root $ProjectRoot `
  --output-root $OutputRoot
```

Copy the returned experiment identity:

```powershell
$ExperimentId = '<returned-experiment-id>'

uv run gemini-trading research replay `
  --experiment-id $ExperimentId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot

uv run gemini-trading research verify `
  --experiment-id $ExperimentId `
  --project-root $ProjectRoot `
  --output-root $OutputRoot
```

## Output interpretation

Successful commands emit one compact, sorted JSON object to standard output.

`backtest` and `replay` return:

- `status`;
- `experiment_id`;
- `result_id`;
- `promotable`.

`verify` additionally returns a sorted `checks` list. A promotable result means only that the experiment used the official conservative evidence policy and passed integrity/replay checks. It does not mean the strategy is profitable or suitable for capital.

Classified failures emit one compact JSON object to standard error and return exit code 2. Tracebacks, credentials, provider bodies, and absolute local paths are not emitted.

## Storage layout

Research evidence is content-addressed below:

```text
research/experiments/<experiment-id>/
```

The persisted set includes the experiment manifest, simulation configuration, event ledger, orders, fills, account/equity evidence, metrics, result manifest, and related hashes. Existing immutable content may be re-read but conflicting content is rejected.

## Replay and verification trust boundary

Replay reads only local canonical dataset bytes and stored research artifacts. It resolves the current clean Git commit, reconstructs the supported synthetic fixture strategy, reruns the kernel, and compares regenerated core artifacts byte for byte. No exchange provider is constructed.

Verification independently checks canonical hashes, stored artifact hashes, experiment/result identities, terminal classification, promotability, and replay equivalence. Missing, malformed, tampered, or commit-mismatched evidence fails closed.

## Known modelling limits

Candle-only simulation cannot establish intrabar path, queue priority, exact bid/ask history, hidden liquidity, adverse selection, or nonlinear market impact. Volume participation is deterministic but is not an order-book reconstruction. These limitations must remain visible in any future strategy review.
