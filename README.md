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

The repository includes the first bounded Candidate multi-model research strategy for BTC/USDT on completed 4-hour candles, long or cash only. It combines point-in-time features, conservative cost-aware labels, deterministic trend and mean-reversion specialists, fold-local calibration, regime-aware arbitration, provider-free comparators, sealed walk-forward evaluation, immutable strategy-study artifacts, replay, and independent verification.

Candidate v0.1 reached a terminal pre-final `REJECTED` state under its governed historical validation. On the corrected approved source, the trend specialist still reached the v0.1 `max_iter=10000` ceiling during development preparation. The final authorization and finalization jobs were skipped, so **no v0.1 final-test access occurred**. The frozen v0.1 candidate was not tuned or rescued after observing that evidence.

Diagnostic command surface:

```text
gemini-trading research strategy-evaluate
gemini-trading research strategy-replay
gemini-trading research strategy-verify
```

Sealed historical-validation command surface:

```text
gemini-trading research dataset-ingest
gemini-trading research dataset-replay
gemini-trading research dataset-verify
gemini-trading research strategy-handoff
gemini-trading research strategy-prepare
gemini-trading research strategy-authorize-final
gemini-trading research strategy-finalize
gemini-trading research strategy-resume
```

The Candidate remains `RESEARCH_ONLY` and always reports `promotable:false` at the CLI boundary. Rejection and inconclusive evidence are valid outcomes. No durable profitability, execution readiness, or capital authorization is claimed.

See:

- `docs/superpowers/plans/2026-07-24-candidate-multi-model-strategy-v0-1.md` for the approved Candidate implementation plan.
- `docs/operations/candidate-multi-model-strategy.md` for the locked Candidate protocol, commands, evidence layout, and limitations.
- `docs/operations/candidate-multi-model-strategy-step-verification.md` for Candidate exact-head and merged-main closure requirements.
- `docs/operations/sealed-btcusdt-historical-validation.md` for the two-stage operational sequence and result semantics.
- `reports/verification/sealed-btcusdt-historical-validation-final.md` for the terminal v0.1 rejection evidence and confirmation of no final-test access.

## Candidate Multi-Model Strategy v0.2

Candidate v0.2 is the prospectively governed successor to rejected v0.1. It preserves the complete v0.1 financial hypothesis and changes only the approved trend-specialist numerical convergence contract plus its version identity: Elastic-Net logistic regression with `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, single-thread execution, `tol=1e-7`, and `max_iter=50000`.

Development evidence is fixed to `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` and must produce exactly 12 complete chronological development folds. The strict pre-final classifier is closed to `QUALIFIED`, `REJECTED`, or `INCONCLUSIVE`. `QUALIFIED` permits only creation of a future prospective-final seal; it does not prove future profitability.

The genuine v0.2 final era begins at the first UTC calendar-month boundary strictly after successful frozen-source/pre-final verification and lasts exactly 18 calendar months. The interval from the development cutoff to that future start is quarantined bridge data and may not be used to tune or rescue v0.2.

Research-only v0.2 command surface:

```text
gemini-trading research strategy-v0-2-qualify
gemini-trading research strategy-v0-2-qualification-verify
gemini-trading research strategy-v0-2-seal-prospective-final
```

The manually dispatched `Candidate v0.2 Development Qualification` workflow consumes a fresh exact-source Stage 1 dataset only after an owner-authored Issue #61 approval marker. It performs development qualification and provider-free verification but does not access future-final market rows or authorize execution.

Candidate v0.2 remains `RESEARCH_ONLY`; future profitability and execution readiness are not established. The pre-final implementation can be completed now, but the prospective 18-month market result cannot exist until the sealed future interval has elapsed and is evaluated under a separate governed operation.

See:

- `docs/superpowers/specs/2026-08-10-candidate-multi-model-strategy-v0-2-design.md` for the approved prospective design.
- `docs/superpowers/plans/2026-08-10-candidate-multi-model-strategy-v0-2.md` for the implementation and operational closure plan.
- `docs/operations/candidate-multi-model-strategy-v0-2.md` for exact Stage 1, qualification, verification, and seal operations.
- `docs/operations/candidate-multi-model-strategy-v0-2-step-verification.md` for exact-head, merged-main, Stage 1, qualification, and pre-final closure requirements.

## Candidate Multi-Model Strategy v0.3

Candidate v0.3 is the separately governed calibrated-arbitration successor to terminally rejected v0.2. It preserves the validated specialist, feature, label, regime, simulator, cost, risk, chronology, replay, and evidence contracts while replacing the sparse fixed entry veto stack with calibration-only fold-local selectivity.

The locked development window is `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`. The primary entry-selectivity rule is q75 with a `0.50` effective floor and at least 40 eligible calibration scores; q70 and q80 are preregistered sensitivity neighbors. Companion probability and cross-specialist disagreement are diagnostics rather than entry vetoes. Any post-evidence redesign becomes Candidate v0.4.

Research-only v0.3 command surface:

```text
gemini-trading research strategy-v0-3-qualify
gemini-trading research strategy-v0-3-verify-qualification
gemini-trading research strategy-v0-3-create-prospective-seal
```

The manually dispatched Candidate v0.3 qualification workflow requires an exact merged-main source, a fresh Stage 1 dataset, and an owner-authored Issue #69 approval marker. Qualification and verification do not automatically create a seal. A future-window seal is possible only from independently verified `QUALIFIED` evidence and contains no market rows or performance results.

Candidate v0.3 remains `RESEARCH_ONLY`; no execution or capital authority is introduced.

See:

- `docs/superpowers/specs/2026-08-12-candidate-multi-model-strategy-v0-3-design.md` for the approved design.
- `docs/superpowers/plans/2026-08-12-candidate-multi-model-strategy-v0-3.md` for the implementation plan.
- `docs/operations/candidate-multi-model-strategy-v0-3.md` for the protected Stage 1, qualification, verification, and seal protocol.
- `docs/operations/candidate-multi-model-strategy-v0-3-step-verification.md` for exact-head, merged-main, Stage 1, qualification, and pre-final closure requirements.

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
