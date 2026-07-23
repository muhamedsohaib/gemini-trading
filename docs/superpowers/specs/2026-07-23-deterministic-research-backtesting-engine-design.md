# Deterministic Research and Backtesting Engine Design

## Status

Approved in principle on 2026-07-23. Written specification pending final user review before implementation planning.

This milestone is Program 5 in the reconstruction sequence. It follows the verified Market Data Core and precedes the candidate strategy milestone.

## 1. Purpose

The engine is an impartial, deterministic judge of strategy behavior. It must establish simulation correctness, reproducibility, accounting integrity, realistic execution assumptions, and auditable evidence. It does not establish profitability and must not be tuned to make a preferred strategy appear successful.

The engine must answer:

- what information the strategy had at each decision point;
- what action it proposed;
- whether the order was eligible, rejected, partially filled, or filled;
- what spread, slippage, latency, liquidity, and fees were applied;
- how cash, position, equity, and drawdown changed;
- whether an independent replay reproduces the same result.

## 2. Scope

### 2.1 Included in the first slice

- Binance Spot canonical candle datasets produced by the Market Data Core;
- one instrument per experiment;
- long-only spot trading;
- quote-currency cash accounting;
- buy, hold, and sell-to-close behavior;
- market and limit orders;
- deterministic partial fills;
- configurable time-in-force with bounded order lifetime;
- Decimal-based accounting;
- deterministic experiment manifests and result identities;
- provider-free replay and independent verification;
- a synthetic fixture strategy used only to prove engine correctness.

### 2.2 Excluded

- short selling;
- leverage, margin, futures, options, or funding;
- liquidation modelling;
- multi-asset portfolio construction;
- production strategy logic;
- machine-learning models;
- reinforcement learning;
- private exchange endpoints or credentials;
- paper, demo, or live order submission.

The design must remain extensible without importing these excluded concerns into the first implementation.

## 3. Design principles

1. Failure defaults to an invalid experiment and no trusted result.
2. Completed-candle strategies may not consume incomplete or future candles.
3. Official evidence uses conservative execution assumptions.
4. Same inputs produce byte-equivalent core outputs.
5. All monetary and quantity calculations use Decimal values under explicit precision rules.
6. Every state transition is attributable to one accepted event.
7. No strategy may override accounting, execution, or risk constraints.
8. Failed and unprofitable experiments remain recorded.
9. Research flexibility must not weaken the official evidence standard.
10. The runtime must remain safe without an external AI service.

## 4. Architecture

The approved approach is a repository-native event-driven kernel.

```text
Canonical dataset identity
        ↓
Verified canonical dataset reader
        ↓
Chronological closed-candle event stream
        ↓
Strategy decision interface
        ↓
Order eligibility and validation
        ↓
Deterministic execution simulator
        ↓
Cash, position, and order state transitions
        ↓
Immutable decisions, orders, fills, and ledgers
        ↓
Metrics, result identity, and verification report
```

Suggested package boundaries:

```text
src/gemini_trading/
├── domain/
│   ├── experiment.py
│   ├── order.py
│   ├── fill.py
│   ├── position.py
│   └── account.py
├── research/
│   ├── contracts.py
│   ├── dataset_reader.py
│   ├── engine.py
│   ├── identity.py
│   ├── metrics.py
│   ├── replay.py
│   └── artifacts.py
├── execution/
│   └── simulator/
│       ├── costs.py
│       ├── liquidity.py
│       ├── precision.py
│       └── fills.py
└── cli/
    └── research.py
```

Domain contracts must not import CLI, filesystem, network, Binance-specific HTTP, or strategy implementation code.

## 5. Event ordering and look-ahead prevention

The authoritative event stream contains only completed canonical candles in strict chronological order.

For each candle `T`:

1. Any orders already eligible on `T` are evaluated using only `T` and prior state.
2. Eligible fills are applied in deterministic order.
3. Account, position, and active-order state is updated.
4. The strategy receives candle `T` plus the resulting authoritative portfolio state.
5. The strategy may emit zero or more order intents.
6. Intents are validated and become orders eligible no earlier than the configured timing policy.
7. A complete decision record is persisted.

The official timing policy is next-candle execution. A decision made after candle `T` closes may first fill on candle `T+1`.

A same-close mode may exist only as a clearly labelled diagnostic policy. It may not be used as primary promotion evidence unless a future strategy contract proves that every required input was available before that close. The engine must never silently change timing policy.

The strategy interface must not expose future candles, future returns, mutable iterators capable of forward access, or provider access.

## 6. Orders

### 6.1 Supported order sides

- `BUY`: opens or increases the long spot position.
- `SELL_TO_CLOSE`: reduces or closes an owned position.

A sell quantity greater than the owned position is rejected. Short positions cannot be created.

### 6.2 Supported order types

- `MARKET`
- `LIMIT`

### 6.3 Time in force

The first slice supports:

- `IOC`: fill available eligible quantity during the first eligible candle and cancel the remainder;
- `BAR`: remain active for one eligible candle and cancel any remainder afterward;
- `GTC`: remain active until filled, cancelled, or maximum active-candle lifetime is reached.

Every active order has an explicit maximum lifetime. Stale orders expire deterministically.

### 6.4 Order identity and ordering

Every order receives a deterministic identity derived from experiment identity, decision sequence, and intent sequence. Duplicate event processing must not create duplicate orders.

When more than one order is eligible on the same candle, processing order is deterministic and recorded. The first slice should reject mutually conflicting simultaneous intents unless the strategy contract explicitly supports and tests them.

## 7. Fill semantics

### 7.1 Official market-order policy

A market order uses the next eligible candle open as the reference price, then applies:

- configured directional half-spread;
- configured slippage;
- configured latency policy;
- exchange precision;
- fees.

The simulator must prevent fills at a price that could not exist within the candle under the configured model. If the configured adjustment creates an invalid price, the order fails safely.

### 7.2 Official conservative limit policy

Candle OHLCV data does not reveal exact intrabar path or queue position. Official results therefore use conservative rules:

- a buy limit requires the candle low to move strictly below the limit price;
- a sell limit requires the candle high to move strictly above the limit price;
- merely touching the limit does not guarantee a fill;
- fill quantity remains subject to latency, participation, precision, cash, and position constraints.

An optimistic touch-fill policy may exist for labelled sensitivity analysis only. It cannot become the official result or promotion evidence.

### 7.3 Partial fills

Fill quantity is capped by a deterministic candle-volume participation model. The configuration defines the maximum proportion of candle volume available to the experiment.

The engine must record:

- requested quantity;
- eligible quantity before precision;
- filled quantity;
- remaining quantity;
- reference and final fill price;
- spread, slippage, and fee components;
- the reason for partial fill or no fill.

Repeated replay with identical inputs must generate identical partial fills.

### 7.4 Known limitation

OHLCV-only simulation cannot reconstruct queue position, exact market impact, trade ordering, or intrabar path. The official conservative policy reduces but does not eliminate this uncertainty. Order-book and trade-level simulation remain a later milestone.

## 8. Cost and exchange-constraint model

Every official experiment includes explicit configuration for:

- maker and taker fee rates;
- spread model;
- slippage model;
- latency model;
- price tick size;
- quantity step size;
- minimum quantity;
- minimum notional;
- maximum candle-volume participation.

Precision and minimum-order rules are applied before accepting a fill. The engine records whether rounding changed the quantity or price. An order that becomes invalid after precision or minimum-notional checks is rejected rather than adjusted secretly.

The official configuration may not use zero costs unless the experiment is explicitly labelled as a gross, non-promotable diagnostic.

## 9. Accounting model

The initial account contains quote-currency cash and at most one long base-asset position.

Core state includes:

- available cash;
- reserved cash for eligible buy orders where applicable;
- position quantity;
- average entry cost;
- realized profit and loss;
- cumulative fees and simulated execution costs;
- active orders;
- marked equity;
- peak equity and drawdown.

Required invariants include:

- cash cannot become negative;
- reserved cash cannot exceed cash;
- position quantity cannot become negative;
- sell-to-close cannot exceed owned quantity;
- every fill belongs to exactly one accepted order;
- every position change is explained by fills;
- every cash change is explained by fills, fees, or explicit initialization;
- fees are charged exactly once;
- equity equals cash plus marked position value;
- duplicate events do not duplicate decisions, orders, or fills;
- terminal ledgers reconcile to terminal account state.

Any invariant violation stops the experiment, records the failure, and prevents creation of a trusted completion result.

## 10. Experiment identity and deterministic serialization

Every experiment manifest records at least:

- manifest schema version;
- canonical dataset ID and canonical file hash;
- exact code commit identity;
- engine version;
- strategy fixture or strategy version identity;
- complete strategy configuration;
- initial capital;
- timing policy;
- fill policy;
- order policy and time-in-force defaults;
- fee, spread, slippage, latency, liquidity, and precision assumptions;
- random seed;
- output schema versions.

The experiment identity is a SHA-256 content identity over deterministic canonical manifest bytes. Wall-clock timestamps, output paths, hostnames, and run-specific logging values do not contaminate the identity.

Core artifacts use compact UTF-8 deterministic JSON or JSONL with stable key ordering, stable Decimal formatting, UTC timestamps, and a single terminal newline.

Two successful executions with the same experiment identity must produce byte-equivalent core artifacts and the same result identity.

## 11. Artifacts

A successful experiment produces immutable artifacts for:

- experiment manifest;
- strategy decisions;
- orders and rejections;
- fills and partial fills;
- cash ledger;
- position ledger;
- equity and exposure series;
- completed trades;
- metrics;
- result manifest;
- verification report.

A failed experiment produces:

- experiment manifest;
- all valid evidence created before failure;
- terminal failure record;
- no trusted completed-result manifest.

Metrics must include at minimum:

- starting and ending equity;
- gross and net return;
- realized and unrealized profit and loss;
- total fees and simulated costs;
- maximum drawdown;
- exposure time;
- order, rejection, fill, partial-fill, and trade counts;
- win rate only where complete round trips exist.

The first milestone does not claim that any metric demonstrates market edge.

## 12. Replay and independent verification

The command surface will include conceptually:

```text
gemini-trading research backtest
gemini-trading research replay
gemini-trading research verify
```

Backtest consumes a verified canonical dataset and an explicit experiment configuration.

Replay performs no network access. It loads the immutable experiment manifest and dataset, reruns the engine, and compares deterministic artifacts.

Verification independently recomputes:

- dataset linkage and hashes;
- experiment identity;
- decision, order, fill, and ledger hashes;
- accounting invariants;
- result identity;
- replay equivalence;
- terminal success or failure state.

Missing, altered, duplicated, inconsistent, or non-deterministic evidence fails closed.

## 13. Error handling and safe state

Errors use typed, safe failure categories such as:

- invalid experiment configuration;
- dataset verification failure;
- chronological or completion violation;
- strategy contract violation;
- invalid order transition;
- insufficient cash;
- invalid sell quantity;
- precision or minimum-notional rejection;
- accounting invariant violation;
- artifact conflict;
- replay mismatch;
- non-deterministic result.

Expected order rejections are recorded as domain outcomes and do not necessarily invalidate the experiment. Integrity, accounting, chronology, or determinism failures invalidate it.

CLI output must not emit secrets, environment dumps, raw unrestricted payloads, absolute operator paths, or unhandled tracebacks.

## 14. Testing and verification

The implementation plan must use test-driven development and include:

- unit tests for domain contracts, order transitions, fills, costs, precision, and accounting;
- property tests for non-negative cash and position, conservation, reconciliation, and deterministic identity;
- regression tests for known prototype failures;
- integration tests using canonical datasets;
- acceptance tests for full backtest, replay, and verify workflows;
- tests for incomplete, duplicated, reversed, and corrupted data;
- next-candle look-ahead prevention tests;
- conservative and optimistic limit-policy separation tests;
- partial-fill and order-expiry tests;
- insufficient-cash and invalid-sell tests;
- exact Decimal and minimum-notional tests;
- duplicate-cycle idempotency tests;
- deterministic rerun and byte-equivalence tests;
- clean failure-artifact tests.

The synthetic fixture strategy must be intentionally simple and clearly marked as non-production. It exists only to exercise buy, hold, sell, market, limit, rejection, and partial-fill paths.

Every task must record focused evidence. Each checkpoint must run the complete deterministic suite, formatting, linting, strict typing, build, dependency audit, tracked-file policy, secret scan, and repository-diff review.

Final acceptance requires fresh verification on the exact pull-request head and again on the exact merged `main` commit.

## 15. AI advisory governance layer

The user requires the assistant to remain part of the final decision layer. This is implemented as a governance requirement, not as direct autonomous trading authority.

The assistant is a required independent advisory reviewer for:

- strategy milestone approval;
- selection of official versus exploratory evidence;
- changes to validation or promotion criteria;
- risk-limit increases;
- exchange-credential introduction;
- transition from research to shadow, paper, demo, or live stages;
- allocation of material real capital;
- acceptance of unresolved limitations.

For each such decision, the assistant may recommend approval, rejection, reduction, additional evidence, or continued testing. The recommendation and supporting evidence must be recorded.

The assistant may not:

- submit or authorize individual exchange orders autonomously;
- override an independent risk-governor rejection;
- raise exposure or loss limits by itself;
- hide failed or unfavorable evidence;
- become the only safety mechanism;
- make the engine dependent on continuous external AI availability.

Final authorization for real-money credentials, live-capable execution, and capital deployment remains an explicit human decision by the user. If the assistant is unavailable or evidence is incomplete, the system fails closed and does not promote or increase risk.

Routine research architecture and conservative modelling defaults may be selected by the assistant without repeated terminology-level user decisions, provided they remain within this approved specification and introduce no real-money authority.

## 16. Milestone completion gate

The milestone is complete only when:

1. official results use next-candle timing and conservative fill assumptions;
2. diagnostic assumptions are clearly separated and non-promotable;
3. completed-candle strategies cannot access future or incomplete data;
4. accounting invariants pass across deterministic, property, and fault tests;
5. identical experiments reproduce byte-equivalent core artifacts;
6. invalid data and impossible transitions fail closed;
7. no credentials, private endpoints, or exchange submission exist;
8. documentation, tests, formatting, strict typing, security scans, dependency audit, and package build pass;
9. exact-head verification evidence is recorded;
10. the merged protected-main commit is independently verified before Issue #12 is closed.

## 17. Next milestone

After this milestone is verified, the project will design and implement Candidate Multi-Model Strategy v0.1:

- Chronos probabilistic short-horizon forecasts;
- Kronos projected range, volatility, and extreme-move probabilities;
- calibrated XGBoost regime probabilities using out-of-fold upstream predictions;
- deterministic tactical playbooks;
- independent risk governance;
- deterministic initial position sizing;
- mandatory ablation against simpler baselines;
- reinforcement-learning allocation deferred until sufficient genuine paper evidence exists.
