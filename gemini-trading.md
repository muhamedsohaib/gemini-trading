# gemini-trading

A reproducibility-first research harness for BTC/USDT strategy work. Every dataset,
backtest and evaluation it produces can be independently replayed and verified from
committed evidence, without re-contacting the exchange.

**Status: research only.** Exchange order submission is disabled. Profitability is not
established. Two strategy candidates have been formally rejected and their negative
evidence is committed to this repository.

## What it does

Three subsystems, each usable on its own:

**Market data** — pulls Binance Spot candles, stores the raw provider response as
evidence, validates that the candle sequence is complete and closed, then writes
content-addressed canonical JSONL with a dataset identity. Once a dataset exists, every
downstream run replays from it. No provider call, no drift, no silent revision.

**Backtest engine** — single-instrument, long-only, next-candle execution. `Decimal`
accounting throughout, with fees, spread, slippage, latency and exchange precision
modelled explicitly rather than assumed away. Output artifacts are immutable and carry
verification receipts.

**Strategy research** — a multi-model trend and mean-reversion system with regime
arbitration, evaluated under sealed walk-forward splits so the evaluator cannot see the
data the decision is made on.

## Quick start

```bash
uv sync --all-groups --frozen

# pull and canonicalise a dataset
uv run gemini-trading market-data ingest --symbol BTCUSDT --interval 1h \
  --start 2024-01-01 --end 2024-12-31

# verify someone else's dataset reproduces byte-for-byte
uv run gemini-trading market-data verify --dataset <id>

# run a backtest against it
uv run gemini-trading research backtest --dataset <id>
```

Python 3.12, `uv` + hatchling. Runtime dependencies are deliberately minimal — numpy,
scikit-learn, threadpoolctl.

## Layout

| Path | Responsibility |
|---|---|
| `src/gemini_trading/data/` | Providers, ingestion, normalisation, validation, storage, dataset identity, verification |
| `src/gemini_trading/domain/` | Candle, order, fill, account, instrument, timeframe |
| `src/gemini_trading/execution/simulator/` | Cost, fill, liquidity and precision models |
| `src/gemini_trading/research/` | Engine, accounting, metrics, artifacts, replay |
| `src/gemini_trading/strategy/` | Features, splits, arbitration, sealed evaluation, candidate stages |
| `src/gemini_trading/safety/` | Execution-mode gate, repository policy, regression guards |
| `tests/` | 596 tests across unit, integration, property, regression, acceptance |
| `docs/` | ADRs and operations runbooks |
| `legacy/prototype_v0/` | Quarantined earlier prototype; import is blocked by repository policy |

## How correctness is enforced

CI runs ruff, pyright in strict mode, pytest with coverage, a build, `pip-audit`, a
tracked-file policy validator, detect-secrets and gitleaks. Strategy qualification runs
are governed by their own workflows so a candidate cannot be promoted by hand.

Generated data — raw, canonical, research and strategy-study output — is gitignored. The
repository holds code, evidence and decisions, not results anyone could regenerate.

## Known gaps

- `execution/` contains only the simulator. There is no paper broker yet.
- Candidate v0.3 is in qualification. v0.1 and v0.2 are terminally rejected.
