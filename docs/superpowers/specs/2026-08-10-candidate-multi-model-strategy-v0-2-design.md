# Candidate Multi-Model Strategy v0.2 Prospective Validation Design

- Status: approved for implementation
- Date: 2026-08-10
- Design gate: GitHub Issue #61
- Branch: `research/candidate-v0-2-prospective-validation`
- Promotion level: `RESEARCH_ONLY`
- Strategy identity: `candidate.multi_model.v0_2`
- Policy identity: `candidate-multi-model-v0.2`
- Implementation authorized by operator: yes
- Execution or capital authority: none

## 1. Purpose

Candidate v0.2 is the prospectively governed successor to rejected Candidate v0.1. It preserves the complete v0.1 financial hypothesis, feature set, label policy, mean-reversion specialist, regime classifier, arbitration, simulated execution economics, risk rules, baselines, controls, robustness thresholds, and long/cash scope. The only model-policy change is the trend specialist numerical convergence contract.

The purpose of v0.2 is not to rescue v0.1 retrospectively. It is to create a new frozen candidate, force that candidate through a strict development-only qualification gate, and only if it qualifies, bind it to a genuinely future 18-calendar-month final era.

Candidate v0.2 remains falsifiable. Failure is preserved as `REJECTED`; incomplete or ambiguous evidence is `INCONCLUSIVE`; successful development qualification is `QUALIFIED`, which means only that the frozen candidate may wait for its prospective final era. None of these states authorizes paper, demo, live, or real-capital trading.

## 2. Provenance and scientific claims

Candidate Multi-Model Strategy is an original project architecture developed through the operator's direction and a ChatGPT-guided design, reasoning, code-generation, testing, and verification process.

The repository must distinguish three claims:

1. **Authenticity and provenance** are established by committed design lineage, exact Git identities, content-addressed policy/data/evidence, deterministic replay, and audit receipts.
2. **Predictive validity** is established only by preregistered out-of-sample evidence and, ultimately, the untouched prospective final era.
3. **ChatGPT contribution** is documented as a core design and engineering contributor. Model performance is not represented as proof of ChatGPT's general capabilities, and ChatGPT authorship does not imply profitability.

This separation keeps the model's origin explicit while keeping its financial claims falsifiable.

## 3. Safety and non-goals

The entire v0.2 milestone is `RESEARCH_ONLY`.

It does not add or authorize:

- exchange credentials or private endpoints;
- broker, paper-broker, demo, live, or production order submission;
- leverage, margin, futures, options, or shorting;
- portfolio allocation or autonomous capital deployment;
- performance-driven model search after the v0.2 freeze;
- reinterpretation of v0.1 as successful;
- any guarantee of future profitability.

The existing deterministic simulator remains the only authority for simulated orders, fills, fees, spread, slippage, precision, liquidity participation, accounting, and metrics.

## 4. Locked market and development dataset

### 4.1 Market scope

- Provider: public Binance Spot evidence through the verified Market Data Core.
- Instrument: `BTCUSDT` / BTC-USDT spot.
- Interval: completed `4h` candles.
- Direction: long or cash only.

### 4.2 Immutable v0.2 development window

The complete v0.2 development dataset is fixed to:

```text
[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)
```

No candle at or after `2026-07-01T00:00:00Z` may be used for v0.2 fitting, calibration, development walk-forward tests, controls, sensitivity analysis, bootstrap analysis, convergence tuning, threshold selection, or rescue analysis.

The previously untouched v0.1 historical final interval `[2025-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` is retired from its v0.1 test role and may participate in v0.2 development only because that use was approved before v0.2 development evidence is observed.

A fresh Stage 1 dataset/handoff must be produced from the exact merged v0.2 implementation commit. The old v0.1 Stage 1 handoff may not be reused because its source-commit identity is different.

The canonical v4 dataset rules, raw evidence, verified exchange-closure handling, exact partial-row exclusions, deterministic continuous segments, replay, provenance, and independent verification remain mandatory.

## 5. Candidate v0.2 structural policy

All v0.1 structural values remain frozen except the explicit identity and trend convergence values below.

### 5.1 New identity

```text
strategy_id    = candidate.multi_model.v0_2
policy_version = candidate-multi-model-v0.2
policy_schema  = candidate-strategy-policy-v2
```

### 5.2 Trend specialist

The trend specialist remains binary elastic-net logistic regression with:

- fold-local standardization;
- scikit-learn `1.9.0` `LogisticRegression`;
- penalty `elasticnet`;
- solver `saga`;
- `C = 1.0`;
- `l1_ratio = 0.5`;
- fixed seed `1701`;
- deterministic single-thread execution;
- inverse-frequency class weights only when the training positive fraction is outside `[0.30, 0.70]`;
- **tolerance `1e-7`**;
- **maximum iterations `50,000`**.

Convergence passes only when the solver terminates strictly before 50,000 iterations. Reaching the ceiling, non-finite parameters, model-artifact mismatch, repeated-fit mismatch, or inference mismatch is a terminal pre-final model-determinism failure.

After v0.2 evidence exists, the iteration ceiling may not be extended, the tolerance may not be relaxed, and the solver, regularization, features, labels, thresholds, or model family may not be changed. Such a change creates Candidate v0.3.

### 5.3 Everything else remains v0.1-equivalent

The following are unchanged:

- the complete point-in-time feature registry and 42-candle maximum dependency;
- the three-candle cost-aware label horizon;
- calibration minimums of 200 observations, 40 positive labels, and 40 negative labels;
- mean-reversion specialist shape and seed `1702`;
- regime rules;
- entry `0.62`, hold `0.50`, exit `0.45`, companion floor `0.45`, disagreement limit `0.25`;
- ATR protection, hold, cooldown, abstention, and long/cash rules;
- simulator economics and precision;
- simple baselines, ablations, negative controls, cost stress, sensitivity neighborhood, and bootstrap seeds/thresholds;
- final economic promotion gates.

## 6. Development-only walk-forward plan

Candidate v0.2 does **not** reserve a historical final partition inside the locked development dataset. The entire fixed dataset is development evidence.

A dedicated development qualification split plan uses:

- initial training: 24 calendar months;
- calibration: 6 calendar months;
- forward development test: 6 calendar months;
- step: 6 calendar months;
- purge: 3 candles;
- embargo: 3 candles;
- label exit offset: 4 candle indexes under the existing next-candle/three-held-candle contract;
- every verified exchange segment boundary as a protected boundary;
- every complete fold available through the fixed development cutoff.

For the exact `[2018-01-01, 2026-07-01)` window this calendar contract yields **12 complete forward development-test folds**. All 12 are mandatory. Omitting a failed fold is prohibited.

Training expands chronologically. Calibration and development-test windows never overlap training or one another after purge/embargo. A label crossing any fold or exchange-segment boundary is excluded.

The development split-plan identity is content-addressed and becomes part of the qualification identity.

## 7. Strict pre-final qualification suite

Candidate v0.2 may receive prospective-final eligibility only after every mandatory qualification requirement below is satisfied on complete, immutable, verified development evidence.

### 7.1 Integrity and chronology

All must pass:

- exact Stage 1 handoff/source/dataset identity;
- canonical v4 dataset verification, continuity, completion, provenance, exclusions, and segment identity;
- point-in-time feature checks;
- label, normalization, alignment, split, purge/embargo, and segment leakage checks;
- exactly 12 complete development folds for the locked dataset;
- no omitted or relabeled failed experiment;
- exact provider-free replay;
- independent verification;
- immutable artifact hashes and qualification identity.

### 7.2 Trend convergence and deterministic repetition

For every fold:

- the v0.2 trend model must converge strictly before 50,000 iterations at `tol=1e-7`;
- the iteration count is persisted;
- the complete trend artifact is fitted twice from identical inputs under the same thread/seed contract;
- serialized trend artifacts must be byte-identical;
- calibration and prediction evidence derived from the repeated fit must be byte-identical;
- custom portable inference must match the library decision function under the existing numerical tolerance.

Any mismatch is `REJECTED` before prospective-final access.

### 7.3 Calibration

Every fold and specialist must satisfy the existing minimum calibration observations and class counts. Calibration artifacts, probability ranges, Brier score, log loss, and ten-bin expected calibration error are stored. Missing or insufficient calibration evidence fails closed.

### 7.4 Development stability

Using only each fold's out-of-sample development-test interval:

- 12/12 folds must be present;
- at least 60% have positive candidate net return;
- at least 60% beat the strongest active simple baseline on return-to-drawdown when defined;
- no one fold contributes more than 50% of summed positive development-fold profit;
- at least 60 completed development-test trades in aggregate.

### 7.5 Negative and component controls

The preregistered development controls remain mandatory:

- shuffled labels must not exhibit a positive economic qualification gate;
- extra-delayed features must not improve return-to-drawdown by more than 5% versus primary development evidence;
- removing disagreement abstention must not improve return-to-drawdown by at least 10% while drawdown is no higher;
- removing volume must not improve return-to-drawdown by at least 10% while drawdown is no higher;
- removing protection must not improve return-to-drawdown by at least 10% while maximum drawdown is reduced.

Undefined ratios fail closed rather than being treated as favorable.

### 7.6 Development robustness

The same predeclared cost and ten-neighbor sensitivity family is run on development-only out-of-sample evidence. Variants remain diagnostics and cannot replace the primary candidate.

Required aggregate development robustness:

- 1.5x-cost net return is positive;
- 1.5x-cost maximum drawdown is at most 27.5%;
- 2x-cost net return is at least -5%;
- 2x-cost maximum drawdown is at most 30%;
- increasing costs may not improve aggregate net return;
- at least 7 of 10 sensitivity variants have positive aggregate development net return;
- median sensitivity net return is positive;
- no sensitivity aggregate drawdown exceeds 35%;
- when primary aggregate development net return is at most 2%, no single neighbor may improve it by more than 100%.

Aggregate development returns are formed only from the non-overlapping chronological development-test windows. Drawdown is recomputed on the concatenated out-of-sample return path, not averaged across folds.

### 7.7 Development uncertainty

Use deterministic moving-block bootstrap on the concatenated primary development-test account-return path versus the strongest active simple baseline:

- 1,000 replicates;
- block length 42 candles, reduced only when the path is shorter;
- seed `1788`;
- paired resampling;
- median net-return difference must be positive;
- 90% lower bound must be above `-2` percentage points.

The sampled-start matrix identity is persisted.

## 8. Qualification result semantics

The v0.2 pre-final report uses:

- `QUALIFIED`: every mandatory pre-final requirement passed on complete verified evidence;
- `REJECTED`: at least one mandatory requirement explicitly failed on complete valid evidence;
- `INCONCLUSIVE`: evidence is missing, invalid, ambiguous, interrupted, or insufficient for a defensible result.

Only `QUALIFIED` permits creation of the prospective-final seal. It does not imply historical or future profitability and does not authorize execution.

No failed `REJECTED` v0.2 qualification may be rescued by tuning v0.2. Any redesign is v0.3.

## 9. Prospective-final window and bridge quarantine

After all of the following exist:

1. approved and committed v0.2 specification;
2. reviewed implementation plan;
3. protected merge of the v0.2 implementation;
4. exact merged-main CI verification;
5. a fresh exact-source Stage 1 v0.2 development dataset and independently verified handoff;
6. complete development-only qualification;
7. independent verification of the exact qualification artifact;
8. `QUALIFIED` classification;

create one prospective-final seal.

The final start is the first UTC calendar-month boundary **strictly after** the successful frozen-source/pre-final verification milestone. The final end is exactly 18 calendar months later.

Example only: if the qualifying milestone completes during August 2026, the prospective final window is `[2026-09-01T00:00:00Z, 2028-03-01T00:00:00Z)`.

The interval from the locked development cutoff `2026-07-01T00:00:00Z` to the prospective final start is the quarantined bridge interval. Bridge rows may not be used for model development or included in the primary final evaluation.

The seal binds:

- strategy and policy identities;
- exact merged code SHA;
- development dataset ID and handoff inventory root;
- qualification ID and artifact root;
- exact successful qualification workflow run/attempt;
- UTC qualification verification timestamp;
- development cutoff;
- bridge start/end;
- final start/end;
- 18-month duration contract.

Seal creation does not load any future-final rows.

## 10. Prospective final evaluation policy

The future final era is evaluated once after the full 18-calendar-month interval has completed and its market data has been independently verified.

The final candidate is the exact frozen v0.2 policy. No fitting, threshold selection, convergence-policy change, or rescue may use bridge or prospective-final outcomes.

The future final evaluation retains the v0.1 preregistered final economics, cost stress, sensitivity, uncertainty, component, integrity, replay, and verification gates. A complete mandatory failure is `REJECTED`; incomplete or ambiguous evidence is `INCONCLUSIVE`; a complete pass is `PASS` and permits only a proposal for a separate paper-trading design gate.

Future exchange closures, partial rows, or provider anomalies must be independently documented and content-addressed before the final dataset can be accepted. They may not be invented prospectively in this implementation.

## 11. Implementation architecture

### 11.1 Versioned policy

`CandidatePolicy.locked_v0_2()` returns a complete standalone v0.2 policy. It is derived in code from the v0.1 values only to reduce drift, then replaces the versioned identity and the two approved numerical values. Serialization includes every field.

### 11.2 Development qualification split

Add a dedicated development-only split-plan type rather than abusing `ChronologicalSplitPlan.final_test`. It owns only development folds and protected boundaries and consumes the entire locked development dataset.

### 11.3 Determinism receipt

Add a content-addressed per-fold determinism receipt storing fold number, trend iteration count, first/second trend model SHA-256, first/second prediction-bundle SHA-256, and a boolean exact-match result. A false match is an explicit failure, never a warning.

### 11.4 Qualification evaluator

Add a separate development qualification evaluator. It executes the fixed candidate, baselines, ablations, controls, cost stresses, and ten sensitivity variants on development-only windows and returns a closed `QualificationReport`.

It does not instantiate any prospective-final data provider and has no final-row selector.

### 11.5 Immutable qualification artifacts

Persist canonical non-executable qualification evidence below:

```text
data/historical-validation/v0-2-qualification/<qualification-id>/
```

Generated evidence remains untracked by Git. The canonical result includes policy/configuration/split identities, experiment references, determinism receipts, robustness/uncertainty evidence, every qualification gate, classification, artifact hashes, and limitations.

### 11.6 Prospective-final seal

Persist the operational seal separately from model evidence. The seal is created only after independent qualification verification and is immutable. Its timestamp determines the prospective calendar boundary; it does not alter the model or qualification result.

### 11.7 GitHub workflow

Add a manually dispatched `Candidate v0.2 Development Qualification` workflow with narrow identity-only inputs:

- exact source commit;
- exact fresh Stage 1 run ID;
- exact Stage 1 artifact name;
- exact dataset ID.

The workflow:

1. checks out the exact source;
2. requires the owner-authored Issue #61 dataset-approval marker for the exact identities;
3. downloads and verifies the exact Stage 1 handoff;
4. asserts the fixed v0.2 development window and dataset evidence contract;
5. executes qualification only;
6. independently verifies qualification provider-free;
7. uploads immutable qualification evidence;
8. emits no final-test access receipt and performs no final evaluation.

A separate seal step/workflow may create the prospective-final seal only from a verified `QUALIFIED` artifact.

## 12. Error handling

Fail closed on:

- incorrect strategy/policy/configuration identity;
- wrong development cutoff;
- source commit or Stage 1 handoff mismatch;
- missing/changed canonical evidence;
- point-in-time or label leakage;
- fold omission or boundary crossing;
- insufficient calibration classes;
- trend non-convergence;
- repeated-fit or prediction mismatch;
- negative-control promotion;
- robustness, uncertainty, or component gate failure;
- artifact tampering or replay mismatch;
- attempt to include bridge/future rows in development;
- attempt to seal a non-`QUALIFIED` result;
- second or changed prospective-final seal.

User-facing CLI/workflow errors remain safe and must not emit credentials, raw provider bodies, environment dumps, uncontrolled tracebacks, or absolute operator paths.

## 13. Testing and verification

### 13.1 Unit

Cover:

- exact v0.2 policy identity and convergence values;
- v0.1 identity unchanged;
- complete 12-fold development plan on the fixed calendar window;
- protected segment/purge/embargo boundaries;
- prospective month-boundary calculation and 18-month duration;
- bridge quarantine;
- determinism receipt hashing and mismatch rejection;
- qualification gate semantics and `QUALIFIED`/`REJECTED`/`INCONCLUSIVE` ordering;
- immutable artifact serialization and tamper rejection.

### 13.2 Integration

Use bounded synthetic/fixture data to prove:

- v0.2 can fit and replay deterministically under the new convergence contract;
- all development paths are final-row-free;
- qualification includes every required case and gate;
- qualification replay is provider-free;
- a rejected or inconclusive qualification cannot create a prospective seal;
- a qualified fixture can create exactly one seal without reading future rows.

Synthetic evidence is architecture evidence only and must never claim economic edge.

### 13.3 Workflow contract

Require:

- manual dispatch only;
- least-privilege permissions;
- immutable/pinned actions under repository policy;
- narrow identity-only inputs;
- Issue #61 owner approval barrier;
- no final-evaluation command;
- no private endpoint or exchange secret;
- exact source/dataset/handoff checks;
- artifact retention and independent qualification verification.

### 13.4 Repository quality gates

The implementation PR and exact merged-main SHA must pass:

```text
uv sync --all-groups --frozen
ruff format --check .
ruff check .
pyright
pytest
python -m build
pip-audit
tracked-file policy
detect-secrets
Gitleaks
```

## 14. Sequencing and freeze

Implementation proceeds through RED-first tests, minimal GREEN changes, full CI, review, protected merge, and exact-main verification.

Once this specification is committed, no performance-driven change is permitted to v0.2. Implementation defects may be corrected only when they restore this written contract; a correction that changes the financial/model contract creates a new candidate.

After a complete v0.2 qualification run has observed development evidence, the model policy is absolutely frozen. A genuine mandatory failure ends v0.2 as `REJECTED`. No solver, tolerance, iteration, regularization, feature, label, threshold, regime, arbitration, cost, or gate change may rescue it.

## 15. Completion boundary

The implementation milestone is complete when:

1. the v0.2 code, qualification workflow, documentation, and tests are merged through protected `main`;
2. exact merged-main CI passes;
3. a fresh exact-source Stage 1 development dataset is produced and independently verified;
4. one v0.2 development qualification run completes and independently verifies;
5. if and only if classification is `QUALIFIED`, one prospective-final seal is created and recorded on Issue #61.

The **financial validation project cannot reach a final predictive `PASS` before the 18-calendar-month future era has actually elapsed**. Reaching the prospective seal is therefore the maximum legitimate completion state available in 2026. This is an evidence constraint, not unfinished model implementation.
