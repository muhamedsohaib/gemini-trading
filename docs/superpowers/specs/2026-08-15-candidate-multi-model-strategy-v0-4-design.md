# Candidate Multi-Model Strategy v0.4 Design

- Status: approved design, pending written-spec review
- Date: 2026-08-15
- Design gate: GitHub Issue #73
- Base main commit at design start: `e13691cf3cda3e046287889765949770ee16f9c0`
- Promotion level: `RESEARCH_ONLY`
- Strategy identity: `candidate.multi_model.v0_4`
- Policy identity: `candidate-multi-model-v0.4`
- Policy schema: `candidate-strategy-policy-v4`
- Implementation authorized by this document: no
- Execution or capital authority: none

## 1. Purpose

Candidate v0.4 is a separately governed successor to terminally rejected Candidate v0.3. It does not rescue, retune, rerun, or reinterpret v0.3.

The v0.3 qualification was a complete, valid, substantive `REJECTED`: integrity, deterministic convergence, calibration construction, percentile replay, provider-free replay, and independent verification passed, while the candidate produced 0/12 positive development folds and only 14 completed trades and failed development economics, trade-count, concentration, cost robustness, sensitivity, several component controls, and paired-bootstrap uncertainty.

The new v0.4 hypothesis is structural rather than parametric:

> Conditional on a slow, fully completed 4h market regime and a bounded 4h context vector, regime-owned 1h trend and mean-reversion specialists can identify sufficiently frequent BTCUSDT long opportunities with stable positive net edge after conservative simulated costs.

The principal experimental change is the information hierarchy: 4h determines market context and specialist ownership; 1h provides tactical observations and decisions. The market, long/cash direction, specialist model families, deterministic simulator, cost philosophy, and research governance remain constrained so that any improvement can be attributed more cleanly to the multi-timeframe architecture.

Qualification semantics remain `QUALIFIED`, `REJECTED`, and `INCONCLUSIVE`. None authorizes paper, demo, live, production, allocation, or capital deployment.

## 2. Safety, provenance, and scientific boundary

The entire milestone is `RESEARCH_ONLY`.

It does not authorize exchange credentials, private endpoints, broker connectivity, paper/demo/live orders, leverage, margin, futures, options, shorting, portfolio allocation, autonomous capital, or production execution.

The repository may document substantial ChatGPT/OpenAI-assisted design, reasoning, code generation, testing, and verification as project provenance. Such provenance is not evidence of predictive validity and must not be represented as proof that OpenAI models possess inherent market-predictive ability. Predictive claims require the preregistered evidence in this specification and, ultimately, untouched prospective evidence.

## 3. Predecessor evidence and redesign boundary

Candidate v0.3 remains immutable and terminally rejected.

Its verified terminal identities are:

```text
merged source              e13691cf3cda3e046287889765949770ee16f9c0
verified Stage 1 run       31850700296
Stage 1 dataset ID         c90a49d3bf28daf375230609547301cc538e8998b8a69ab405f38d9921cff811
qualification run          31858191469
qualification ID           1ed6d119efacd5317af868a9ec2286e3f9440d6ce926bdf900c7da67b4ac96eb
qualification inventory    6e13ab069dff4d7a44248eb736ddcdcb0e90bbb889663fb8b9794dadcecaffd8
result                     REJECTED
prospective access         none
```

The following v0.3 evidence motivates v0.4 but may not be changed retroactively:

- 0/12 positive development folds;
- 14 completed development trades versus a mandatory minimum of 60;
- negative aggregate economics under base and stressed costs;
- poor sensitivity-neighbor behavior;
- failed no-percentile-selectivity, delayed-feature, and no-protection controls;
- strongly negative paired-bootstrap uncertainty;
- integrity, calibration, deterministic replay, and independent verification nevertheless passed.

Therefore v0.4 changes the temporal information architecture and specialist operating domains. It does not simply lower thresholds or weaken qualification gates.

## 4. Locked market and development data

### 4.1 Market scope

```text
Provider:        Binance Spot public historical evidence
Instrument:      BTCUSDT
Direction:       long or cash only
Tactical clock:  completed 1h candles
Context clock:   completed 4h candles derived from canonical 1h evidence
```

No other asset, derivative, short exposure, funding rate, order book, on-chain series, sentiment feed, news feed, macro series, or cross-asset input participates in v0.4.

### 4.2 Immutable development window

The complete v0.4 development window is fixed to:

```text
[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)
```

No candle at or after `2026-08-01T00:00:00Z` may influence v0.4 feature selection, model fitting, calibration, percentile construction, expected-return mapping, development testing, controls, sensitivity, bootstrap analysis, rule selection, qualification, or rescue analysis.

The same historical cutoff is retained deliberately. Moving the cutoff forward merely to add post-v0.3 observations would add researcher degrees of freedom without creating genuinely untouched evidence.

A fresh Stage 1 canonical 1h dataset and handoff must later be generated from the exact protected-merged v0.4 implementation source. No v0.3 Stage 1 artifact or approval marker may be reused.

### 4.3 Canonical 1h timeline

The verified 1h series is the sole canonical tactical timeline. It must preserve the repository's existing content-addressed raw evidence, completion, continuity, provider provenance, verified exchange-closure declarations, exclusions, deterministic segment boundaries, immutable replay, and independent verification properties.

All strategy decisions are indexed to completed canonical 1h candles.

### 4.4 Deterministic 4h derivation

Each 4h context bar is derived only from four consecutive, valid, completed 1h bars aligned to UTC 4-hour boundaries. For a bar covering `[T, T+4h)` where `T.hour mod 4 == 0`:

- open = first 1h open;
- high = maximum constituent high;
- low = minimum constituent low;
- close = final constituent close;
- volume = exact sum of constituent volume;
- the bar is valid only if all four expected 1h slots are present, valid, completed, and belong to one verified continuous segment.

A partial 4h bar, a bar spanning a protected segment boundary, or a bar with a missing/invalid constituent is not a valid context bar.

Independently fetched public Binance 4h bars may be used as an integrity cross-check. They may not silently replace, repair, or modify the canonical derived context series.

### 4.5 Strict as-of join

For every 1h decision row, the available 4h context is the latest valid 4h bar whose close time is less than or equal to the 1h decision timestamp.

Example:

```text
00:00-01:00  1h
01:00-02:00  1h
02:00-03:00  1h
03:00-04:00  1h   -> 4h bar [00:00,04:00) becomes available at 04:00
```

A decision at `04:00` may use that context. A decision before `04:00` may not.

Every joined row must persist both the tactical decision timestamp and the exact 4h context-bar identity used. No future-completed 4h bar, partial current 4h bar, interpolation, backward fill, or later-context substitution is permitted.

## 5. Candidate identity and model-family freeze

```text
strategy_id    = candidate.multi_model.v0_4
policy_version = candidate-multi-model-v0.4
policy_schema  = candidate-strategy-policy-v4
```

Candidates v0.1-v0.3 remain independently replayable and immutable.

v0.4 retains the existing specialist model families to isolate the multi-timeframe hypothesis.

### 5.1 Trend specialist

The trend specialist remains scikit-learn 1.9.0 elastic-net logistic regression with:

- fold-local standardization;
- penalty `elasticnet`;
- solver `saga`;
- `C = 1.0`;
- `l1_ratio = 0.5`;
- fixed seed `1701`;
- deterministic single-thread execution;
- inverse-frequency class weights only when training positive fraction is outside `[0.30, 0.70]`;
- tolerance `1e-7`;
- maximum iterations `50,000`;
- convergence required strictly before the iteration ceiling;
- portable non-executable artifact serialization and custom-inference agreement retained.

### 5.2 Mean-reversion specialist

The mean-reversion specialist remains deterministic scikit-learn gradient-boosted decision trees with:

- logistic classification loss;
- 150 estimators;
- maximum depth 2;
- learning rate `0.03`;
- minimum leaf size 100;
- no row subsampling;
- no feature subsampling;
- fixed seed `1702`;
- deterministic single-thread execution;
- fold-local standardization;
- no hyperparameter search;
- portable non-executable artifact serialization and custom-inference agreement retained.

No neural network, transformer, random forest, XGBoost/LightGBM/CatBoost substitution, AutoML search, reinforcement learning, stacking search, or model-family competition is permitted in v0.4. A model-family redesign is a later candidate.

## 6. Feature architecture

### 6.1 General rules

Every feature must be deterministic, finite, point-in-time, trailing-only, reproducible offline from verified evidence, and available by the 1h decision timestamp. Learned normalization statistics are fold-local.

No centered windows, future extrema, full-sample normalization, future labels, future context, random imputation, or post-cutoff data are permitted.

### 6.2 1h tactical feature registry

The existing economic feature families are re-instantiated on completed 1h candles with a maximum tactical dependency of 42 completed 1h bars.

#### Trend specialist tactical features

- log returns over 1, 2, 3, 6, 12, 24, and 42 hours;
- positive-return fraction over 6, 12, 24, and 42 hours;
- 3-hour return minus the preceding 3-hour return;
- distance from trailing 12- and 42-hour highs and lows;
- EMA 6, 12, 24, and 42 distances from close;
- EMA 6/24, 12/42, and 24/42 normalized spreads;
- EMA slopes over 3 and 6 hours;
- same-sign return fraction over 6, 12, and 24 hours;
- realized volatility over 6, 12, 24, and 42 hours;
- ATR over 6, 12, and 24 hours;
- current true range divided by trailing ATR 24;
- log volume change over 1, 3, 6, and 12 hours;
- volume divided by trailing 12-, 24-, and 42-hour median volume;
- volume z-score over 24 and 42 hours;
- return sign multiplied by normalized volume;
- candle range multiplied by normalized volume.

#### Mean-reversion specialist tactical features

- close z-score over 12, 24, and 42 hours;
- close distance from trailing 12-, 24-, and 42-hour median normalized by ATR 24;
- drawdown from trailing 12-, 24-, and 42-hour highs;
- rebound from trailing 12-, 24-, and 42-hour lows;
- candle body/range, upper-wick/range, lower-wick/range, and close location;
- close location within trailing 12- and 24-hour ranges;
- realized volatility over 6, 12, 24, and 42 hours;
- ATR over 6, 12, and 24 hours;
- current true range divided by trailing ATR 24;
- the same volume transformations listed for the trend specialist.

No RSI, MACD, Bollinger-band expansion, arbitrary technical-indicator library, automated feature generation, post-result feature pruning, or performance-driven feature search is permitted.

### 6.3 Compact six-variable 4h numeric context

Each eligible specialist receives exactly the following six numeric features from the latest fully completed valid 4h context bar:

1. signed `(EMA_12 - EMA_42) / ATR_24`;
2. `realized_volatility_6 / realized_volatility_42`;
3. current true range / `ATR_24`;
4. close location within trailing 24-bar 4h range;
5. close distance from trailing 24-bar 4h median / `ATR_24`;
6. 3-bar slope of 4h `EMA_12` / `ATR_24`.

The full 4h feature registry is not supplied to the tactical learners.

The categorical regime state is not an ML feature. It is a deterministic ownership gate.

### 6.4 Feature isolation

- trend specialist: trend/momentum/return/volatility/volume tactical features + exactly six 4h context values;
- mean-reversion specialist: mean-reversion/candle/volatility/volume tactical features + exactly six 4h context values;
- regime classifier: deterministic 4h descriptors only.

This prevents the tactical specialists from becoming unrestricted duplicate regime learners.

## 7. Deterministic 4h regime layer

The 4h regime classifier remains deterministic and not fitted to profit labels.

```text
trend_strength   = abs(EMA_12 - EMA_42) / ATR_24
volatility_ratio = realized_volatility_6 / realized_volatility_42
```

Evaluate states in this order:

1. `UNSTABLE`: `volatility_ratio >= 1.75` or current true-range/ATR-24 ratio `>= 2.5`;
2. `TRENDING`: `trend_strength >= 1.0`, `volatility_ratio < 1.5`, and EMA 12/42 spread sign unchanged for three completed 4h bars;
3. `RANGING`: `trend_strength <= 0.5` and `volatility_ratio <= 1.25`;
4. `INDETERMINATE`: otherwise.

`UNSTABLE` therefore has precedence over all other states.

Every 1h decision persists its owning 4h regime observation and exact underlying context identity.

## 8. Regime-matched specialist domains

v0.4 deliberately matches specialist fitting and calibration populations to the environments in which each specialist may act.

### 8.1 Trend domain

Trend-specialist training, calibration, percentile construction, expected-return mapping, and entry prediction use only valid tactical rows whose latest completed 4h regime is `TRENDING`.

### 8.2 Mean-reversion domain

Mean-reversion training, calibration, percentile construction, expected-return mapping, and entry prediction use only valid tactical rows whose latest completed 4h regime is `RANGING` and for which at least one tactical stretch condition is true:

```text
1h close_zscore_24 <= -0.75
OR
1h drawdown_from_high_24 >= 0.02
```

The numerical prerequisite is retained but now represents a 24-hour tactical window rather than a 24x4h window.

### 8.3 Abstention domains

`UNSTABLE` and `INDETERMINATE` permit no new position.

The non-owning specialist may be computed only for diagnostics where technically useful. It cannot approve, veto, resize, hand off, or modify an entry.

## 9. Labels, calibration, and expected-return mapping

### 9.1 Economic horizon

The primary economic horizon remains 12 hours.

For a 1h decision after completed tactical candle `t`:

- hypothetical label entry uses official simulator market execution on the next 1h candle;
- the label evaluates the 12-hour held path under the locked next-candle timing contract;
- the label exit occurs after the twelfth held 1h candle under the same deterministic timing convention;
- costs, spread, slippage, precision, minimum-order, latency, and liquidity assumptions are derived from the locked simulator configuration.

Changing the observation frequency does not weaken or shorten the economic target.

### 9.2 Cost-aware positive class

The positive-class hurdle remains:

```text
full modeled round-trip market execution cost + 10 basis points
```

With the currently accepted base assumptions, the implementation derives the exact hurdle from simulator policy; it is not hard-coded independently from execution economics.

A label is positive only when the hypothetical 12-hour gross return strictly exceeds that hurdle.

### 9.3 Platt calibration

Each specialist retains deterministic logistic Platt calibration fitted only on that fold's regime-matched calibration population.

Each mandatory specialist calibration population requires at least:

```text
800 eligible observations
160 positive labels
160 negative labels
```

These are minimum evidence requirements, not optimization targets. If a complete, valid fold lacks the required population because the frozen specialist domain is too sparse, that is a substantive v0.4 qualification failure (`REJECTED`), not an infrastructure `INCONCLUSIVE`.

Persist Brier score, log loss, ten-bin expected calibration error, class counts, temporal span, row identities, and canonical calibration artifact bytes.

### 9.4 Calibration-only expected-return mapping

Retain the existing deterministic expected-gross-return mapping concept. For each specialist and fold:

1. obtain calibrated probabilities only on that specialist's regime-matched calibration rows;
2. pair those probabilities with the corresponding realized 12-hour gross label returns;
3. fit the existing deterministic expected-return mapping using calibration data only;
4. freeze the mapping before the development-test interval;
5. persist and independently replay the mapping artifact.

No development-test outcome may fit or alter this map.

### 9.5 Fold-local q75 selectivity

For each specialist and fold, construct the primary entry threshold exclusively from that specialist's eligible calibration scores:

- require at least 160 eligible scores;
- sort calibrated probabilities deterministically;
- compute empirical q75 using deterministic linear interpolation;
- effective threshold = `max(q75, 0.50)`;
- persist eligible-row identity, score-vector identity, observation count, quantile method, raw q75, effective threshold, and canonical bytes.

The primary percentile is globally frozen at 75%. No adaptive percentile selection, cross-fold borrowing, global fallback, or threshold relaxation is allowed.

## 10. Walk-forward chronology

Use the following calendar contract:

```text
initial training:     24 calendar months
calibration:           6 calendar months
development test:      6 calendar months
step:                  6 calendar months
training mode:         expanding
primary clock:         1h
context clock:         4h
label horizon:         12h
purge:                 12h
embargo:               12h
```

Every complete fold available through the fixed development cutoff is mandatory. No complete fold may be omitted because of invalid calibration, poor economics, low activity, or failed controls.

The exact fold count must be derived deterministically from the verified v0.4 Stage 1 dataset and persisted before qualification scoring.

Training labels may not cross into calibration; calibration labels may not cross into development test; no label may cross a protected market-data segment boundary. The 12-hour overlapping-label structure must be explicitly represented in evidence rather than treated as independent hourly observations.

## 11. Deterministic arbitration

### 11.1 Permitted outputs

The candidate may emit only:

- enter long;
- remain long;
- exit to cash;
- remain in cash.

Exactly one long position may exist. No pyramiding, averaging down, martingale, discretionary scaling, or simultaneous specialist positions are permitted.

### 11.2 Entry ownership

At each completed 1h decision:

- `TRENDING` -> only the trend specialist is eligible;
- `RANGING` + tactical stretch -> only the mean-reversion specialist is eligible;
- `UNSTABLE` or `INDETERMINATE` -> no new position.

A new long entry requires all of the following:

1. a valid regime-owned specialist row;
2. active calibrated probability `>=` the fold-local effective q75 threshold;
3. calibration-derived active expected gross return strictly greater than the full modeled round-trip cost hurdle plus the locked 10-bps excess-edge requirement;
4. valid chronology and context as-of relationship;
5. no cooldown violation;
6. simulator-controlled position, precision, minimum-order, liquidity, and available-cash constraints.

There is no cross-specialist voting requirement. Companion probability and disagreement may be persisted as diagnostics but cannot approve or veto a v0.4 entry.

### 11.3 Next-1h execution

A signal generated after a completed 1h candle may execute no earlier than the next 1h candle under the official deterministic simulator timing. No same-candle fill is permitted.

### 11.4 Fixed position ownership

A position's owning specialist is fixed at entry and persisted for the entire trade. A trend-owned trade never becomes mean-reversion-owned, and vice versa.

Each trade must preserve:

- entry regime;
- owning specialist;
- 1h feature identity;
- exact 4h context identity;
- calibrated probability;
- q75 threshold;
- expected-gross-return evidence;
- cost hurdle;
- entry reason;
- exit reason.

### 11.5 Hold and exit

Base probability semantics remain:

```text
hold probability floor = 0.50
model exit threshold   = 0.45
```

The owning specialist is rescored on compatible tactical rows. When the 4h regime becomes incompatible with ownership, the deterministic regime-exit timer governs and the position is not handed to another specialist.

Exit at the next permitted 1h execution when any applicable condition is met:

- owning specialist probability `<= 0.45` and ordinary minimum-hold conditions permit;
- regime becomes `UNSTABLE` (hard risk exit; minimum hold does not block);
- the regime is incompatible with ownership for two consecutive completed 4h context observations;
- `INDETERMINATE` persists beyond one completed 4h context observation;
- protection is breached;
- maximum hold reaches 72 hours.

No position may cross a verified segment boundary. Existing latency-aware forced-cash boundary semantics remain mandatory.

## 12. Risk and protection

Preserve real-time risk durations rather than raw v0.3 candle counts:

```text
minimum ordinary hold: 8 hours
maximum hold:          72 hours
cooldown after exit:    8 hours
```

Protection is evaluated on the tactical 1h execution series:

- initial stop = entry price minus `2.5 * 1h ATR_24` measured at the entry decision;
- trailing stop = highest completed 1h close since entry minus `3.0 * 1h ATR_24`, never lower than its prior level;
- breach detection uses completed 1h evidence and exits no earlier than the next permitted 1h execution;
- protection and `UNSTABLE` exits may override the ordinary 8-hour minimum hold.

The 4h ATR remains context only and does not directly set tactical stop levels.

For normalized research comparison, one long position may target the maximum affordable notional up to 100% of marked equity after reserving simulator-estimated entry costs. This is a research normalization convention, not future real-capital sizing authority.

## 13. Baselines

All baselines use the exact same canonical 1h dataset, segment boundaries, next-candle timing, costs, precision, liquidity, and accounting as v0.4.

The existing baseline family is retained and translated to the 1h tactical clock:

1. `cash.v1`: remain in cash;
2. `buy_hold.v1`: enter at the first eligible next-1h execution and hold through the comparison interval;
3. `ema_20_50.v1`: long when completed 1h EMA20 is above EMA50, otherwise cash;
4. `donchian_20_10.v1`: enter on completed-1h 20-bar high breakout, exit on completed-1h 10-bar low breakout;
5. `mean_reversion_z24.v1`: enter when completed-1h z-score24 `<= -1.5`, exit at zero or common protection.

The strongest active simple baseline for each mandatory comparison is chosen by the same preregistered baseline-selection rule used by the existing qualification framework. No post-result custom baseline may be added or removed to alter v0.4's conclusion.

## 14. Mandatory development qualification

### 14.1 Integrity and deterministic evidence

All must pass:

- exact source/dataset/policy/split identity;
- canonical 1h evidence verification;
- deterministic 4h derivation verification;
- independent 4h cross-check evidence where available;
- exact as-of join verification;
- no partial/future 4h usage;
- point-in-time feature verification;
- label alignment and 12-hour boundary protection;
- purge/embargo verification;
- verified segment-boundary cash semantics;
- complete fold inventory;
- trend convergence before 50,000 iterations;
- deterministic repeated fitting and inference;
- portable inference agreement;
- calibration and expected-return-map replay;
- percentile replay;
- provider-free qualification replay;
- independent verification;
- immutable evidence identities and inventory root.

Any economic result obtained with invalid integrity evidence is non-qualifiable.

### 14.2 Development stability

Using only non-overlapping development-test intervals:

- at least 60% of complete folds have positive candidate net return;
- at least 60% beat the strongest active simple baseline on return-to-drawdown where defined;
- at least 60 completed development-test trades occur in aggregate;
- no fold contributes more than 50% of summed positive development profit.

Undefined mandatory ratios fail closed.

### 14.3 Opportunity-density diagnostics

Every fold must persist a deterministic decision funnel:

```text
eligible 1h tactical rows
valid 4h context rows
regime-owned rows
specialist scored rows
q75 passes
expected-edge passes
risk/cooldown passes
actual entries
```

Every rejected opportunity receives a deterministic reason code. These diagnostics are forensic evidence only and are not optimization targets or qualification thresholds beyond the explicit aggregate minimum of 60 completed trades.

### 14.4 Negative and component controls

Mandatory controls include:

- shuffled labels using the existing fixed shuffled-label seed; shuffled-label evidence must not pass primary economic qualification;
- extra-delayed tactical/context features; delay must not improve return-to-drawdown by more than the existing 5% tolerance versus primary evidence;
- no-volume ablation; removing volume must not improve return-to-drawdown by at least 10% while drawdown is no higher;
- no-protection ablation; removing protection must not improve return-to-drawdown by at least 10% while maximum drawdown is reduced;
- no-percentile-selectivity ablation; replace q75 with the unchanged 0.50 probability floor while all other rules remain fixed; it must not improve return-to-drawdown by at least 10% while maximum drawdown is no higher;
- **no-4h-numeric-context ablation**; remove the six numeric 4h context values while retaining the 4h regime ownership gate and all 1h tactical features. This ablation must not improve return-to-drawdown by at least 10% while maximum drawdown is no higher than primary v0.4.

The no-4h-context ablation directly tests whether the compact slow-context vector adds economic value rather than merely increasing model capacity.

### 14.5 Cost robustness

Retain the existing hostile development thresholds:

- 1.5x modeled costs: net return > 0 and maximum drawdown <= 27.5%;
- 2x modeled costs: net return >= -5% and maximum drawdown <= 30%;
- increasing transaction costs may not improve aggregate net return.

The higher 1h decision frequency does not justify optimistic cost assumptions.

### 14.6 Sensitivity neighborhood

Freeze ten one-dimensional variants around the primary v0.4 policy:

- entry percentile: q70, q80;
- exit probability: 0.42, 0.48;
- maximum hold: 48h, 96h;
- initial stop: 2.0 ATR, 3.0 ATR;
- cooldown: 4h, 12h.

All other rules remain identical for each variant. Each percentile variant uses calibration-only deterministic quantile construction.

Required robustness:

- at least 7/10 variants have positive aggregate net return;
- median variant net return > 0;
- no variant aggregate maximum drawdown > 35%;
- the existing primary-stability rule remains mandatory.

### 14.7 Development uncertainty

Use deterministic paired moving-block bootstrap on concatenated primary development-test returns versus the strongest active simple baseline:

```text
replicates:    1000
block length:  168 x 1h candles
seed:          1788
```

The 168-hour block preserves the temporal dependency horizon previously represented by 42x4h rather than incorrectly shrinking it to 42 hours.

Mandatory thresholds:

- median paired net-return difference > 0;
- 90% lower bound > -2 percentage points.

Persist the exact sampled-start matrix identity and deterministic bootstrap artifact.

## 15. Qualification result semantics

### `QUALIFIED`

Every mandatory requirement passes on complete valid evidence. This permits only creation of a prospective-final seal. It does not establish future profitability and does not authorize execution.

### `REJECTED`

Complete valid evidence exists and at least one mandatory requirement fails. This is terminal for v0.4.

Substantive failures include, among others, insufficient regime-matched training/calibration population on otherwise valid data, economic gate failures, insufficient trades, cost failures, control failures, sensitivity failures, or bootstrap failures.

No v0.4 rerun, retuning, gate relaxation, threshold change, cutoff extension, label change, feature change, model change, or rescue analysis may seek a better outcome. Any financial redesign becomes Candidate v0.5.

### `INCONCLUSIVE`

Evidence is missing, corrupted, interrupted, invalid, ambiguous, or generated through a defective measurement/infrastructure path. Only evidence/infrastructure correction is permitted. Financial policy may not change under an `INCONCLUSIVE` repair.

## 16. Prospective-final policy

A prospective seal may be created only after:

1. this written specification is explicitly reviewed and approved;
2. a detailed implementation plan is reviewed;
3. implementation is protected-merged;
4. exact merged-main CI passes;
5. a fresh exact-source v0.4 Stage 1 1h dataset is independently verified;
6. complete development qualification passes;
7. the exact qualification artifact is provider-free replayed and independently verified;
8. the result is `QUALIFIED`.

The prospective final begins at the first UTC calendar-month boundary strictly after successful frozen-source qualification verification and ends exactly 18 calendar months later.

All data from the development cutoff through the prospective start is a quarantined bridge interval and participates in neither v0.4 development nor final performance evaluation.

During the prospective era, infrastructure may verify raw ingestion health, continuity, completion, and integrity. Strategy predictions, decisions, P&L, promotion metrics, or interim performance summaries may not be materialized for operator decision-making before the full 18-month window closes.

After the final window closes and data integrity is verified, one frozen final evaluation is permitted.

## 17. Post-prospective boundary

Even a successful prospective final does not authorize immediate capital deployment. Any later paper/demo execution, execution-quality study, operational-risk validation, or real-capital phase requires a separate design and explicit operator authorization.

A possible later progression is:

```text
v0.4 development QUALIFIED
-> 18-month prospective final PASS
-> separately authorized frozen paper/demo study
-> execution-quality and operational-risk validation
-> separately authorized small-capital research phase
```

No stage is automatic.

## 18. Fail-closed behavior

Fail closed on:

- source/dataset/policy/split/artifact mismatch;
- invalid or incomplete canonical 1h evidence;
- invalid 4h derivation;
- partial/future/stale 4h context;
- incorrect as-of joins;
- non-finite features, scores, probabilities, quantiles, or expected returns;
- label leakage or boundary crossing;
- convergence or deterministic-repeat mismatch;
- insufficient mandatory calibration population;
- percentile replay mismatch;
- expected-return-map replay mismatch;
- missing mandatory fold/control/cost/sensitivity/bootstrap evidence;
- provider-free replay mismatch;
- independent verification mismatch;
- interrupted qualification without exact immutable resumability.

No global threshold fallback, cross-fold calibration borrowing, context interpolation, model substitution, dynamic relaxation, or performance-selected rescue is allowed.

## 19. Implementation and testing boundary

Implementation scope is limited to the minimum v0.4-specific data, feature, model-domain, arbitration, qualification, replay, and workflow changes required by this design. v0.1-v0.3 behavior must remain independently replay-compatible.

Required TDD coverage must include at least:

- deterministic 1h canonical Stage 1 acceptance;
- exact 1h-to-4h aggregation and UTC alignment;
- missing constituent and segment-boundary 4h rejection;
- strict as-of joins and partial-4h look-ahead prevention;
- exact six-variable 4h context vector;
- 1h specialist feature registries;
- regime-matched trend training/calibration;
- regime-and-stretch-matched mean-reversion training/calibration;
- 800/160/160 calibration minimums;
- 160-score q75 minimum and exact quantile replay;
- 12-hour labels, 12-hour purge, and 12-hour embargo;
- calibration-only expected-return mapping;
- next-1h execution;
- 8h/72h/8h real-time risk translation;
- fixed position ownership and no specialist handoff;
- `UNSTABLE`, incompatible-regime, and indeterminate exits;
- 1h ATR stop/trailing-stop semantics;
- decision-funnel diagnostics and reason codes;
- no-4h-context ablation;
- cost/sensitivity/bootstrap translation;
- latency-aware segment-boundary forced-cash behavior;
- repeated-fit/artifact/inference determinism;
- provider-free replay and independent verification;
- v0.1-v0.3 regression compatibility;
- workflow acceptance and exact-source identity enforcement;
- full repository tests, typecheck, lint/format, build/package, dependency audit, tracked-policy, secret, and security checks before merge.

No unrelated refactoring is authorized.

## 20. No-rescue freeze

After explicit operator approval of this written specification, observed v0.4 evidence may evaluate but may not change:

- BTCUSDT Spot long/cash scope;
- 1h tactical and 4h context clocks;
- fixed development cutoff;
- deterministic 4h derivation/as-of rules;
- tactical feature registries;
- six-variable 4h context vector;
- regime classifier thresholds;
- regime-matched specialist domains;
- 12-hour label and cost hurdle;
- specialist model families and parameters;
- Platt calibration and expected-return mapping;
- calibration minimums;
- q75 construction and 0.50 floor;
- entry/hold/exit arbitration;
- 8h/72h/8h risk durations;
- 2.5/3.0 ATR protection;
- simulator economics;
- walk-forward structure;
- baselines;
- controls and ablations;
- cost-stress gates;
- sensitivity neighborhood;
- bootstrap contract;
- qualification semantics;
- prospective-final policy.

Failure is evidence, not a request to tune. Any substantive redesign after observed v0.4 development evidence becomes Candidate v0.5.

`future_profitability_not_established = true`  
`prospective_final_accessed = false`  
`execution_authorized = false`  
`research_only = true`
