# Candidate Multi-Model Strategy v0.1 Final Verification

## Milestone status

- Milestone: Candidate Multi-Model Strategy v0.1 implementation
- Boundary: `RESEARCH_ONLY`
- Pull request: #20
- Approved design/plan base: `21fb5cd07702c76c522d3e82f740ec7c320e51f7`
- Verified clean implementation head before this report: `465b6f1efc547c73cce360c88e811d97cbb25349`
- Ordinary CI on that head: run `30083561600` — passed
- Dependency-lock SHA-256: `e72fcb7f84e3ebee85d01953539ff0449b00e8b2cc6b57d0c22660ffbf8075da`
- Complete collected test count at acceptance checkpoint: 442
- Real seven-year historical Candidate run: **not performed**
- Profitability or durable edge: **not established**
- Paper, demo, live, or real-capital authorization: **not granted**

## Deterministic diagnostic acceptance

- Acceptance workflow run: `30083215682`
- Feature-head SHA associated with the workflow: `19b224ac6dcf396192db46929986a58e6c1f919b`
- Pull-request merge checkout observed inside the workflow: `8436ce6b65cceb2d3648e50eb0199cd4c6f8ad92`
- Focused acceptance execution 1: 2 passed
- Focused acceptance execution 2: 2 passed
- Exact receipt comparison: byte-identical; diff empty
- Study ID: `511749dfe6f008c94fd5989dcb4c3855b1f0f9270cad0c6f156549ba4b29d9ba`
- Study result ID: `5e4eb02af9fee6726504f9bbba6c8e307d9cdcd9fae58d099b8c7119f84e31b6`
- Classification: `INCONCLUSIVE`
- CLI promotable value: `false`
- Tamper rejection: `true`

The synthetic dataset is intentionally shorter than the seven-year promotion requirement. It exercises the complete architecture and must remain non-promotable. Its `INCONCLUSIVE` classification is therefore the required safe result, not evidence of trading edge.

## Replay and independent verification receipt

- `artifact_hashes_verified`
- `closed_reconstruction_registry_verified`
- `code_commit_verified`
- `final_test_receipt_verified`
- `mandatory_gates_verified`
- `referenced_experiments_verified`
- `replay_equivalent`
- `study_identity_verified`
- `study_result_identity_verified`

Replay and verification used immutable local evidence. Provider and network construction were denied during acceptance. A deliberately modified artifact was rejected with a safe failure and no traceback.

## Canonical artifact hashes

| Artifact | SHA-256 |
|---|---|
| `ablations.json` | `3c4fa9e7e33cbb601874ad23aa85db707377d35efae9ca3012b148f1920416c3` |
| `arbitration-decisions.jsonl` | `07c52d159a76316e498197072b086960aaacda1b370a161af2921f89b0e10093` |
| `baselines.json` | `0727577f5b2908ef5e7aaf2043d4d43c3d4c450305ca2e4c57f7d1d33cd352cd` |
| `bootstrap.json` | `4a4458743ae4e7b197c485bc227684e436ed6c1284967eba055df6017a423450` |
| `calibration.jsonl` | `aba09497d42127d8cc12979e414faed52f533f44048d32434fa9cb87dff190d9` |
| `cost-stress.json` | `52949c6d86dc24105c3ee2b8d1261068dfc7985f686dba861dd1d83eed2ddaca` |
| `experiments.jsonl` | `d7dc234f336d486059eef53b9db33355872ec37100411f2e39220236a9570140` |
| `feature-matrix.jsonl` | `01040593f500bc1554af989824a207148e32f78eb6ee7e61c3b9159a025e138e` |
| `feature-registry.json` | `b77507414e600720d863bd711119b1768498a70360b737061fd8fe390b850ff5` |
| `folds.jsonl` | `80387bd51940e48fec1ce467c6c9a837a8d82ce17b68a32b7916835d331b0d55` |
| `labels.jsonl` | `09fdb6710400884498ace97a6007074298130d173f5e4d286c248f9e5eeb8597` |
| `limitations.json` | `46551569ae6e10adc8f03ab05bb5635fd1eb4d7b2bb348880b0b153c6143e5a8` |
| `models.jsonl` | `34518e5f93b54d7ff3d258e1ebbb2d689081ffbbc7e0909c8ffe4e473ef12828` |
| `negative-controls.json` | `0115ec79e4349c64d92aa1f448c9192ec7ddb7d1acb9bb275e96b0d4e1d95954` |
| `parameter-sensitivity.json` | `07e31561d95acd6d3032f935569ebadc3be989c05873bb6d5808fe77fffae2c1` |
| `policy.json` | `ef0b62904503d3f6d273ef767fdc00a4898ffa837d550ba692e40785016b1bd1` |
| `predictions.jsonl` | `abd10e160f799e33eda4ed88a2ad8212568b058fbb0790282d0285db24c56778` |
| `promotion-gates.json` | `c1042724d7eed8f0b5998acd3e19b719803697f9e234aaecf7ec85a338a22686` |
| `regimes.jsonl` | `06e38cbd114786160f61d5a9c802a821dac3e5d4fe3b8fa334bb56c79a61058e` |
| `split-plan.json` | `380b7fe212f2a6567693b4e055e0e55e630840d9f0b88e10f13985cfc3278819` |
| `study-manifest.json` | `7bf5ee4bead55bc4c72e6292f896d681b977fa20d1b6325d28fc55073dfb6604` |
| `study-result-manifest.json` | `8861f13cf1bb053fe441df1c39c1f83d282bb66c2b639f01949fd03e3a63da48` |

## Mandatory promotion gates

Observed status totals: **11 pass**, **14 fail**, **7 not evaluated**.

| Gate | Status | Observed | Required | Evidence reason |
|---|---|---:|---:|---|
| `development.fold_count` | **FAIL** | `1` | `>=5` | development fold count evaluated |
| `development.positive_return_folds` | **FAIL** | `0` | `>=0.60` | positive-return development-fold fraction evaluated |
| `development.baseline_rtd_folds` | **NOT_EVALUATED** | `missing` | `>=0.60` | missing development return-to-drawdown comparator |
| `development.profit_concentration` | **FAIL** | `1` | `<=0.50` | development profit concentration evaluated |
| `development.trade_count` | **FAIL** | `0` | `>=60` | development completed-trade count evaluated |
| `final.net_return` | **FAIL** | `0.00` | `>0` | final net return evaluated |
| `final.trade_count` | **FAIL** | `0` | `>=30` | final trade count evaluated |
| `final.absolute_drawdown` | **PASS** | `0.00` | `<=0.25` | final absolute drawdown evaluated |
| `final.relative_drawdown` | **PASS** | `0.00` | `<=0.80*buy_hold` | final drawdown relative to buy-and-hold evaluated |
| `final.return_to_drawdown` | **NOT_EVALUATED** | `missing` | `>=0.50` | missing candidate return-to-drawdown |
| `final.simple_baseline_rtd` | **NOT_EVALUATED** | `missing` | `>=1.10x` | missing simple baseline return-to-drawdown comparator |
| `final.specialist_rtd` | **NOT_EVALUATED** | `missing` | `>=1.05x` | missing specialist return-to-drawdown comparator |
| `final.simple_baseline_net_return` | **FAIL** | `0.00` | `>=strongest simple baseline-0.02` | final simple-baseline net-return comparison evaluated |
| `final.trade_concentration` | **NOT_EVALUATED** | `missing` | `<=0.25` | missing positive-trade concentration |
| `final.regime_nonnegative` | **PASS** | `4` | `>=2` | non-negative required regimes evaluated |
| `final.regime_loss` | **NOT_EVALUATED** | `missing` | `>=-0.25*positive_profit` | missing aggregate positive profit |
| `cost.one_half_return` | **FAIL** | `0.00` | `>0` | 1.5x cost return evaluated |
| `cost.one_half_drawdown` | **PASS** | `0.00` | `<=0.275` | 1.5x cost drawdown evaluated |
| `cost.double_return` | **PASS** | `0.00` | `>=-0.05` | 2x cost return evaluated |
| `cost.double_drawdown` | **PASS** | `0.00` | `<=0.30` | 2x cost drawdown evaluated |
| `cost.monotonicity` | **PASS** | `0.00,0.00,0.00` | `base>=1.5x>=2x` | cost monotonicity evaluated |
| `sensitivity.positive_neighbors` | **FAIL** | `0` | `>=7/10` | positive neighboring variants evaluated |
| `sensitivity.median_return` | **FAIL** | `0.00` | `>0` | neighbor median return evaluated |
| `sensitivity.drawdown` | **PASS** | `0.00` | `<=0.35` | neighbor drawdown evaluated |
| `sensitivity.primary_stability` | **PASS** | `0.00` | `no >100% neighbor improvement when primary<=0.02` | primary sensitivity stability evaluated |
| `uncertainty.bootstrap_median` | **FAIL** | `0.0` | `>0` | bootstrap median return difference evaluated |
| `uncertainty.bootstrap_lower_bound` | **PASS** | `0.0` | `>-0.02` | bootstrap 90% lower bound evaluated |
| `control.shuffled_labels` | **PASS** | `False` | `false` | shuffled-label economic gates evaluated |
| `control.delayed_features` | **NOT_EVALUATED** | `missing` | `<=1.05x primary` | missing delayed-feature comparator |
| `control.no_disagreement` | **FAIL** | `False` | `true` | disagreement component value evaluated |
| `control.no_volume` | **FAIL** | `False` | `true` | volume component value evaluated |
| `control.no_protection` | **FAIL** | `False` | `true` | protection component value evaluated |

Failed and not-evaluated gates are preserved as evidence. They are not converted into passing outcomes and they prevent any promotion claim.

## Limitations

- The diagnostic dataset did not meet the seven-year history requirement.
- Synthetic or short-history evidence is non-promotable.
- OHLCV does not establish exact intrabar path, queue priority, hidden liquidity, adverse selection, or market impact.
- The study does not establish durable profitability, future performance, capacity, or execution readiness.
- A real historical study still requires continuous independently verified BTC/USDT 4h data, at least five development folds, a sealed 18-calendar-month final test, and all mandatory controls and gates.
- Any paper, demo, live, or capital phase requires a separate written gate, independent review, newly defined failure conditions, and explicit human authorization.

## Cumulative scope review

- No credentials or private endpoints were added.
- No broker, exchange-order submission, paper brokerage, demo, or live execution path was added.
- No leverage, futures, shorting, portfolio allocation, autonomous retraining, or capital authority was added.
- Candidate evaluation consumes verified local canonical evidence and uses the deterministic research simulator.
- Replay and verification remain provider-free and fail closed on missing, malformed, tampered, incomplete, or commit-mismatched evidence.
- Temporary diagnostic workflows were removed from the clean implementation head.

## Final advisory classification

`INCONCLUSIVE` and `promotable:false`.

This milestone verifies a deterministic, reproducible, fail-closed research architecture. It does not establish economic usefulness or authorize deployment. Rejection and inconclusive outcomes remain valid and expected when required evidence is absent or gates fail.

## Remaining protected-main closure

1. Commit this report and the final documentation corrections.
2. Pass ordinary CI on the resulting exact PR head.
3. Review the cumulative PR and recorded failed/not-evaluated gates.
4. Mark PR #20 ready for review.
5. Merge only through protected `main` after approval.
6. Run purpose-built verification on the exact merged-main SHA.
7. Close Issue #16 only after merged-main verification is recorded.
