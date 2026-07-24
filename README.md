# Gemini Trading

Gemini Trading is a hybrid open-core research and paper-execution platform under controlled reconstruction.

## Current Status

- Promotion level: `RESEARCH_ONLY`
- Supported execution modes: `research`, `paper`
- Exchange order submission: disabled
- Profitability: not established

## Public Core

The public repository contains canonical market-data contracts, deterministic research tools, baseline strategy interfaces, portfolio and risk primitives, paper-execution foundations, testing, security controls, and reproducible benchmark evidence.

Private strategy parameters, trained proprietary artifacts, production credentials, production infrastructure, and investor-only evidence are excluded.

## Verified Market Data Core

The repository includes a deterministic public Binance Spot market-data pipeline for research and paper only. Live mode is rejected before provider construction. The pipeline stores exact raw response evidence, validates completed candle sequences, creates deterministic canonical JSONL and dataset identities, supports provider-free replay, and independently verifies persisted evidence.

Command surface:

```text
gemini-trading market-data ingest
gemini-trading market-data replay
gemini-trading market-data verify
```

The Market Data Core establishes data integrity and reproducibility. It does not establish strategy profitability.

See:

- `docs/architecture/adr/0002-market-data-core.md` for the architecture decision and trust boundaries.
- `docs/operations/binance-market-data.md` for exact operator commands, supported intervals, storage layout, replay, verification, and the optional bounded public smoke test.
- `reports/verification/market-data-core-final.md` for final milestone evidence.

## Deterministic Research Engine

The repository includes a single-instrument, long-only, candle-based deterministic research engine. Official evidence uses completed canonical candles, next-candle execution, conservative strict-cross limit fills, explicit fees, spread, slippage, latency, precision, minimums, and deterministic partial fills. Accounting uses `Decimal`, and immutable content-addressed artifacts support provider-free replay and independent verification.

Command surface:

```text
gemini-trading research backtest
gemini-trading research replay
gemini-trading research verify
```

The checked-in scripted fixture strategy is synthetic and non-production. Diagnostic same-close or optimistic-touch policies are non-promotable. OHLCV simulation cannot establish exact intrabar path, queue priority, hidden liquidity, or market impact. Profitability, paper-broker readiness, live-trading readiness, and real-capital readiness are not established.

See:

- `docs/architecture/adr/0003-deterministic-research-engine.md` for the engine decision and trust boundaries.
- `docs/operations/deterministic-backtesting.md` for POSIX and PowerShell operator commands.
- `docs/operations/deterministic-backtesting-step-verification.md` for exact-head and merged-main closure requirements.
- `reports/verification/deterministic-backtesting-final.md` for milestone acceptance evidence.

## Candidate Multi-Model Strategy v0.1

The repository includes a bounded research implementation for the first Candidate multi-model strategy. Its locked scope is BTC/USDT on completed 4-hour candles, long or cash only. It combines point-in-time features, conservative cost-aware labels, deterministic trend and mean-reversion specialists, fold-local calibration, regime-aware arbitration, provider-free comparators, sealed walk-forward evaluation, immutable strategy-study artifacts, replay, and independent verification.

Command surface:

```text
gemini-trading research strategy-evaluate
gemini-trading research strategy-replay
gemini-trading research strategy-verify
```

The Candidate remains `RESEARCH_ONLY` and always reports `promotable:false` at the CLI boundary. Rejection and inconclusive evidence are valid outcomes. No real seven-year historical result, durable profitability, execution readiness, or capital authorization is claimed. Until the concrete end-to-end evaluator is accepted, `strategy-evaluate` fails closed rather than fabricating economic evidence.

See:

- `docs/superpowers/plans/2026-07-24-candidate-multi-model-strategy-v0-1.md` for the approved implementation and verification plan.
- `docs/operations/candidate-multi-model-strategy.md` for the locked protocol, commands, evidence layout, and limitations.
- `docs/operations/candidate-multi-model-strategy-step-verification.md` for exact-head, deterministic acceptance, and merged-main closure requirements.
- `reports/verification/candidate-multi-model-strategy-progress.md` for the current milestone evidence and unresolved work.

## Safety

The current package fails closed when configured for demo, live, production, or an unknown mode. Historical prototype code is preserved under `legacy/prototype_v0/` and is not supported for execution.

The `main` branch requires pull requests and passing `quality` and `gitleaks` checks. Direct pushes, force pushes, and deletions are blocked by repository rules.

The assistant may advise on evidence quality, promotion proposals, limitations, and risk changes, but human authorization remains mandatory for any future real-capital action.

## Development

```bash
uv sync --all-groups --frozen
uv run pre-commit run --all-files
uv run pytest
uv run pyright
```

See:

- `docs/superpowers/specs/2026-07-21-hybrid-open-core-reconstruction-design.md` for the approved architecture.
- `docs/architecture/adr/0001-paper-only-reconstruction-foundation.md` for the paper-only reconstruction decision.
- `reports/security/foundation-verification.md` for observed foundation-verification evidence and limitations.
