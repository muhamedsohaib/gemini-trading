# Candidate Multi-Model Strategy v0.1 Progress Evidence

## Status

- Milestone state: implementation in progress
- Promotion boundary: `RESEARCH_ONLY`
- Pull request: #20, draft
- Approved design and plan base: `21fb5cd07702c76c522d3e82f740ec7c320e51f7`
- Completed implementation tasks: 1–11
- Current task: 12 — documentation, concrete end-to-end evaluation, final evidence, and exact verification
- Real seven-year historical Candidate run: not performed or claimed
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
- GREEN CI: `30078079673` — complete quality and security workflow passed

The concrete dataset-to-study evaluator remains deliberately fail-closed. No placeholder hashes or fabricated economic result is emitted.

## Task 12 evidence in progress

### Documentation RED

- RED head: `1b04d11c95c3516a611d4cb4bca77a826e368304`
- RED CI: `30078344627`
- Expected failure: required Candidate operations document absent

### Documentation implementation

Added:

- `docs/operations/candidate-multi-model-strategy.md`
- `docs/operations/candidate-multi-model-strategy-step-verification.md`
- Candidate section in `README.md`
- this progress report

The operations document records the research-only boundary, exact market and interval, seven-year requirement, sealed 18-month final test, CLI commands, valid rejection outcome, immutable evidence, replay/verification trust boundary, limitations, and the current fail-closed evaluator status.

## Remaining work

1. Implement the concrete dataset-to-study evaluator using the existing verified canonical dataset and research engine.
2. Add deterministic synthetic BTCUSDT H4 end-to-end acceptance.
3. Exercise features, labels, splits, model training, calibration, regimes, arbitration, comparators, experiments, immutable study artifacts, replay, verification, tamper rejection, and unsafe-mode rejection.
4. Require synthetic classification `INCONCLUSIVE` and identical repeated identities.
5. Run complete quality, security, focused acceptance, exact PR-head, independent review, protected merge, and exact merged-main verification.
6. Write `reports/verification/candidate-multi-model-strategy-final.md` with exact observed evidence.
7. Close Issue #16 only after merged-main verification.

## Safety confirmation

No credentials, private endpoints, exchange submission, broker integration, paper/demo/live execution, leverage, futures, shorting, portfolio allocation, autonomous retraining, or real-capital authority has been introduced by this milestone.
