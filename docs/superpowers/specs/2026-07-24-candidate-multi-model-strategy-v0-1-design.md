# Candidate Multi-Model Strategy v0.1 Design

- Status: Proposed for explicit review
- Date: 2026-07-24
- Issue: #16
- Promotion level: `RESEARCH_ONLY`
- Implementation authorized by this document: no

## 1. Purpose

Design the first non-synthetic strategy candidate for the verified Gemini Trading research platform. The candidate combines bounded trend, mean-reversion, and market-regime specialists behind deterministic arbitration. It consumes only verified point-in-time market data and runs only through the deterministic research and execution-simulation boundaries already accepted by the repository.

The candidate is not presumed profitable. The design makes the hypothesis falsifiable, constrains model-selection freedom, prevents leakage, and ensures that failure produces a documented rejection rather than post-hoc tuning.

## 2. Research hypothesis

A deterministic ensemble of complementary trend, mean-reversion, and market-regime specialists, using only completed BTC/USDT 4-hour Binance Spot OHLCV candles available at each decision timestamp, can improve net risk-adjusted performance over predeclared simple long/cash baselines after conservative simulated costs.

The ensemble must add measurable value over its strongest standalone specialist. It must abstain when evidence is weak, conflicting, incompatible with the detected regime, or insufficient to clear the cost-aware target.

The hypothesis is rejected when the locked candidate fails any mandatory untouched-test, robustness, integrity, or reproducibility gate in this document.

## 3. Non-goals

Candidate v0.1 does not include:

- a general-purpose probabilistic financial adviser;
- geopolitical, news, regulatory, social-media, or narrative analysis;
- OKX, derivatives, funding, open interest, liquidation, order-book, on-chain, macroeconomic, or cross-asset features;
- ETH/USDT model selection or rescue testing;
- deep neural networks, transformers, reinforcement learning, unrestricted AutoML, or continuously changing model pools;
- portfolio construction, dynamic allocation optimization, leverage, margin, futures, options, or shorting;
- broker, demo, or live exchange connectivity;
- credentials, private endpoints, order submission, or real-capital authority.

Deferred capabilities require separate design gates.

## 4. Existing trust boundaries

The implementation must preserve these accepted boundaries:

1. Canonical market data is content-addressed, continuous, completed, immutable, replayable, and independently verifiable.
2. Strategy decisions see completed candles only.
3. Official execution timing is next-candle timing.
4. Official fills and costs remain controlled by the deterministic simulator, not by strategy code.
5. Accounting uses exact repository domain contracts and fails closed.
6. Research evidence is immutable and provider-free replayable.
7. Diagnostic or optimistic policies are non-promotable.
8. Real-capital authorization remains a separate human decision.

## 5. Market and dataset scope

### 5.1 Locked scope

- Instrument: `BTC/USDT` spot.
- Timeframe: completed `4h` candles.
- Direction: long or cash only.
- Provider: Binance Spot public REST through the verified Market Data Core.
- Canonical schema: `candle-dataset-v1`.

### 5.2 Minimum history

A promotable experiment requires at least seven years of continuous completed 4-hour candles after canonical verification. This supports the locked 18-month untouched test and at least five complete development folds. If seven years are unavailable at the experiment cutoff, the result is `INSUFFICIENT_HISTORY` and cannot be promoted.

### 5.3 Dataset lock

Before fitting any model, lock:

- canonical dataset ID;
- first and last candle open times;
- exact candle count;
- instrument, timeframe, schema, and provider identities;
- repository commit;
- feature, label, split, model, calibration, regime, arbitration, risk, baseline, and cost-policy identities.

No later candle may be appended to the locked experiment. A changed cutoff creates a new dataset and experiment identity.

### 5.4 External replication

OKX and ETH/USDT may not select, tune, rescue, or reinterpret Candidate v0.1. They remain later independent replication gates.

## 6. Point-in-time feature contract

### 6.1 General requirements

Every feature must be deterministic, finite, trailing-only, reproducible from the canonical dataset without a network, and based only on candles completed by the decision timestamp. Learned normalization statistics must be fitted inside the current training fold.

Each feature requires a stable name, version, parameter set, lookback, data type, and provenance declaration.

Prohibited operations include centered windows, full-sample scaling, future extrema, future labels, backward filling from future values, random imputation, revised future observations, and index alignment that exposes later candles.

A missing, non-finite, insufficient-lookback, or misaligned feature makes the observation ineligible. Silent imputation is prohibited.

### 6.2 Locked registry

Maximum feature dependency is 42 candles.

#### Return and momentum

- log returns over 1, 2, 3, 6, 12, 24, and 42 candles;
- positive-return fraction over 6, 12, 24, and 42 candles;
- 3-candle return minus the preceding 3-candle return;
- distance from trailing 12- and 42-candle highs and lows.

#### Trend

- EMA 6, 12, 24, and 42 distances from close;
- EMA 6/24, 12/42, and 24/42 normalized spreads;
- EMA slopes over 3 and 6 candles;
- same-sign return fraction over 6, 12, and 24 candles.

#### Volatility and candle structure

- realized volatility over 6, 12, 24, and 42 candles;
- average true range over 6, 12, and 24 candles;
- current true range divided by trailing ATR 24;
- candle body/range, upper-wick/range, lower-wick/range, and close location;
- close location within trailing 12- and 24-candle ranges.

#### Mean-reversion state

- close z-score over 12, 24, and 42 candles;
- close distance from trailing 12-, 24-, and 42-candle median normalized by ATR 24;
- drawdown from trailing 12-, 24-, and 42-candle highs;
- rebound from trailing 12-, 24-, and 42-candle lows.

#### Volume

- log volume change over 1, 3, 6, and 12 candles;
- volume divided by trailing 12-, 24-, and 42-candle median volume;
- volume z-score over 24 and 42 candles;
- return sign multiplied by normalized volume;
- candle range multiplied by normalized volume.

### 6.3 Specialist isolation

- Trend specialist: return, momentum, trend, volatility, and volume features only.
- Mean-reversion specialist: mean-reversion state, candle structure, volatility, and volume features only.
- Regime specialist: deterministic trend-strength and volatility-state descriptors only.

This isolation prevents duplicate unrestricted learners.

## 7. Labels and horizon

### 7.1 Primary horizon

The decision horizon is three completed 4-hour candles, or 12 hours, measured from official next-candle execution.

For a decision after candle `t`:

- hypothetical entry uses the simulator's market execution on candle `t + 1`;
- hypothetical evaluation exit uses market execution after the third held candle;
- label economics use the locked base fee, spread, slippage, latency, precision, minimum-order, and liquidity assumptions.

### 7.2 Cost-aware positive class

The positive-class hurdle is:

```text
estimated base round-trip market execution cost + 10 basis points
```

With the currently accepted 10 bps taker fee, 5 bps half-spread, and 10 bps slippage per side, the initial hurdle is 60 bps. The implementation must derive this from the locked simulator configuration. A cost-policy change creates a new label identity.

Both learned specialists estimate the probability that the hypothetical 12-hour net return is strictly greater than the hurdle. Returns less than or equal to the hurdle are negative labels.

The target itself therefore enforces the cost hurdle; no separate learned expected-return mapping is permitted in v0.1.

### 7.3 Mean-reversion eligibility

The mean-reversion specialist is trained and evaluated only when at least one condition is active:

- trailing 24-candle close z-score is at most `-0.75`; or
- drawdown from trailing 24-candle high is at least `2%`.

The trend specialist uses all eligible observations.

### 7.4 Boundary overlap

The three-candle label horizon requires a three-candle purge and three-candle embargo. An observation whose label crosses a boundary may not appear on either side.

## 8. Specialist models

### 8.1 Trend specialist

Elastic-net logistic regression with:

- fold-local standardization;
- `C = 1.0`;
- `l1_ratio = 0.5`;
- `saga` solver;
- `max_iter = 10000`;
- tolerance `1e-8`;
- fixed seed `1701`;
- single-thread deterministic execution;
- inverse-frequency class weights only when the training positive fraction is outside `[0.30, 0.70]`.

### 8.2 Mean-reversion specialist

Deterministic shallow gradient-boosted decision trees with:

- 150 estimators;
- maximum depth 2;
- learning rate 0.03;
- minimum leaf size 100 observations;
- no row or feature subsampling;
- fixed seed `1702`;
- single-thread deterministic execution;
- no hyperparameter search.

The implementation plan must lock the exact library and version. Library identity becomes part of model identity.

### 8.3 Calibration

Each specialist uses logistic Platt calibration fitted only on the fold calibration segment.

A calibration segment requires at least 200 eligible observations, 40 positive labels, and 40 negative labels for that specialist. Otherwise the fold is invalid and the experiment fails closed.

Store Brier score, log loss, and ten-bin expected calibration error. These describe probability quality but do not replace economic gates.

### 8.4 Regime specialist

The regime classifier is deterministic and not fitted to profit labels.

```text
trend_strength = abs(EMA_12 - EMA_42) / ATR_24
volatility_ratio = realized_volatility_6 / realized_volatility_42
```

Evaluate states in order:

1. `UNSTABLE`: `volatility_ratio >= 1.75` or current true-range/ATR-24 ratio is at least `2.5`.
2. `TRENDING`: `trend_strength >= 1.0`, `volatility_ratio < 1.5`, and EMA 12/42 spread sign is unchanged for three completed candles.
3. `RANGING`: `trend_strength <= 0.5` and `volatility_ratio <= 1.25`.
4. `INDETERMINATE`: otherwise.

Store the regime with every decision.

## 9. Deterministic arbitration

### 9.1 Outputs

The candidate may emit only enter long, remain long, exit to cash, or remain in cash.

### 9.2 Entry

No new entry is allowed during `UNSTABLE` or `INDETERMINATE`.

During `TRENDING`:

- trend probability is at least `0.62`;
- mean-reversion probability, when available, is not below `0.45`;
- conflicting specialist probabilities differ by no more than `0.25`.

During `RANGING`:

- a mean-reversion eligibility condition is active;
- mean-reversion probability is at least `0.62`;
- trend probability is not below `0.45`;
- conflicting specialist probabilities differ by no more than `0.25`.

### 9.3 Position size

One long position targets the maximum affordable notional up to 100% of marked equity after reserving simulator-estimated entry costs. Precision, minimums, liquidity participation, and available cash remain simulator-controlled.

This normalizes signal evaluation and does not imply a future real-capital allocation.

### 9.4 Hold and exit

Hold only while:

- active specialist probability is at least `0.50`;
- regime remains compatible, or is `INDETERMINATE` for no more than one candle;
- no protection or maximum-hold exit has triggered.

Exit at next-candle execution when:

- active specialist probability is at most `0.45`;
- regime becomes `UNSTABLE`;
- regime is incompatible for two consecutive completed candles;
- a completed-candle low breaches protection;
- holding period reaches 18 candles, or 72 hours.

Protection rules:

- initial level: entry price minus `2.5 * ATR_24` measured at the entry decision;
- trailing level: highest completed close since entry minus `3.0 * ATR_24`, never lower than its prior value;
- breach detection uses a completed candle and exits no earlier than the next candle.

Minimum hold is two candles except for `UNSTABLE` or protection exits. A two-candle cooldown follows every exit. No pyramiding or discretionary scaling is allowed.

### 9.5 Fail closed

Missing output, invalid probability, missing regime, non-finite feature, identity mismatch, stale configuration, or insufficient evidence emits no new order and invalidates required evidence.

## 10. Baselines, ablations, and controls

All comparisons use identical datasets, timing, costs, precision, liquidity, and accounting.

### 10.1 Simple baselines

1. `cash.v1`: no trade.
2. `buy_hold.v1`: enter at the first eligible next-candle execution and hold.
3. `ema_20_50.v1`: long when EMA 20 is above EMA 50; otherwise cash.
4. `donchian_20_10.v1`: enter on completed-candle 20-bar high breakout; exit on completed-candle 10-bar low breakout.
5. `mean_reversion_z24.v1`: enter when z-score 24 is at most `-1.5`; exit at zero or common protection.

### 10.2 Required ablations and controls

- trend specialist without regime gating;
- mean-reversion specialist without regime gating;
- regime gate using the relevant simple baseline instead of learned models;
- ensemble without disagreement abstention;
- ensemble without volume features;
- ensemble without protection;
- all features delayed by one additional candle;
- shuffled labels for both learned specialists using seed `1799`.

A shuffled-label control passing any economic promotion gate invalidates the experiment.

## 11. Chronological evaluation

### 11.1 Final untouched test

The last 18 calendar months form the sealed final test. Dataset ID, time range, and observation count are recorded before training. Model-selection code may not open final-test predictions, metrics, or outcomes.

The locked candidate is evaluated once. Any later structural, model, feature, or threshold change creates Candidate v0.2 and requires a new future untouched era or independent replication dataset.

### 11.2 Development folds

All earlier data is the development era. Use expanding walk-forward folds:

- initial training: 24 months;
- calibration: 6 months;
- forward development test: 6 months;
- step: 6 months;
- purge: 3 candles;
- embargo: 3 candles.

At least five complete forward development-test folds are mandatory.

### 11.3 Multiple-testing control

Candidate v0.1 contains one locked architecture with fixed model parameters and thresholds. No performance-driven family, hyperparameter, feature, horizon, or threshold search is allowed.

Five simple baselines and required ablations are preregistered. Sensitivity variants are diagnostics and cannot replace the primary candidate.

## 12. Metrics

### 12.1 Required existing metrics

- starting and ending equity;
- gross and net return;
- realized and unrealized P&L;
- fees and execution costs;
- maximum drawdown;
- exposure;
- order, rejection, fill, partial-fill, and trade counts;
- win rate.

### 12.2 Required additional metrics

Add exact deterministic definitions for:

- annualized geometric return using 4-hour account snapshots;
- annualized volatility;
- downside deviation;
- Sortino ratio with zero minimum acceptable 4-hour return;
- return-to-drawdown ratio;
- turnover;
- exposure-adjusted net return;
- average and median trade return;
- profit factor;
- average hold duration;
- regime-level return, drawdown, exposure, and trade count;
- specialist Brier score, log loss, and expected calibration error.

Undefined ratios remain `null`.

The primary economic score is final-test annualized geometric return divided by maximum drawdown. Cash cannot become the strongest active baseline through a zero denominator.

## 13. Robustness and uncertainty

### 13.1 Cost stress

Replay locked decisions under base, 1.5-times, and 2-times fee, spread, and slippage. Predictions and decisions remain unchanged.

### 13.2 Parameter neighbourhood

Change one item at a time:

- entry probability: `0.59`, `0.65`;
- exit probability: `0.42`, `0.48`;
- maximum hold: 12, 24 candles;
- initial protection: 2.0, 3.0 ATR;
- cooldown: 1, 3 candles.

These ten variants cannot replace the primary candidate.

### 13.3 Block bootstrap

Use 1,000 deterministic moving-block replicates, block length 42 candles, seed `1788`, on final-test account-return differences against the strongest active baseline.

Report median and 90% confidence intervals for net-return difference, maximum-drawdown difference, and return-to-drawdown-ratio difference when defined.

## 14. Mandatory promotion gates

Advancement is only to a separately designed shadow or paper-consideration gate.

### 14.1 Integrity

All must pass:

- canonical dataset verification;
- continuity, completion, provenance, and identity checks;
- feature, label, normalization, alignment, and split leakage tests;
- complete folds, baselines, ablations, sensitivities, and controls;
- exact provider-free replay;
- independent verification.

### 14.2 Development stability

- at least five folds;
- at least 60% of folds have positive candidate net return;
- at least 60% beat the strongest active baseline's return-to-drawdown ratio when defined;
- no fold contributes more than 50% of summed positive fold profit;
- at least 60 completed development-test trades.

### 14.3 Final-test economics

- base-cost net return is positive;
- at least 30 completed trades;
- maximum drawdown is at most 25%;
- maximum drawdown is at most 80% of buy-and-hold drawdown;
- return-to-drawdown ratio is at least 0.50;
- return-to-drawdown ratio is at least 10% above the strongest active simple baseline;
- net return is no more than 2 percentage points below the strongest active simple baseline;
- ensemble return-to-drawdown ratio is at least 5% above the strongest standalone learned specialist;
- no trade contributes more than 25% of total positive trade profit;
- at least two of `TRENDING`, `RANGING`, and `INDETERMINATE` have non-negative contribution;
- no required regime loses more than 25% of aggregate positive profit.

`UNSTABLE` is assessed for avoided exposure, not required profit.

### 14.4 Cost robustness

- 1.5-times-cost net return is positive;
- 1.5-times-cost drawdown is at most 27.5%;
- 2-times-cost net return is at least `-5%`;
- 2-times-cost drawdown is at most 30%.

### 14.5 Sensitivity robustness

Across ten neighbourhood variants:

- at least seven have positive net return;
- median net return is positive;
- no drawdown exceeds 35%;
- when primary net return is at most 2%, no single variant may improve it by more than 100%.

### 14.6 Uncertainty and component controls

- bootstrap median net-return difference versus the strongest active baseline is positive;
- bootstrap 90% lower bound is above `-2` percentage points;
- shuffled-label controls fail every economic promotion gate;
- extra-delayed features do not beat the primary return-to-drawdown ratio by more than 5%;
- removing disagreement abstention must not improve return-to-drawdown by at least 10% while also producing drawdown no higher than the primary candidate;
- removing volume must not improve return-to-drawdown by at least 10% while also producing drawdown no higher than the primary candidate;
- removing protection must not improve return-to-drawdown by at least 10% while also reducing maximum drawdown.

If any of the final three conditions fails, the claimed component is unsupported and Candidate v0.1 is rejected rather than rewritten after final-test observation.

## 15. Automatic rejection or inconclusive classification

Reject or classify inconclusive on:

- insufficient history, folds, calibration classes, or final-test trades;
- any point-in-time, look-ahead, label, split, normalization, or alignment leakage;
- final-test access before sealing;
- any change after final-test observation;
- negative-control promotion;
- non-deterministic output or artifact mismatch;
- base-cost final-test loss;
- any mandatory drawdown, baseline, ensemble-increment, cost, sensitivity, uncertainty, or component gate failure;
- dependence on one fold, trade, threshold, or feature family beyond declared limits;
- missing evidence, provider-dependent replay, or failed verification;
- undocumented exclusion of failed experiments or folds.

Rejected evidence remains immutable and cannot be relabeled successful through narrative interpretation.

## 16. Identities and artifacts

### 16.1 Identities

Content-address:

- dataset;
- feature registry and matrices;
- label policy and vectors;
- split plan;
- model family, library, configuration, fitted model, and calibration per fold;
- seed policy;
- regime, arbitration, risk, baseline, ablation, and cost policies;
- experiment and result.

### 16.2 Artifacts

Persist:

- locked configuration;
- point-in-time feature audit;
- split and boundary audit;
- fold statistics, labels, models, calibrators, probabilities, and regimes;
- decisions and reason codes;
- orders, rejections, fills, accounts, trades, and metrics;
- baseline, ablation, control, cost, sensitivity, and bootstrap results;
- gate report with a reason for every pass or failure;
- replay and independent-verification receipts;
- limitations and final classification.

Replay must require no provider or network.

## 17. Component boundaries

1. `FeatureRegistry`: trailing point-in-time features.
2. `LabelPolicy`: cost-aware 12-hour labels isolated from decision-time code.
3. `ChronologicalSplitPlan`: sealed folds and untouched test.
4. `TrendSpecialistTrainer`: locked elastic-net model.
5. `MeanReversionSpecialistTrainer`: locked shallow boosted-tree model.
6. `ProbabilityCalibrator`: fold-local Platt calibration.
7. `RegimeClassifier`: deterministic states.
8. `MultiModelArbiter`: valid outputs and account state to long/cash intents.
9. `BaselineSuite`: identical-policy comparisons.
10. `EvaluationSuite`: fold, final, regime, robustness, uncertainty, and gates.
11. `StrategyArtifactStore`: immutable evidence.
12. `StrategyReplayVerifier`: reconstruction and independent verification.

Model and feature code may not control accounting or fills.

## 18. Error handling

Classify and fail closed on:

- insufficient history or lookback;
- invalid feature or probability;
- point-in-time violation;
- split overlap;
- label leakage;
- insufficient calibration classes;
- model determinism failure;
- configuration or identity mismatch;
- missing artifact;
- replay mismatch;
- incomplete required evidence.

CLI errors must not expose credentials, raw provider bodies, environment dumps, absolute operator paths, or uncontrolled tracebacks.

## 19. Testing

### Unit

Cover every feature, label, regime rule, calibration contract, threshold, risk rule, metric, identity, and serialization boundary.

### Property

Prove:

- future candles cannot alter prior features or decisions;
- equivalent inputs produce identical identities and outputs;
- probabilities are finite and within `[0, 1]`;
- no sell exceeds position;
- no prohibited-regime or cooldown entry occurs;
- higher costs cannot improve net equity with fixed decisions and fills;
- serialization is deterministic.

### Regression

Cover full-sample normalization, label overlap, next-candle off-by-one, feature/label misalignment, premature final-test access, model randomness, negative-control promotion, and artifact tampering.

### Integration

Run a deterministic fixture through features, labels, splits, specialists, calibration, regime gating, arbitration, simulation, artifacts, replay, and verification.

### Acceptance

Demonstrate a complete historical research run, byte-stable provider-free replay, independent verification, rejection of live/demo/production modes, safe insufficient-evidence classification, final-test sealing, and a complete pass/fail gate report.

## 20. Governance and capital boundary

- Runtime remains `RESEARCH_ONLY`.
- No credentials, private endpoints, broker, demo, live, or real-capital submission.
- No automatic promotion.
- The assistant may independently review evidence and limitations.
- A human must separately authorize any future shadow, paper, demo, or real-capital stage.
- Passing establishes research-candidate evidence only, not durable profitability or capital safety.

## 21. Sequencing constraint

No implementation plan or strategy code may begin until:

1. this specification is explicitly reviewed and approved;
2. requested changes are incorporated;
3. self-review confirms no placeholders, contradictions, or unresolved scope ambiguity;
4. the approved specification is committed;
5. a separate implementation plan is written and reviewed.

Implementation must then proceed through test-driven, independently verifiable milestones without silently broadening scope.