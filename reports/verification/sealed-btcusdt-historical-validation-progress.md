# Sealed BTCUSDT Historical Validation Progress

## Safety status

- Promotion level: `RESEARCH_ONLY`
- Exchange order submission: disabled
- Credentials and private endpoints: not used
- Real Stage 1 dataset workflow: not yet run
- Real sealed Stage 2 study: not yet run
- Profitability and capital readiness: not established

## Approved scope

- Public Binance Spot `BTCUSDT`
- Completed `4h` candles
- Fixed window: `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`
- Candidate identity: `candidate.multi_model.v0_1`
- Final untouched test: last 18 calendar months, single access

## Implementation checkpoints

- Design gate: Issue #22
- Draft implementation PR: #23
- Dataset artifact inventory and strict handoff contract: implemented
- Canonical artifact-relative path enforcement, including rejection of normalized aliases such as `./a`: implemented and unit-verified
- Durable final-test access receipt and exact-resume decision: implemented
- Immutable development-only pre-final evidence: implemented
- Operational evaluator phase separation and integration coverage: implemented
- Development feature, label, baseline, and simulator evidence restricted before the final-test boundary: implemented and focused-regression verified
- Study replay strategies bind deterministic evaluation end boundaries: implemented
- Windowed buy-and-hold and already-long baseline state reconstruction: implemented
- Resume receipt-to-study identity binding: implemented
- Fixed-scope historical-validation CLI: implemented
- Manual Stage 1 and Stage 2 workflows with artifact barriers: implemented
- Stage 1 dataset production restricted to the protected `main` branch: implemented
- Owner-authenticated dataset approval and bot-authenticated cross-run final seal: implemented
- Stable run-independent local final-access seal: implemented
- Extended provider-free replay and sealed evidence-chain verification: implemented
- Synthetic end-to-end acceptance and operator documentation: implemented
- Temporary implementation and diagnostic workflows: removed
- Cumulative scope and safety review: complete with no strategy-policy, threshold, feature-definition, label, model, or promotion-gate changes
- Exact-head cumulative CI: pending a successful GitHub runner allocation

Generated raw data, canonical datasets, repository-seal receipts, stable local seals, final-access receipts, pre-final evidence, and full strategy studies remain excluded from tracked repository files.
