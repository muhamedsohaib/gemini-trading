# Candidate Multi-Model Strategy v0.1 Design

- Status: Proposed for explicit review
- Date: 2026-07-24
- Issue: #16
- Promotion level: `RESEARCH_ONLY`
- Implementation authorized by this document: no

## 1. Purpose

Design the first non-synthetic strategy candidate for the verified Gemini Trading research platform. The candidate combines bounded trend, mean-reversion, and market-regime specialists behind deterministic arbitration. It consumes only verified point-in-time market data and runs only through the deterministic research and execution-simulation boundaries already accepted by the repository.

The candidate is not presumed profitable. The design exists to make the hypothesis falsifiable, constrain model-selection freedom, prevent leakage, and ensure that failure produces a documented rejection rather than post-hoc tuning.

## 2. Research hypothesis

A deterministic ensemble of complementary trend, mean-reversion, and market-regime specialists, using only completed BTC/USDT 4-hour Binance Spot OHLCV candles available at each decision timestamp, can improve net risk-adjusted performance over predeclared simple long/cash baselines after conservative simulated costs.

The ensemble must add measurable value over its strongest standalone specialist. It must abstain when its evidence is weak, conflicting, incompatible with the detected regime, or insufficient to clear costs.

The hypothesis is rejected when the locked candidate fails any mandatory untouched-test, robustness, integrity, or reproducibility gate defined in this document.

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

The design preserves these accepted repository boundaries:

1. Canonical market data is content-addressed, continuous, completed, immutable, replayable, and independently verifiable.
2. Strategy decisions see completed candles only.
3. Official execution timing is next-candle timing.
4. Official fills and costs remain controlled by the deterministic simulator, not by strategy code.
5. Accounting uses exact repository domain contracts and fails closed.
6. Research evidence is immutable and provider-free replayable.
7. Diagnostic or optimistic policies are non-promotable.
8. Real-capital authorization remains a separate human decision.

The strategy implementation may not bypass or redefine these boundaries.

## 5. Market and dataset scope

### 5.1 Instrument and timeframe

- Instrument: `BTC/USDT` spot.
- Timeframe: completed `4h` candles.
- Direction: long or cash only.
- Provider: Binance Spot public REST through the verified Market Data Core.
- Canonical schema: `candle-dataset-v1`.

### 5.2 Minimum history

A promotable experiment requires at least six years of continuous completed 4-hour candles after canonical verification. If six years are unavailable at the locked experiment cutoff, the result is `INSUFFICIENT_HISTORY` and cannot be promoted.

### 5.3 Dataset lock

Before model fitting, the experiment must lock:

- canonical dataset ID;
- first and last included candle open times;
- exact candle count;
- instrument and timeframe identity;
- canonical schema version;
- provider identity;
- repository commit;
- feature, label, split, model, arbitration, and cost-policy identities.

No later candle may be appended to the locked experiment. A new cutoff produces a new dataset and experiment identity.

### 5.4 External replication

OKX and ETH/USDT are not available for selecting, tuning, rescuing, or reinterpreting Candidate v0.1. They are reserved for later independent replication gates after this design is implemented and evaluated.

## 6. Point-in-time feature contract

### 6.1 General requirements

Every feature must be:

- deterministic;
- finite;
- based only on candles completed by the decision timestamp;
- computed with trailing windows only;
- fitted or normalized within the current training fold only when learned statistics are required;
- assigned a stable name, version, parameters, lookback, data type, and provenance declaration;
- reproducible from the canonical dataset without a provider or network.

Prohibited operations include centered windows, full-sample scaling, future extrema, future labels, revised future observations, random imputation, backward filling from future values, and any index alignment that exposes later candles.

A missing, non-finite, insufficient-lookback, or misaligned feature makes that observation ineligible. Silent imputation is prohibited in v0.1.

### 6.2 Feature registry

The maximum feature dependency is 42 candles. The locked registry contains:

#### Return and momentum

- log return over 1, 2, 3, 6, 12, 24, and 42 candles;
- cumulative positive-return fraction over 6, 12, 24, and 42 candles;
- close-to-close acceleration: 3-candle return minus prior 3-candle return;
- distance from trailing 12- and 42-candle highs and lows.

#### Trend

- EMA 6, 12, 24, and 42 distances from close;
- EMA 6/24, 12/42, and 24/42 normalized spreads;
- trailing EMA slopes over 3 and 6 candles;
- trend consistency: fraction of same-sign 1-candle returns over 6, 12, and 24 candles.

#### Volatility and candle structure

- realized volatility over 6, 12, 24, and 42 candles;
- true-range average over 6, 12, and 24 candles;
- current true range divided by trailing 24-candle average true range;
- candle body divided by range;
- upper- and lower-wick fractions;
- close location within the current candle range;
- rolling close location within the trailing 12- and 24-candle high-low range.

#### Mean-reversion state

- close z-score against trailing 12-, 24-, and 42-candle mean and standard deviation;
- close distance from trailing 12-, 24-, and 42-candle median, normalized by average true range;
- drawdown from the trailing 12-, 24-, and 42-candle high;
- rebound from the trailing 12-, 24-, and 42-candle low.

#### Volume

- log volume change over 1, 3, 6, and 12 candles;
- volume divided by trailing 12-, 24-, and 42-candle median volume;
- trailing volume z-score over 24 and 42 candles;
- signed volume proxy: candle return sign multiplied by normalized volume;
- price-range multiplied by normalized volume.

### 6.3 Specialist feature isolation

The trend specialist receives only return, momentum, trend, volatility, and volume features.

The mean-reversion specialist receives only mean-reversion state, candle structure, volatility, and volume features.

The regime specialist receives only deterministic trend-strength and volatility-state descriptors defined below.

Feature isolation prevents the specialists from becoming duplicate unrestricted learners.

## 7. Labels and decision horizon

### 7.1 Primary horizon

The primary decision horizon is three completed 4-hour candles, or 12 hours, measured from official next-candle execution.

For a decision after candle `t`:

- hypothetical entry occurs at the simulator's next-candle market execution for candle `t + 1`;
- hypothetical evaluation exit occurs at the simulator's market execution after the third held candle;
- the label uses the same conservative fee, spread, slippage, latency, precision, and minimum-order assumptions as the locked base simulation policy.

### 7.2 Cost hurdle

The positive-class hurdle equals:

```text
base estimated round-trip market execution cost + 10 basis points
```

Under the current accepted base assumptions of 10 bps taker fee, 5 bps half-spread, and 10 bps slippage per side, the initial hurdle is 60 bps. The calculation must be derived from the locked simulation configuration rather than duplicated as an unrelated constant. Any cost-policy change creates a new label identity.

### 7.3 Shared binary target

Both learned specialists estimate the probability that the hypothetical 12-hour trade's net return exceeds the cost hurdle.

- Positive label: net return strictly greater than the hurdle.
- Negative label: net return less than or equal to the hurdle.

The mean-reversion specialist is trained only on observations satisfying at least one predeclared downside-stretch condition:

- trailing 24-candle close z-score less than or equal to `-0.75`; or
- drawdown from trailing 24-candle high greater than or equal to `2%`.

The trend specialist is trained on all eligible observations.

### 7.4 Overlap control

Because labels use three future candles, chronological boundaries require a minimum three-candle purge and a three-candle embargo. No observation whose label window crosses a boundary may be used on either side of that boundary.

## 8. Specialist models

### 8.1 Trend specialist

Model family: elastic-net logistic regression.

Locked training configuration:

- standardized numeric features using training-fold mean and standard deviation only;
- regularization strength `C = 1.0`;
- elastic-net mixing `l1_ratio = 0.5`;
- deterministic solver and iteration limit;
- fixed random seed `1701` when the implementation requires a seed;
- no class rebalancing unless the positive-class fraction falls outside `[0.30, 0.70]` in the training fold, in which case deterministic inverse-frequency weights are used and recorded.

### 8.2 Mean-reversion specialist

Model family: shallow gradient-boosted decision trees.

Locked training configuration:

- 150 estimators;
- maximum depth 2;
- learning rate 0.03;
- minimum leaf size 100 observations;
- full deterministic row and feature participation with no stochastic subsampling;
- fixed random seed `1702`;
- no unrestricted hyperparameter search.

### 8.3 Calibration

Each learned specialist is calibrated with logistic Platt scaling fitted only on the fold's calibration segment.

A calibration segment must contain at least 200 eligible observations, at least 40 positive labels, and at least 40 negative labels. Otherwise the fold is invalid and the experiment fails closed.

Calibration evidence includes Brier score, log loss, and ten-bin expected calibration error. Calibration statistics are diagnostic; they do not replace economic evaluation.

### 8.4 Regime specialist

The regime specialist is deterministic and not fitted to profit labels.

Define:

```text
trend_strength = abs(EMA_12 - EMA_42) / ATR_24
volatility_ratio = realized_volatility_6 / realized_volatility_42
```

States are evaluated in this order:

1. `UNSTABLE` when `volatility_ratio >= 1.75` or current true-range ratio is at least `2.5`.
2. `TRENDING` when `trend_strength >= 1.0`, `volatility_ratio < 1.5`, and the EMA 12/42 spread sign is unchanged for the previous three completed candles.
3. `RANGING` when `trend_strength <= 0.5` and `volatility_ratio <= 1.25`.
4. `INDETERMINATE` otherwise.

The regime state uses completed candles only and is stored with every strategy decision.

## 9. Deterministic arbitration

### 9.1 Candidate outputs

The candidate may emit only:

- enter long;
- remain long;
- exit to cash;
- remain in cash.

Abstention is represented by remaining in cash or preserving an existing position only when hold conditions remain valid.

### 9.2 Entry rules

No new entry is permitted during `UNSTABLE` or `INDETERMINATE` regimes.

During `TRENDING`:

- trend probability must be at least `0.62`;
- expected gross edge implied by the development-fold probability/return mapping must exceed the locked cost hurdle plus 10 bps;
- mean-reversion probability, when available, must not be below `0.45`;
- the difference between available specialist probabilities must not exceed `0.25` when they imply conflicting economic actions.

During `RANGING`:

- at least one mean-reversion stretch condition must be active;
- mean-reversion probability must be at least `0.62`;
- expected gross edge must exceed the locked cost hurdle plus 10 bps;
- trend probability must not be below `0.45`;
- specialist disagreement must satisfy the same `0.25` limit.

### 9.3 Position size

Official strategy comparisons use one long position with a target notional equal to 100% of marked equity at entry, subject to simulator precision, minimums, liquidity participation, and available cash. This normalizes signal evaluation and avoids a separate sizing optimization.

Position sizing is research-only and does not imply a future real-capital allocation.

### 9.4 Hold and exit rules

A position is held only while all applicable conditions remain true:

- active specialist probability remains at least `0.50`;
- regime remains compatible with the specialist or becomes `INDETERMINATE` for no more than one candle;
- no risk-stop, trailing protection, or maximum-hold condition has triggered.

Exit to cash at the next-candle execution when any condition occurs:

- active specialist probability is at most `0.45`;
- regime becomes `UNSTABLE`;
- regime is incompatible with the active specialist for two consecutive completed candles;
- completed-candle low breaches the initial or trailing protection level;
- maximum holding period reaches 18 candles, or 72 hours.

Risk protection:

- initial protection level: entry price minus `2.5 * ATR_24` measured at the entry decision;
- trailing protection level after entry: highest completed close since entry minus `3.0 * ATR_24`, never lower than the prior trailing level;
- a breach is detected from a completed candle and exits no earlier than the next candle.

Minimum holding period is two candles except for `UNSTABLE` regime or risk-protection exits.

After any exit, a two-candle cooldown prevents re-entry. No pyramiding or partial discretionary scaling is allowed.

### 9.5 Fail-closed behavior

Missing specialist output, invalid probability, missing regime state, non-finite feature, identity mismatch, stale configuration, or insufficient history produces no new order and classifies the experiment as invalid when it affects required evidence.

## 10. Baselines and ablations

Every baseline runs through the identical dataset, next-candle execution, cost, precision, liquidity, and accounting policies.

### 10.1 Required baselines

1. `cash.v1`: no trade.
2. `buy_hold.v1`: enter at the first eligible next-candle execution and hold through the evaluation window.
3. `ema_20_50.v1`: long when EMA 20 is above EMA 50; otherwise cash.
4. `donchian_20_10.v1`: enter on completed-candle 20-bar high breakout and exit on completed-candle 10-bar low breakout.
5. `mean_reversion_z24.v1`: enter when trailing 24-bar close z-score is at most `-1.5`; exit when it reaches zero or the common risk stop triggers.

### 10.2 Required ablations

- trend specialist with common risk rules but without regime gating;
- mean-reversion specialist with common risk rules but without regime gating;
- deterministic regime gate using the relevant simple baseline instead of a learned specialist;
- ensemble without disagreement abstention;
- ensemble without volume features;
- ensemble without risk protection;
- ensemble with all features delayed by one additional candle;
- shuffled-label trend and mean-reversion specialists using seed `1799`.

A shuffled-label or extra-delayed negative control that appears promotable invalidates the experiment and triggers leakage/integrity investigation.

## 11. Chronological evaluation protocol

### 11.1 Final untouched test

The last 18 calendar months of the locked canonical dataset form the final untouched test era.

The final test dataset ID, time range, and expected observation count are sealed before any model training. The implementation must prevent final-test metrics, predictions, and outcomes from being opened by model-selection code.

The final test is evaluated once for the locked candidate configuration. Failure cannot be repaired by tuning against the final test. Any subsequent change creates Candidate v0.2 and requires a new future untouched era or an explicitly independent replication dataset.

### 11.2 Development era

All data before the final 18 months forms the development era.

Development uses expanding-window walk-forward folds with:

- minimum initial training window: 24 months;
- calibration/validation window: 6 months;
- forward development-test window: 6 months;
- step size: 6 months;
- purge: 3 candles;
- embargo: 3 candles.

At least five complete forward development-test folds are required. Otherwise the experiment is `INSUFFICIENT_FOLDS` and cannot be promoted.

### 11.3 Selection freedom

Candidate v0.1 has one locked end-to-end architecture and no performance-driven model-family or hyperparameter search.

The only permitted development selection is the learned probability-to-expected-return mapping fitted within each fold. All structural thresholds and model parameters in this design are fixed before the final test.

This design controls multiple testing by pre-registering one primary candidate, five simple baselines, and the required ablations. Sensitivity variants are robustness diagnostics and may not replace the primary candidate.

## 12. Metrics

### 12.1 Existing deterministic economic metrics

Required existing metrics include:

- starting and ending equity;
- gross and net return;
- realized and unrealized profit and loss;
- total fees and execution costs;
- maximum drawdown;
- exposure fraction;
- order, rejection, fill, partial-fill, and completed-trade counts;
- win rate.

### 12.2 Additional deterministic metrics

The strategy milestone must add exact documented definitions for:

- annualized geometric return from 4-hour account snapshots;
- annualized volatility;
- downside deviation;
- Sortino ratio using zero as the minimum acceptable 4-hour return;
- return-to-drawdown ratio: annualized geometric return divided by maximum drawdown;
- turnover as total traded notional divided by average marked equity;
- exposure-adjusted net return;
- average and median completed-trade return;
- profit factor;
- average holding duration;
- regime-level net return, drawdown, exposure, and trade count;
- Brier score, log loss, and expected calibration error for each specialist.

Undefined ratios remain `null`; they may not be replaced with infinity or arbitrary caps.

### 12.3 Primary promotion score

The primary economic comparison is the return-to-drawdown ratio on the untouched final test.

When a comparator has zero maximum drawdown, it is eligible only if its net return is positive; cash remains contextual and cannot become the strongest active baseline through a zero denominator.

## 13. Robustness and uncertainty

### 13.1 Cost sensitivity

Re-run the locked final-test decisions under:

- base costs;
- 1.5 times fee, spread, and slippage assumptions;
- 2.0 times fee, spread, and slippage assumptions.

Model predictions and decisions remain unchanged; only execution economics are stressed.

### 13.2 Parameter-neighbourhood sensitivity

Run diagnostic variants changing one item at a time:

- entry threshold: `0.59` and `0.65` instead of `0.62`;
- exit threshold: `0.42` and `0.48` instead of `0.45`;
- maximum hold: 12 and 24 candles instead of 18;
- initial ATR protection: 2.0 and 3.0 instead of 2.5;
- cooldown: 1 and 3 candles instead of 2.

These variants cannot replace the primary candidate.

### 13.3 Block bootstrap

Use 1,000 deterministic moving-block bootstrap replicates with block length 42 candles and seed `1788` on final-test account-return differences between the candidate and the strongest active baseline.

Report the median and 90% confidence interval for:

- net-return difference;
- maximum-drawdown difference;
- return-to-drawdown-ratio difference when defined.

The bootstrap is uncertainty evidence, not permission to override mandatory economic gates.

## 14. Mandatory promotion gates

Candidate v0.1 may advance only to a separately designed shadow or paper-consideration gate when every condition passes.

### 14.1 Integrity and reproducibility

- canonical dataset verification passes;
- no continuity, completion, provenance, or identity failure;
- no feature or label leakage test failure;
- exact replay reproduces experiment and result identities and all core artifact bytes;
- independent verification passes;
- all required folds, baselines, ablations, sensitivities, and negative controls complete.

### 14.2 Development stability

- at least five forward development-test folds;
- at least 60% of folds have positive candidate net return;
- at least 60% of folds beat the strongest active baseline's return-to-drawdown ratio when both ratios are defined;
- no single fold contributes more than 50% of summed positive fold profit;
- the candidate has at least 60 completed development-test trades across folds.

### 14.3 Untouched final-test economics

- net return is strictly positive under base costs;
- at least 30 completed trades;
- maximum drawdown is at most 25%;
- maximum drawdown is at most 80% of buy-and-hold maximum drawdown;
- return-to-drawdown ratio is at least 0.50;
- return-to-drawdown ratio is at least 10% greater than the strongest active simple baseline;
- net return is not lower than the strongest active simple baseline by more than 2 percentage points;
- ensemble return-to-drawdown ratio is at least 5% greater than the strongest standalone learned specialist;
- no single completed trade contributes more than 25% of total positive completed-trade profit;
- at least two of `TRENDING`, `RANGING`, and `INDETERMINATE` regimes have non-negative net contribution, and no required regime loses more than 25% of aggregate positive profit.

`UNSTABLE` is expected to remain predominantly cash and is assessed for avoided exposure rather than required profit.

### 14.4 Cost robustness

- 1.5-times-cost net return remains strictly positive;
- 1.5-times-cost maximum drawdown remains at most 27.5%;
- 2-times-cost net return is no worse than `-5%`;
- 2-times-cost maximum drawdown remains at most 30%.

### 14.5 Sensitivity robustness

Across the ten one-at-a-time parameter-neighbourhood variants:

- at least seven have positive net return;
- median net return is positive;
- no variant exceeds 35% maximum drawdown;
- no single neighbouring value improves final-test net return by more than 100% while the primary candidate is barely positive, because that pattern indicates threshold instability requiring rejection.

### 14.6 Uncertainty and controls

- moving-block bootstrap median net-return difference versus the strongest active baseline is positive;
- the 90% interval lower bound for net-return difference is greater than `-2` percentage points;
- shuffled-label controls fail all economic promotion gates;
- the extra-delayed-feature control does not outperform the primary candidate's return-to-drawdown ratio by more than 5%;
- removing disagreement abstention does not reduce trade count while materially improving all risk metrics, because that result would invalidate the claimed value of arbitration;
- ensemble-without-volume and ensemble-without-risk-protection results are reported and do not expose a hidden dependence on one arbitrary component.

## 15. Automatic rejection conditions

The candidate is rejected or classified inconclusive when any condition occurs:

- insufficient history, folds, calibration classes, or final-test trades;
- point-in-time, look-ahead, label, split, normalization, or alignment leakage;
- final-test access before the candidate configuration is sealed;
- any structural or threshold change after final-test observation;
- negative-control promotion;
- non-deterministic model output or artifact mismatch;
- base-cost untouched-test net loss;
- mandatory drawdown, baseline, ensemble-increment, cost, sensitivity, or uncertainty gate failure;
- outcome depends materially on one fold, trade, arbitrary threshold, or feature family;
- missing evidence, provider-dependent replay, or failed independent verification;
- undocumented exclusion of failed experiments or folds.

A rejected result remains stored as immutable research evidence. It cannot be relabeled successful through narrative interpretation.

## 16. Identities and artifacts

### 16.1 Required identities

Content-address and persist:

- dataset identity;
- feature-registry identity;
- feature-matrix identity per split;
- label-policy and label-vector identities;
- chronological split-plan identity;
- model-family and fixed-configuration identities;
- fitted model identity per fold;
- calibration identity per fold;
- random-seed policy identity;
- regime-policy identity;
- arbitration-policy identity;
- risk-policy identity;
- baseline and ablation identities;
- simulation-cost-policy identity;
- experiment and result identities.

### 16.2 Required artifacts

Persist immutable canonical artifacts for:

- complete locked configuration;
- feature registry and point-in-time audit;
- split plan and boundary audit;
- fold feature statistics;
- fold labels;
- fitted specialist models and calibration parameters;
- fold and final-test probabilities;
- regime states;
- arbitration decisions and reason codes;
- orders, rejections, fills, account snapshots, completed trades, and metrics;
- baseline, ablation, negative-control, cost-sensitivity, parameter-sensitivity, and bootstrap results;
- promotion-gate evaluation with pass/fail reason per gate;
- replay receipt;
- independent-verification receipt;
- limitations and final classification.

Provider-free replay must require no exchange or network access.

## 17. Component boundaries

The implementation plan must preserve these independently testable units:

1. `FeatureRegistry`: declares and computes trailing point-in-time features.
2. `LabelPolicy`: derives cost-aware 12-hour labels without exposing them to decision-time code.
3. `ChronologicalSplitPlan`: seals development folds and final untouched boundaries.
4. `TrendSpecialistTrainer`: fits the locked elastic-net model.
5. `MeanReversionSpecialistTrainer`: fits the locked shallow boosted-tree model.
6. `ProbabilityCalibrator`: fits and applies fold-local Platt calibration.
7. `RegimeClassifier`: emits deterministic regime states.
8. `MultiModelArbiter`: converts valid specialist outputs and account state into long/cash intents.
9. `BaselineSuite`: runs all predeclared comparisons under identical simulation assumptions.
10. `EvaluationSuite`: computes fold, final, regime, robustness, uncertainty, and promotion evidence.
11. `StrategyArtifactStore`: serializes immutable model and evaluation evidence.
12. `StrategyReplayVerifier`: reconstructs and independently verifies the complete experiment.

Model and feature code may not control accounting or simulator fill behavior.

## 18. Error handling

Errors must be classified, safe, and fail closed. Required classes include:

- insufficient history or lookback;
- invalid feature value;
- point-in-time violation;
- split overlap or boundary violation;
- label leakage;
- insufficient calibration classes;
- model determinism failure;
- probability range violation;
- strategy configuration mismatch;
- missing artifact;
- identity mismatch;
- replay mismatch;
- required evidence incomplete.

CLI errors must not emit credentials, raw provider bodies, environment dumps, absolute operator paths, or uncontrolled tracebacks.

## 19. Testing strategy

### 19.1 Unit tests

Cover every feature, label, regime rule, calibration contract, arbitration threshold, risk rule, metric, identity, and serialization boundary.

### 19.2 Property tests

Prove:

- future-candle changes cannot alter prior features or decisions;
- equivalent canonical inputs produce identical identities and outputs;
- probabilities remain finite and within `[0, 1]`;
- no sell can exceed the long position;
- no order occurs in prohibited regimes or during cooldown;
- cost increases cannot improve net equity when decisions and fills are otherwise fixed;
- artifact serialization is deterministic.

### 19.3 Regression tests

Include explicit regressions for:

- full-sample normalization leakage;
- label overlap at fold boundaries;
- off-by-one next-candle execution;
- feature/label index misalignment;
- final-test access before seal;
- model randomness despite fixed seeds;
- negative-control false promotion;
- tampered model, feature, prediction, or evaluation artifacts.

### 19.4 Integration tests

Run a small deterministic canonical fixture through features, labels, folds, specialists, calibration, regime gating, arbitration, simulation, artifacts, replay, and verification.

### 19.5 Acceptance tests

Acceptance must demonstrate:

- one complete historical research run;
- provider-free byte-stable replay;
- independent verification;
- safe rejection of live/demo/production modes;
- safe classification of insufficient evidence;
- correct final-test sealing;
- complete gate report containing failures as well as passes.

## 20. Security, governance, and capital boundary

- Runtime remains `RESEARCH_ONLY`.
- No credentials or private exchange endpoints.
- No broker, demo, live, or real-capital order submission.
- No automatic strategy promotion.
- The assistant may independently review evidence, limitations, and gate status.
- A human must separately authorize any future shadow, paper, demo, or real-capital stage.
- Passing this design's gates establishes only research-candidate evidence. It does not establish durable profitability or capital safety.

## 21. Implementation sequencing constraint

No implementation plan or strategy code may begin until:

1. this written specification is explicitly reviewed and approved;
2. any requested changes are incorporated;
3. a self-review confirms no placeholders, contradictions, or unresolved scope ambiguity;
4. the approved specification is committed;
5. a separate implementation plan is written and reviewed.

The implementation must proceed through test-driven, independently verifiable milestones and may not silently broaden this scope.