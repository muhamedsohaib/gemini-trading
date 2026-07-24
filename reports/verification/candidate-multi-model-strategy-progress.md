# Candidate Multi-Model Strategy v0.1 Progress Evidence

## Status

- Milestone state: implementation and cumulative advisory review complete; review-ready
- Promotion boundary: `RESEARCH_ONLY`
- Pull request: #20
- Approved design and plan base: `21fb5cd07702c76c522d3e82f740ec7c320e51f7`
- Completed implementation tasks: 1–12
- Final verified PR head: `b215070d586dbd5897c796d063213806be1e4a99`
- Final PR CI: `30087869706` — passed
- Real seven-year historical Candidate run: not performed or claimed
- Diagnostic classification: `INCONCLUSIVE`
- CLI promotable value: `false`
- Profitability: not established

## Completed boundaries

### Tasks 1–3 — policy, point-in-time data, labels, and chronology

- Locked BTC/USDT completed-4h, long-or-cash policy.
- Immutable strategy contracts and fail-closed error taxonomy.
- Deterministic 42-candle point-in-time feature registry.
- Conservative three-candle cost-aware labels with next-candle entry.
- Seven-year minimum history, expanding calendar folds, purge, embargo, and sealed 18-month final test.

### Tasks 4–6 — models, arbitration, risk, and comparators

- Seeded single-thread elastic-net trend model and gradient-boosted mean-reversion model.
- Canonical non-executable model artifacts and custom inference parity.
- Fold-local Platt calibration and expected-return mapping.
- Completed-candle regime classification and deterministic arbitration.
- Long-only Candidate adapter with no pyramiding, empty-position sells, broker, provider, or network access.
- Five provider-free comparators using the shared conservative research engine.

### Tasks 7–8 — evaluation and sealed study orchestration

- Expanded deterministic economic and calibration metrics.
- Regime attribution and deterministic moving-block bootstrap.
- Mandatory development, final, cost, sensitivity, ablation, and negative-control gates.
- Required case registries, preserved failed-case evidence, final-test access denial during development, and identity-bound single-use final receipt.

### Tasks 9–10 — immutable evidence, replay, and verification

- Exact 22-file canonical strategy-study artifact contract.
- Content-derived study-result identity and immutable local storage.
- Closed seven-strategy replay registry.
- Provider-free replay, exact code-commit binding, referenced research-experiment verification, complete gate verification, and safe sorted check output.

### Task 11 — CLI interface and locked configuration

- Commands: `strategy-evaluate`, `strategy-replay`, and `strategy-verify`.
- Exact Candidate v0.1 configuration schema.
- Rejection of extra fields, altered identities, zero costs, same-close timing, optimistic fills, and unsafe runtime modes.
- Runtime policy is checked before configuration, dataset, provider, or model work.
- Provider-free local replay and safe verification summaries.

Evidence:

- RED head: `805550a3c30890c24706d330ba7b578bcfd79757`
- RED CI: `30076588226`
- GREEN head: `88d99e709f0c40b7f5ed2270412eeddcdb3fefab`
- Focused tests: 12 passed
- GREEN CI: `30078079673`

### Task 12 — concrete evaluator, documentation, and acceptance

- Concrete provider-free dataset-to-study evaluator implemented.
- Deterministic specialist training, calibration, regimes, arbitration, comparators, controls, cost stress, sensitivity, bootstrap, study execution, and immutable evidence generation integrated.
- Operations documentation, step-verification protocol, README entry, and end-to-end acceptance added.
- Synthetic acceptance exercises local evaluation, repeated deterministic identities, referenced-experiment replay, strategy-study replay, independent verification, tamper rejection, network denial, and unsafe-mode rejection.
- Synthetic/short history is forced to `INCONCLUSIVE` and `promotable:false`.

Evidence:

- Documentation RED head: `1b04d11c95c3516a611d4cb4bca77a826e368304`
- Documentation RED CI: `30078344627`
- Focused Task 12 acceptance: 12 passed during implementation diagnostics
- Full implementation CI: `30082950174` — passed
- Deterministic acceptance workflow: `30083215682` — two focused runs and two exact receipts passed; receipt diff empty
- Clean implementation head: `465b6f1efc547c73cce360c88e811d97cbb25349`
- Clean implementation CI: `30083561600` — passed
- Study ID: `511749dfe6f008c94fd5989dcb4c3855b1f0f9270cad0c6f156549ba4b29d9ba`
- Study result ID: `5e4eb02af9fee6726504f9bbba6c8e307d9cdcd9fae58d099b8c7119f84e31b6`
- Mandatory gates: 32 recorded — 11 pass, 14 fail, 7 not evaluated
- Complete collected tests at acceptance checkpoint: 442
- Dependency-lock SHA-256: `e72fcb7f84e3ebee85d01953539ff0449b00e8b2cc6b57d0c22660ffbf8075da`

The diagnostic result verifies deterministic architecture and fail-closed evidence handling only. It does not establish trading edge, durable profitability, paper readiness, live readiness, or capital authorization.

## Cumulative review correction

The cumulative PR review found that shuffled-label and component-ablation gate inputs were initially hardcoded in `build_promotion_report()` instead of being derived from the executed final control evidence. That would have made the component-value gates permanently fail regardless of real evidence.

The correction now derives:

- shuffled-label economic invalidation from the executed shuffled-label metrics;
- disagreement-abstention component support from primary versus no-disagreement return-to-drawdown and drawdown;
- volume component support from primary versus no-volume evidence;
- protection component support from primary versus no-protection evidence, requiring an actual drawdown reduction for the ablation to invalidate protection.

Evidence:

- Review RED head: `3221d25c4df5df84f4bc554f0c044c996fc9233e`
- Review RED CI: `30086424983` — strict Pyright failed against the intentionally absent evidence-derived helpers
- Review-corrected clean code head: `4527e2a2f520b0e15a4f245297a1c4b1bd75b3c4`
- Review GREEN CI: `30087016792` — frozen sync, Ruff format, Ruff lint, strict Pyright, complete pytest suite, package build, dependency audit, tracked-file policy, detect-secrets, and Gitleaks passed
- Final report-bearing PR head: `b215070d586dbd5897c796d063213806be1e4a99`
- Final report-bearing CI: `30087869706` — passed
- Temporary review-format workflow removed before the review GREEN CI
- Final changed-file list contains no temporary workflow

The synthetic diagnostic gate totals remain unchanged because its primary return-to-drawdown is undefined and its shuffled-label control exhibits no positive economic gate. The failure and not-evaluated evidence remains preserved.

## Remaining protected-main closure

1. Obtain review approval and merge only through protected `main`.
2. Run exact merged-main verification.
3. Close Issue #16 only after merged-main verification is recorded.

## Safety confirmation

No credentials, private endpoints, exchange submission, broker integration, paper/demo/live execution, leverage, futures, shorting, portfolio allocation, autonomous retraining, or real-capital authority has been introduced by this milestone.
