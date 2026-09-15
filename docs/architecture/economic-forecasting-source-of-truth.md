# Gemini Trading Economic Forecasting Source of Truth

Status: CANONICAL PROGRAM DIRECTION
Date locked: 2026-09-15
Boundary: RESEARCH_ONLY

## Purpose

Gemini Trading is no longer governed by the objective "build a better BTC trading strategy." The program objective is to become a point-in-time, multimodal economic forecasting and decision-intelligence system.

Trading remains an important downstream consumer and economic-value test, but it is not the definition of intelligence and it is not the parent architecture.

This document is the program-level source of truth. Candidate-specific specifications remain authoritative for the exact experiments they govern. In particular, Candidate v0.4 must be completed according to its frozen design and may not be retrofitted to this broader architecture after observing results.

## Current Scientific State

The research laboratory is materially more mature than the predictive hypothesis.

The repository already contains deterministic market-data ingestion and replay, verified exchange closure and segment handling, sealed dataset identities, point-in-time feature construction, next-candle simulation, explicit modeled costs, deterministic model training, walk-forward evaluation, immutable qualification evidence, provider-free replay, and independent verification.

That infrastructure is retained and extended.

The candidate history is evidence, not embarrassment:

- Candidate v0.1: terminal REJECTED.
- Candidate v0.2: terminal REJECTED.
- Candidate v0.3: terminal REJECTED after a valid substantive qualification; integrity, determinism, calibration, replay, and verification succeeded while the economic hypothesis failed.
- Candidate v0.4: the final currently authorized BTC-only candidate line. It tests a preregistered hierarchical 1h/4h hypothesis and must be completed once without rescue tuning.

A failed hypothesis with a trustworthy laboratory is useful scientific progress. The program will not respond to failure by repeatedly loosening thresholds or adding arbitrary BTC-specific complexity.

## Program Doctrine

### 1. Forecast first, decide second

The forecasting system estimates future economic and market distributions. Decision engines consume those forecasts later.

A trading policy is therefore a consumer of forecasts, not the forecasting model itself.

### 2. Point-in-time truth before model sophistication

Every observation must carry enough provenance to answer:

- what was observed;
- when the underlying event occurred;
- when the value became available to an observer;
- which release or vintage supplied it;
- whether it was revised later;
- which source produced it;
- whether the stored representation can be independently replayed.

For macroeconomic data, historical revisions must never leak into an earlier forecast origin. "Latest downloaded historical series" is not acceptable evidence when the original vintage can differ.

### 3. Probabilistic forecasts, not single-number prophecies

The primary output is a predictive distribution or calibrated probability, not a point estimate alone.

Examples include:

- return quantiles;
- volatility distributions;
- regime transition probabilities;
- probability an economic release beats consensus;
- growth, inflation, liquidity, stress, and policy-state distributions.

### 4. Forecast skill is evaluated before monetization

A model can contain information even when a particular trading policy fails to monetize it. Forecast evaluation and decision evaluation are therefore separate layers.

Primary forecasting metrics may include, as appropriate:

- calibration error;
- Brier score;
- log loss;
- CRPS;
- quantile/pinball loss;
- interval coverage and sharpness;
- directional accuracy and balanced accuracy;
- regime-transition accuracy;
- forecast improvement versus naive and classical baselines.

Trading metrics remain secondary decision-layer evidence:

- net return;
- Sharpe-like risk-adjusted measures;
- drawdown;
- turnover;
- cost robustness;
- tail exposure;
- concentration.

### 5. Model tournament, not model allegiance

No architecture is presumed to be the winner.

The system must support governed challengers from multiple families:

- naive and random-walk baselines;
- autoregressive and state-space models;
- VAR/Bayesian VAR and dynamic-factor approaches where appropriate;
- regularized linear models;
- gradient-boosted/tree ensembles;
- deterministic neural temporal models;
- time-series foundation models;
- multimodal/event-conditioned models;
- ensemble and mixture-of-experts meta-forecasters.

Foundation models are challengers. They do not replace baselines or governance.

### 6. Information breadth before parameter breadth

The next major gains should come from richer, correctly timestamped evidence rather than larger BTC-specific hyperparameter searches.

The system expands across three evidence families:

1. Market state
2. Economic/macro state
3. Event/text/alternative information

### 7. Economic state is a first-class latent representation

The long-term forecasting core maintains a timestamped Economic State Vector with probabilistic components such as:

- growth;
- inflation;
- liquidity;
- financial stress;
- USD pressure;
- risk appetite;
- credit impulse;
- commodity shock;
- policy stance;
- crypto liquidity.

The exact vector is versioned. New dimensions require a new state-schema version and prospective evaluation.

Assets and economic variables are forecast conditionally on the state rather than treated as unrelated isolated targets.

### 8. Scientific discovery is automated; outcome rescue is not

The project should automate the research loop:

Evidence -> hypothesis -> preregistration -> implementation -> sealed experiment -> adversarial controls -> independent replay -> leaderboard -> accept/reject/archive.

AI systems may propose hypotheses, write experiment scaffolding, detect anomalies, summarize evidence, and generate adversarial tests.

They may not alter a frozen experiment after observing outcome data. A post-result financial redesign is a new candidate or new hypothesis identity.

## Target Architecture

```text
                     ECONOMIC REALITY
                            |
          +-----------------+------------------+
          |                 |                  |
       Markets            Macro             Events
          |                 |                  |
          +-----------------+------------------+
                            |
                            v
                 POINT-IN-TIME DATA FABRIC
                            |
                            v
                   ECONOMIC STATE ENGINE
               +------------+-------------+
               |            |             |
            Regimes      Nowcasts       Event state
               |            |             |
               +------------+-------------+
                            |
                            v
                    FORECAST TOURNAMENT
       classical + ML + temporal + foundation + fusion
                            |
                            v
                  PROBABILISTIC FORECAST BUS
          horizons: intraday / daily / weekly / monthly+
                            |
                            v
                     DECISION ENGINES
          trading / risk / scenarios / alerts / allocation
```

The existing deterministic trading engine is retained primarily in the Decision Engines and scientific-verification layers.

## Point-in-Time Economic Data Fabric

The data fabric is the first new subsystem and the highest priority after the canonical direction is locked.

### Core requirements

Every observation must have a deterministic identity and explicit chronology fields. At minimum the normalized contract distinguishes:

- `series_id`;
- `observation_time`;
- `available_time`;
- `vintage_time` where applicable;
- `retrieved_time`;
- `source_id`;
- `value` plus typed unit/scale metadata;
- raw-evidence digest;
- canonical-row digest.

A consumer requesting information as of time `T` must be unable to observe a row whose `available_time > T`.

### Initial evidence domains

The architecture must be capable of representing these domains without coupling the canonical schema to one vendor:

Market:

- crypto spot and derivatives state;
- major equity indices and breadth;
- FX and broad USD state;
- sovereign yields and curve structure;
- volatility indices;
- credit-spread proxies;
- commodities and precious metals.

Macro:

- inflation;
- labor;
- growth/output;
- consumption/retail;
- surveys/PMIs;
- housing;
- monetary/liquidity variables;
- central-bank balance sheets and policy rates;
- inflation expectations.

Events and alternative information are added only after the numeric point-in-time contract is proven.

## Forecast Bus Contract

Forecasts are immutable versioned artifacts, not ephemeral model outputs.

A forecast artifact binds:

- forecast origin;
- target identifier;
- horizon;
- training/data cutoff identity;
- feature/state identity;
- model artifact identity;
- distribution or calibrated probability output;
- uncertainty metadata;
- run/source commit identity;
- evaluation eligibility status.

Forecasts must never be silently overwritten. Revised forecasts are new artifacts with explicit lineage.

## Benchmark Arena

Every forecasting target must have a baseline suite appropriate to its statistical structure. A sophisticated model that cannot reliably outperform naive or classical baselines is not promoted merely because it is more complex.

The arena separates:

- development leaderboard;
- sealed validation leaderboard;
- prospective leaderboard.

Development results may guide a new hypothesis. They may not rewrite a frozen hypothesis under the same identity.

## Meta-Forecasting

Ensembling is permitted only after component forecasters have independently reproducible evidence.

The future meta-forecaster may condition model weights on regime/state, horizon, target, and recent calibration quality, but the weighting rule itself is a governed model requiring its own walk-forward and prospective evaluation.

## Decision Layer

Decision engines consume forecast artifacts through explicit interfaces.

The initial trading consumer may ask questions such as:

- probability return exceeds modeled costs;
- probability drawdown exceeds a risk threshold;
- expected return distribution conditional on the current state;
- probability of regime transition during the intended holding period.

No decision engine may mutate upstream forecast evidence.

## Candidate v0.4 Closure Rule

Candidate v0.4 continues in parallel with Economic Forecasting v1.

It must:

1. finish the already preregistered implementation;
2. pass exact-head CI and protected merge;
3. create a fresh exact-source Stage 1 artifact;
4. receive exact dataset approval;
5. run development qualification once;
6. independently verify the qualification artifact;
7. terminate as QUALIFIED, REJECTED, or INCONCLUSIVE according to its frozen contract.

If REJECTED, there is no rescue tuning. A BTC Candidate v0.5 is not the default next step. A new BTC-specific candidate requires a distinct information hypothesis that is justified by the broader forecasting program rather than by threshold or parameter rescue.

## Program Phases

### Phase I - Close the BTC-only generation

Complete Candidate v0.4 Tasks 7-14 and execute its governed evidence sequence once.

### Phase II - Economic Data Fabric v1

Build deterministic point-in-time observation contracts, vintage-aware storage, as-of querying, sealed dataset identities, replay, and independent verification.

### Phase III - Forecast Benchmark Arena v1

Introduce target/horizon contracts, naive/classical baselines, common probabilistic metrics, immutable forecast artifacts, and challenger adapters.

### Phase IV - Economic State Engine v1

Create versioned latent state estimates and regime-transition probabilities from cross-asset and macro evidence.

### Phase V - Information/Event Engine v1

Add economic-calendar surprises, central-bank text, news/event extraction, and other timestamp-safe evidence under independent provenance contracts.

### Phase VI - Meta-Forecaster v1

Build governed regime-aware ensemble weighting and calibration across validated component forecasters.

### Phase VII - Economic Decision Layer v1

Connect forecasts to trading, risk, scenario simulation, alerts, and later portfolio decisions without weakening capital-authority boundaries.

## Parallelism Rule

Candidate v0.4 closure and Economic Data Fabric v1 may proceed in parallel because they do not share a financial hypothesis.

The Data Fabric must not read or optimize against v0.4 development P&L. v0.4 must not adopt new macro, cross-asset, or event features after its specification freeze.

## Governance

The repository remains `RESEARCH_ONLY` unless a separate explicit governance change is approved.

No document in the economic-forecasting program authorizes:

- live exchange order submission;
- autonomous capital deployment;
- leverage or derivatives exposure;
- production credentials;
- removal or weakening of risk controls.

A future path to paper or real capital requires independent evidence and a separate authorization gate.

## Success Criteria for the Program

The project becomes an actual economic forecasting system when all of the following are true:

1. Multiple heterogeneous economic/market data families are stored point-in-time with vintage-safe replay.
2. Forecast artifacts exist for multiple targets and horizons independent of trading decisions.
3. Forecast accuracy/calibration is evaluated against naive and classical baselines.
4. At least one nontrivial model or ensemble demonstrates reproducible out-of-sample forecast improvement on a sealed evaluation.
5. An Economic State Vector is produced without look-ahead leakage and has independently reproducible lineage.
6. Decision engines consume forecasts through stable interfaces rather than embedding forecasting logic internally.
7. Prospective performance can be evaluated without changing the frozen forecasting specification.

Profitability is not assumed by satisfying these criteria. It must be demonstrated separately.

## Immediate Execution Order

1. Merge this source-of-truth direction into `main`.
2. Record the direction and current v0.4 implementation state in the relevant GitHub issues.
3. Finish Candidate v0.4 without financial redesign.
4. Begin Economic Data Fabric v1 with observation chronology and vintage identity before adding providers.
5. Add the Forecast Benchmark Arena only after the data contract is independently replayable.

This order is canonical until replaced by an explicitly approved successor architecture document.
