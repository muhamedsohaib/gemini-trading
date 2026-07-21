# Gemini Trading Hybrid Open-Core Reconstruction Design

## Status

Approved direction: controlled reconstruction in the existing repository using a hybrid open-core operating model.

This specification governs the reconstruction of the current prototype into an auditable research, risk, paper-execution, and eventual controlled-live trading platform. It does not claim or guarantee profitability. Market edge must be established through reproducible evidence and hostile validation.

## 1. Purpose

The project will become a benchmark-quality trading research platform with clear separation between:

- public open-core infrastructure;
- private strategy intellectual property;
- private production execution and credentials;
- immutable evidence supporting every performance claim.

The current repository remains the historical baseline. Existing prototype code is not treated as production architecture and will be replaced subsystem by subsystem after tests capture its known defects.

## 2. Product Boundary

### Public open core

The public repository may include:

- domain models and interfaces;
- canonical market-data contracts;
- provider adapter interfaces and public-data adapters;
- data validation and quality checks;
- feature-pipeline interfaces;
- deterministic baseline strategies;
- event-driven backtesting infrastructure;
- paper broker and execution simulator;
- portfolio accounting primitives;
- independent risk-governor framework;
- experiment manifests and reproducibility tooling;
- testing, CI, documentation, and security controls;
- synthetic or redistributable example datasets;
- benchmark reports that do not expose private parameters.

### Private extensions

Private repositories or private deployment packages will contain:

- proprietary strategy parameters and ensembles;
- trained model artifacts not approved for public release;
- production exchange adapters where disclosure creates operational risk;
- production infrastructure configuration;
- exchange and database credentials;
- investor-only evidence and commercial analysis;
- private monitoring endpoints and incident details.

### Explicit exclusions

The public core will not contain unrestricted production credentials, direct autonomous LLM order authority, unpublished private datasets, or claims of institutional readiness unsupported by evidence.

## 3. Non-Negotiable Constraints

1. All execution remains paper-only until explicit promotion gates are satisfied.
2. Failure defaults to no trade.
3. Risk governance is independent of strategy and model code.
4. The same strategy interface is used in research, backtest, shadow, paper, demo, and live modes.
5. Completed-candle strategies may never consume incomplete candles.
6. Every decision is reproducible from immutable data, code version, configuration, model version, and random seed.
7. No production exploration or random allocation is permitted.
8. No model or strategy is promoted without out-of-sample and forward evidence after realistic costs.
9. Every advanced component must prove incremental value over simpler baselines through ablation testing.
10. LLMs may assist research and operations but may not submit orders, override risk rejections, raise limits, or deploy models autonomously.
11. Secrets must never be committed. Any exposed secret is rotated before repository cleanup.
12. Production-capable changes require review, automated validation, and rollback instructions.

## 4. Target Architecture

```text
Market-data providers
        ↓
Raw immutable market-data store
        ↓
Canonical validation and normalization
        ↓
Feature pipeline and feature registry
        ↓
Regime models and independent strategy models
        ↓
Signal normalization and optional ensemble layer
        ↓
Portfolio construction
        ↓
Independent pre-trade risk governor
        ↓
Execution simulator or exchange adapter
        ↓
Order and position state machines
        ↓
Immutable decision and execution ledger
        ↓
Performance, drift, security, and risk monitoring
```

Each component communicates through versioned domain contracts. Replacing an exchange, model, database, or strategy must not require rewriting unrelated components.

## 5. Repository Structure

```text
gemini-trading/
├── src/gemini_trading/
│   ├── domain/
│   ├── data/
│   │   ├── providers/
│   │   ├── validation/
│   │   └── storage/
│   ├── features/
│   ├── models/
│   │   ├── regimes/
│   │   ├── forecasts/
│   │   └── registry/
│   ├── strategies/
│   ├── portfolio/
│   ├── risk/
│   ├── execution/
│   │   ├── simulator/
│   │   └── adapters/
│   ├── ledger/
│   ├── monitoring/
│   ├── research/
│   └── cli/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── property/
│   ├── regression/
│   └── acceptance/
├── configs/
│   ├── research/
│   ├── paper/
│   ├── demo/
│   └── live/
├── migrations/
├── reports/
├── docs/
│   ├── architecture/
│   ├── research/
│   ├── risk/
│   ├── operations/
│   ├── investor/
│   └── superpowers/
├── pyproject.toml
├── uv.lock
├── Dockerfile
└── README.md
```

## 6. Domain Contracts

The initial domain layer will define immutable or tightly validated representations for:

- `Instrument`;
- `Timeframe`;
- `Candle`;
- `DatasetVersion`;
- `FeatureVector`;
- `RegimePrediction`;
- `Signal`;
- `TradeIntent`;
- `RiskDecision`;
- `Order`;
- `Fill`;
- `Position`;
- `PortfolioSnapshot`;
- `StrategyVersion`;
- `ModelVersion`;
- `ExperimentRun`.

Regimes use enums rather than string parsing. All timestamps are timezone-aware UTC. Every closed-candle decision records the candle identity and completion state. Monetary and quantity calculations use representations appropriate for exchange precision and deterministic accounting.

## 7. Data Flow

1. A provider retrieves raw exchange payloads.
2. The raw payload is persisted unchanged with retrieval metadata.
3. A validator rejects malformed, stale, duplicated, out-of-order, impossible, or incomplete records.
4. A normalizer produces canonical candles.
5. A dataset builder assigns an immutable dataset version and content hash.
6. Feature computation runs only against a specified dataset version.
7. Strategies consume validated features and portfolio state.
8. Signals are normalized into trade intents.
9. The independent risk governor approves, modifies, or rejects each intent.
10. An execution implementation simulates or submits approved orders.
11. Order, fill, position, decision, and risk records are persisted to an immutable audit ledger.
12. Monitoring evaluates data quality, execution integrity, P&L, exposure, drift, and operational health.

A single decision cycle must use one canonical market snapshot. Independently fetched prices and indicators may not be mixed.

## 8. Research and Validation Design

The research engine will be event-driven and share production strategy interfaces. It must model:

- maker and taker fees;
- spread;
- configurable slippage;
- latency;
- exchange tick, quantity, and notional limits;
- partial fills and rejected orders;
- funding where applicable;
- position and cash accounting;
- portfolio exposure;
- stop and target behavior.

Validation includes:

- chronological train, validation, and frozen test periods;
- walk-forward evaluation;
- purged splits where labels overlap future horizons;
- parameter perturbation;
- higher-cost and delayed-entry stress tests;
- regime-specific attribution;
- Monte Carlo trade-sequence analysis;
- removal of best trades and best periods;
- ablation tests for every complex layer;
- comparison with cash, buy-and-hold, simple EMA, simple Bollinger, deterministic regime switching, and Version 0.

Failed experiments remain recorded. Test-set results may not be repeatedly optimized against.

## 9. Strategy and Model Design

### Deterministic baseline

The first reconstructed strategy is rule-based and intentionally simple. It must preserve complete regime identities, validate entry-stop-target geometry, distinguish sell-to-close from short selling, prevent repeated entries, require valid position state, reject stale data, and include costs.

### Regime modeling

Machine-learning regime classification is a separate optional component. Training and inference are separate processes. Models require multi-period historical data, correct target handling, time-aware validation, probability calibration, stored artifacts, feature/version metadata, class-distribution reports, and drift monitoring.

### Reinforcement learning

The existing randomized allocation component is not considered functioning reinforcement learning. RL remains excluded from the execution path until a valid environment, state transition, reward function, constrained action space, offline training procedure, and out-of-policy evaluation are implemented. Production exploration is prohibited.

### Chronos and Kronos

Chronos and Kronos are experimental plugins, not mandatory layers. Each requires a written hypothesis, input/output contract, model card, benchmark, ablation evidence, and defined failure behavior before promotion.

## 10. Risk Architecture

The risk governor is a separate service or package that does not depend on strategy internals. It consumes trade intents and authoritative portfolio state.

Required controls include:

- account-equity verification;
- stop-distance-based position sizing;
- maximum order and position notional;
- maximum asset, strategy, and portfolio exposure;
- correlation and concentration limits;
- daily loss and drawdown limits;
- consecutive-loss controls;
- stale-data and price-deviation rejection;
- duplicate-order prevention;
- trading-session rules;
- reserved cash requirements;
- emergency kill switch;
- automatic demotion on integrity or risk failure.

Risk decisions are immutable and include machine-readable reason codes. Strategies cannot override a rejection.

## 11. Execution Architecture

The execution subsystem uses an explicit state machine:

```text
PROPOSED
→ RISK_APPROVED
→ SUBMITTED
→ ACKNOWLEDGED
→ PARTIALLY_FILLED
→ FILLED
→ EXIT_PENDING
→ CLOSED
```

Terminal and exceptional states include `REJECTED`, `CANCELLED`, `EXPIRED`, and `RECONCILIATION_REQUIRED`.

The paper broker is implemented before any demo adapter. Required properties include idempotent submission, unique client-order identifiers, partial-fill accounting, retry policies that cannot duplicate orders, stop and target management, restart recovery, and position reconciliation.

## 12. Security Design

Immediate security work precedes all engineering work:

- rotate exposed Supabase credentials;
- inspect database access logs;
- remove secrets from current files and Git history;
- add secret scanning and pre-commit protection;
- use least-privilege credentials per environment;
- separate public, private, demo, and production configurations;
- prohibit service-role credentials in local application code;
- document incident response and credential rotation;
- scan dependencies and containers;
- protect the default branch and require pull requests.

## 13. Testing Strategy

Testing layers include:

- unit tests for pure domain, indicator, strategy, accounting, and risk logic;
- regression tests reproducing every known Version 0 defect;
- property tests for invariants such as no negative cash, invalid OHLC rejection, and exposure limits;
- integration tests for provider, storage, ledger, and broker boundaries;
- acceptance tests for complete decision cycles;
- deterministic replay tests from immutable datasets;
- fault-injection tests for outages, duplicates, restarts, stale data, partial fills, and corrupted artifacts.

The first regression suite must prove that:

- `Trending Down` cannot route into uptrend logic;
- incomplete candles cannot reach closed-candle strategies;
- trailing rows without future outcomes cannot receive false labels;
- duplicate decision cycles cannot create duplicate orders;
- production execution cannot choose random allocation;
- sell-to-close requires an eligible position;
- invalid stop-entry-target geometry is rejected.

## 14. CI and Governance

Every pull request must pass formatting, linting, strict type checking, unit tests, integration tests, regression tests, secret scanning, dependency scanning, and package-build validation.

The `main` branch is protected. Production-capable changes require review and rollback documentation. Architecture decisions are recorded in ADRs. Versioned releases use semantic versioning. Public claims reference immutable reports generated by a specific commit and dataset version.

## 15. Promotion Ladder

```text
RESEARCH_ONLY
    ↓
HISTORICALLY_VALIDATED
    ↓
SHADOW_MODE
    ↓
PAPER_FORWARD
    ↓
DEMO_EXCHANGE
    ↓
LIMITED_LIVE
    ↓
CONTROLLED_SCALE
```

Promotion requires passing CI and security gates, a reproducible validation report, independent risk approval, sufficient forward evidence, no unresolved critical defects, a rollback plan, and explicit human authorization. Systems may be automatically demoted because of drift, drawdown, data-quality failure, execution anomalies, or reconciliation failure.

## 16. OpenAI Integration Boundary

OpenAI capabilities may support repository analysis, coding, test generation, research hypothesis generation, experiment summaries, anomaly investigation, audit-ledger querying, documentation, and investor reporting.

OpenAI models may not directly submit orders, override risk decisions, increase limits, deploy unvalidated models, change production configuration, or suppress unfavorable evidence. All AI-generated modifications follow the same review and CI process as human changes.

## 17. Investor Evidence

Investor-facing materials are generated from the immutable evidence layer and include:

- architecture and security documentation;
- data lineage;
- strategy and model specifications;
- validation methodology;
- gross-to-net reconciliation;
- drawdown and tail-risk reports;
- performance and regime attribution;
- capacity and liquidity analysis;
- change-management history;
- external review findings;
- material weaknesses and known limitations.

Screenshots or manually selected winning periods are not accepted as primary evidence.

## 18. Reconstruction Sequence

The project is decomposed into independently reviewable programs:

1. Security containment and repository freeze.
2. Engineering foundation and CI.
3. Domain contracts and immutable decision identities.
4. Canonical market-data pipeline.
5. Deterministic research and backtesting engine.
6. Reconstructed rule-based baseline.
7. Independent risk governor.
8. Paper broker and execution state machine.
9. Immutable ledger and monitoring.
10. Machine-learning regime research.
11. Optional advanced-model and RL research.
12. Shadow, paper-forward, demo, and controlled-live promotion.
13. Investor evidence and governance package.

Each program receives its own implementation plan. Security containment is first.

## 19. Acceptance Criteria

The reconstruction design is satisfied when:

- no valid secret exists in repository content or history;
- every merge is automatically validated;
- experiments are exactly reproducible;
- strategies use the same contracts across research and execution;
- all execution-capable actions pass the independent risk governor;
- every position is traceable to its data, signal, risk decision, order, and fills;
- advanced layers demonstrate measurable out-of-sample value over simpler baselines;
- the system explains why it traded, refused to trade, or entered a safe state;
- investor reports are generated from immutable evidence;
- no real-capital promotion occurs without explicit human approval.

## 20. First Implementation Plan

The first implementation plan will cover only security containment and repository governance. It will not alter strategy behavior beyond enforcing paper-only operation and preventing further secret exposure.
