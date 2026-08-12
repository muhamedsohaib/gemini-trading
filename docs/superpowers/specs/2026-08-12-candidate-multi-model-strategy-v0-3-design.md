# Candidate Multi-Model Strategy v0.3 Design

- Status: approved design, pending written-spec review
- Date: 2026-08-12
- Design gate: GitHub Issue #69
- Promotion level: `RESEARCH_ONLY`
- Strategy identity: `candidate.multi_model.v0_3`
- Policy identity: `candidate-multi-model-v0.3`
- Implementation authorized by this document: no
- Execution or capital authority: none

## 1. Purpose

Candidate v0.3 is a separately governed successor to terminally rejected Candidate v0.2. It does not rescue, retune, rerun, or reinterpret v0.2. Its new hypothesis is narrowly structural: v0.2's decision layer was too sparse because entry required multiple simultaneous hard vetoes even though model convergence, repeated-fit determinism, calibration evidence, chronology, replay, and independent verification passed.

The v0.2 result may inform the v0.3 design because v0.3 has a new identity. Once this written specification is approved, no observed v0.3 development result may alter it.

Qualification semantics remain `QUALIFIED`, `REJECTED`, or `INCONCLUSIVE`. None authorizes paper, demo, live, production, allocation, or capital deployment.

## 2. Safety and scientific boundary

The entire milestone is `RESEARCH_ONLY`.

It does not authorize exchange credentials, private endpoints, broker connectivity, paper/demo/live orders, leverage, futures, shorting, portfolio allocation, or autonomous capital. ChatGPT-guided provenance is recorded as project history, not as evidence of predictive validity. Predictive claims require preregistered out-of-sample evidence.

## 3. Predecessor evidence and redesign boundary

Candidate v0.2 produced 3 completed trades across 12 complete development folds, all three in one fold, with 0/12 positive-return folds and approximately -25.61% aggregate primary development return. Convergence, deterministic repetition, integrity, calibration, replay, and independent verification passed. Activity, economics, robustness, sensitivity, component controls, and uncertainty failed.

Therefore v0.3 changes the decision/arbitration layer only. The following remain v0.2-equivalent unless explicitly changed below:

- BTCUSDT Spot, completed 4h candles, long/cash only;
- feature registry and three-candle label horizon;
- trend and mean-reversion model families;
- trend deterministic convergence contract;
- regime classifier;
- simulator and next-candle execution timing;
- cost model, stops, position sizing, cooldown, and risk accounting;
- purge/embargo chronology and protected segment boundaries;
- walk-forward/calibration structure;
- simple baselines;
- development/final economic gates;
- provider-free replay and independent verification.

## 4. Immutable development data

The v0.3 development dataset is fixed to:

```text
[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)
```

No candle at or after `2026-08-01T00:00:00Z` may be used for v0.3 fitting, calibration, development tests, controls, sensitivity, bootstrap, rule selection, or rescue analysis.

A fresh Stage 1 dataset/handoff must be generated from the exact merged v0.3 implementation source. No v0.2 Stage 1 artifact or approval may be reused. The canonical v4 dataset, verified exchange-closure handling, exclusions, deterministic segments, replay, provenance, and independent verification remain mandatory.

Candles from the development cutoff through any eventual prospective-final start are a quarantined bridge interval and are used for neither development qualification nor prospective-final evaluation.

## 5. Candidate identity and specialist freeze

```text
strategy_id    = candidate.multi_model.v0_3
policy_version = candidate-multi-model-v0.3
policy_schema  = candidate-strategy-policy-v3
```

Candidate v0.1 and v0.2 remain immutable and independently replayable.

The trend specialist remains scikit-learn 1.9.0 elastic-net logistic regression with fold-local standardization, `saga`, `C=1.0`, `l1_ratio=0.5`, seed `1701`, deterministic single-thread execution, the existing conditional class-weight rule, `tol=1e-7`, and `max_iter=50,000`. Existing strict convergence, artifact, repeated-fit, and portable-inference checks remain mandatory.

The mean-reversion specialist, seed `1702`, features, labels, and calibration path remain unchanged.

## 6. Regime ownership

- `TRENDING`: only the trend specialist may drive entry.
- eligible `RANGING`: only the mean-reversion specialist may drive entry, with the existing stretch prerequisite.
- `UNSTABLE`: no new position.
- `INDETERMINATE`: no new position.

The regime classifier itself is unchanged.

## 7. v0.3 arbitration redesign

### 7.1 Fold-local entry score threshold

The v0.2 fixed entry threshold `0.62` is retired for v0.3 entry decisions only.

For each fold and each active specialist, derive the entry threshold exclusively from that fold's calibration partition:

1. select calibration rows on which that specialist is regime-eligible;
2. for mean reversion, also require the existing ranging stretch prerequisite;
3. use the calibrated active-specialist probability score;
4. require at least 40 eligible calibration scores;
5. sort the scores and compute the empirical 75th percentile using deterministic linear interpolation;
6. define the effective entry threshold as `max(q75, 0.50)` where `0.50` is the unchanged hold-probability floor;
7. persist the eligible-row identity, score-vector identity, quantile method, observation count, raw q75, and effective threshold.

The primary percentile is globally frozen at `75%`. It is never selected from development-test outcomes. Fewer than 40 required eligible scores fails closed; there is no cross-fold borrowing, global fallback, adaptive percentile, or threshold relaxation.

### 7.2 Entry conditions

A new long position may be opened only when:

- regime ownership permits entry;
- active calibrated probability is at or above the fold-local effective threshold;
- active expected gross return is strictly greater than the full modeled transaction-cost hurdle plus the unchanged extra edge requirement;
- existing position-risk, stop-validity, chronology, and next-candle execution constraints pass.

The former hard entry vetoes below become diagnostics only:

- companion specialist probability floor `0.45`;
- cross-specialist disagreement limit `0.25`.

Their values remain computed and persisted, but they cannot block a primary v0.3 entry.

### 7.3 Hold, exit, cooldown, and protection

The v0.2 hold probability `0.50`, exit probability `0.45`, minimum hold `2`, maximum hold `18`, cooldown `2`, indeterminate tolerance, initial stop `2.5 ATR`, trailing stop `3.0 ATR`, and state-transition/risk semantics remain unchanged.

Each fold's percentile threshold is frozen before its development-test interval begins and never recomputed from development-test rows or while a position is open.

## 8. Walk-forward plan

Use the existing chronological contract:

- initial training 24 calendar months;
- calibration 6 calendar months;
- forward development test 6 calendar months;
- step 6 calendar months;
- purge 3 candles;
- embargo 3 candles;
- existing label-exit offset and protected segment rules;
- expanding training history;
- every complete fold available through the fixed cutoff is mandatory.

The exact fold count must be deterministically derived from the verified Stage 1 dataset and persisted. No complete fold may be omitted because of poor results.

## 9. Mandatory pre-final qualification

### 9.1 Integrity, chronology, convergence, determinism, calibration

All v0.2 requirements remain, including exact Stage 1/source/dataset identity, canonical verification, point-in-time features, label alignment, purge/embargo, segment leakage checks, complete fold inventory, trend convergence strictly before 50,000 iterations, byte-deterministic repeated fitting/inference, portable inference agreement, calibration minimums/diagnostics, provider-free replay, independent verification, and immutable artifact identities.

Additionally, every fold-local percentile artifact must independently replay to the same eligible-row identity, score vector, q75, effective threshold, and serialized bytes.

### 9.2 Development stability

Using only non-overlapping development-test intervals:

- every complete fold is present;
- at least 60% have positive candidate net return;
- at least 60% beat the strongest active simple baseline on return-to-drawdown when defined;
- no fold contributes more than 50% of summed positive development profit;
- at least 60 completed development-test trades occur in aggregate.

Undefined mandatory ratios fail closed.

### 9.3 Negative and component controls

Mandatory controls:

- shuffled labels must not pass the primary economic qualification gates;
- extra-delayed features must not improve return-to-drawdown by more than 5% versus primary evidence;
- removing volume must not improve return-to-drawdown by at least 10% while drawdown is no higher;
- removing protection must not improve return-to-drawdown by at least 10% while maximum drawdown is reduced.

The v0.2 `no-disagreement` control is obsolete because disagreement is no longer a primary veto. Replace it with:

- `no-percentile-selectivity`: use the unchanged `0.50` hold floor as the entry score threshold while leaving all other v0.3 rules unchanged;
- this ablation must not improve return-to-drawdown by at least 10% while maximum drawdown is no higher than primary v0.3.

Companion probability and disagreement distributions remain persisted diagnostics.

### 9.4 Cost robustness

Retain the v0.2 development thresholds:

- 1.5x-cost net return > 0;
- 1.5x-cost maximum drawdown <= 27.5%;
- 2x-cost net return >= -5%;
- 2x-cost maximum drawdown <= 30%;
- higher costs may not improve aggregate return.

### 9.5 Sensitivity neighborhood

Keep ten one-dimensional variants. Replace the obsolete fixed-entry pair with percentile neighbors:

- entry percentile `70%`, `80%`;
- exit probability `0.42`, `0.48`;
- maximum hold `12`, `24` candles;
- initial stop `2.0`, `3.0` ATR;
- cooldown `1`, `3` candles.

Each percentile variant uses the same calibration-only deterministic quantile construction. Required robustness remains at least 7/10 positive variants, positive median return, no aggregate drawdown above 35%, and the existing primary-stability rule.

### 9.6 Development uncertainty

Retain the deterministic paired moving-block bootstrap on concatenated primary development-test returns versus the strongest active simple baseline:

- 1,000 replicates;
- block length 42 candles unless mathematically shortened by path length;
- seed `1788`;
- median net-return difference > 0;
- 90% lower bound > -2 percentage points;
- sampled-start matrix identity persisted.

## 10. Qualification result semantics

- `QUALIFIED`: every mandatory requirement passes on complete valid evidence.
- `REJECTED`: at least one mandatory requirement explicitly fails on complete valid evidence.
- `INCONCLUSIVE`: evidence is missing, invalid, interrupted, ambiguous, or insufficient.

Only `QUALIFIED` permits creation of a prospective-final seal. It does not imply profitability and does not authorize execution.

A genuine mandatory `REJECTED` result is terminal for v0.3. The candidate may not be rerun, retuned, or relaxed to seek a better result. Any redesign after observed v0.3 evidence becomes Candidate v0.4.

## 11. Prospective-final policy

A prospective seal may exist only after the written v0.3 specification is approved and committed, the implementation plan is reviewed, implementation is protected-merged, exact merged-main CI passes, a fresh exact-source Stage 1 dataset is independently verified, complete development qualification passes, the exact qualification artifact is independently verified, and the pre-final result is `QUALIFIED`.

The prospective final begins at the first UTC calendar-month boundary strictly after successful frozen-source/pre-final verification and ends exactly 18 calendar months later.

No strategy predictions, decisions, P&L, promotion gates, or performance metrics may be materialized from prospective-final rows before the entire final window ends. Raw ingestion integrity may be monitored without generating strategy outcomes. After the final window closes and data integrity is verified, one final evaluation is permitted under the frozen identities.

## 12. Fail-closed behavior

Fail closed on insufficient eligible calibration rows, non-finite scores/quantiles, quantile replay mismatch, source/dataset/policy/split/artifact mismatch, chronology or leakage violations, convergence/determinism mismatch, missing mandatory fold/control/robustness/bootstrap evidence, or interrupted qualification without exact immutable resumability.

No fallback global threshold, cross-fold borrowing, adaptive percentile, dynamic relaxation, solver substitution, or threshold search is allowed.

## 13. Implementation and testing boundary

Implementation scope is limited to the v0.3 identity and minimum arbitration/qualification changes required by this design. v0.1 and v0.2 behavior must remain independently replay-compatible. No unrelated refactoring is authorized.

Required TDD coverage includes exact quantile construction and ties, 40-score minimum failures, calibration-only provenance, specialist/regime ownership, diagnostic-only companion/disagreement behavior, cost-edge preservation, unchanged hold/exit/risk behavior, percentile sensitivity variants, no-percentile-selectivity ablation, deterministic artifact/replay, v0.1/v0.2 regressions, workflow acceptance, and the full repository quality/type/test/build/dependency/secret/security suite before merge.

## 14. No-rescue freeze

After operator approval of this written specification, development evidence may evaluate but may not change features, labels, specialist models, regime rules, primary percentile `75%`, quantile method, 40-score minimum, companion/disagreement diagnostic-only status, expected-edge hurdle, hold/exit/cooldown/risk rules, cutoff, split structure, baselines, controls, cost gates, sensitivity gates, bootstrap gates, or qualification semantics.

Failure is evidence, not a request to tune. Any redesign is Candidate v0.4.

`future_profitability_not_established = true`  
`prospective_final_accessed = false`  
`execution_authorized = false`  
`research_only = true`
