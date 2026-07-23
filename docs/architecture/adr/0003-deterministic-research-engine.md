# ADR 0003: Deterministic Research Engine

- Status: Accepted
- Date: 2026-07-23
- Promotion level: `RESEARCH_ONLY`

## Context

The repository needs an impartial backtesting kernel that can judge strategy behavior without importing exchange connectivity, credentials, production strategy logic, or real-capital authority. Market data is accepted only through the verified canonical dataset boundary established by the Market Data Core.

## Decision

Use a repository-native, event-driven, single-instrument, long-only spot simulation kernel with these rules:

1. Official evidence uses completed candles and next-candle execution timing.
2. Official limit fills use conservative strict-cross assumptions.
3. Fees, spread, slippage, latency, precision, minimum quantity, minimum notional, and deterministic partial fills are explicit inputs.
4. Monetary and quantity accounting uses `Decimal` and fails closed on invalid state transitions or reconciliation errors.
5. Experiment and result identities are content-addressed from canonical inputs and artifacts.
6. Research artifacts are immutable. Provider-free replay reconstructs the experiment from local evidence and requires byte-equivalent core artifacts.
7. Independent verification checks dataset integrity, artifact hashes, experiment identity, result identity, and replay equivalence.
8. Diagnostic timing or optimistic fill policies are always non-promotable.
9. CLI output is compact safe JSON. Classified failures return exit code 2 without traceback, secret, raw provider body, or absolute-path leakage.
10. No credential loading, private endpoint, broker adapter, or exchange order submission exists in this milestone.

## Governance

The assistant may review evidence, classification, limitations, promotion readiness, and proposed risk changes as an independent adviser. Human authorization remains mandatory for any future real-capital decision. This ADR does not authorize paper brokerage, demo trading, live trading, capital allocation, or production strategy promotion.

## Consequences

### Positive

- Identical verified inputs reproduce identical experiment IDs, result IDs, and core artifact bytes.
- Failed, unprofitable, and diagnostic experiments remain auditable rather than being hidden.
- Replay and verification do not depend on an exchange provider or network access.
- Strategy code cannot control accounting, execution assumptions, or promotion classification.

### Limitations

- Candle OHLCV cannot prove intrabar path, queue position, exact spread evolution, hidden liquidity, adverse selection, or market impact.
- Partial fills use deterministic candle-volume participation rather than an exchange order book.
- The first slice is single-instrument and long-only; it excludes shorting, leverage, margin, futures, funding, liquidation, options, and portfolio construction.
- The included scripted fixture strategy is synthetic and non-production.
- Profitability, strategy edge, paper-trading readiness, and real-capital readiness are not established.

## Rejected alternatives

- Reusing the legacy prototype: rejected because its behavior was not an acceptable trust boundary.
- Network-dependent replay: rejected because historical evidence must remain independently reproducible.
- Floating-point accounting: rejected because deterministic monetary reconciliation requires explicit decimal semantics.
- Same-close or optimistic fills as official evidence: rejected due to look-ahead and overstatement risk; they remain diagnostic and non-promotable only.
