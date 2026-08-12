# Candidate v0.2 Development Qualification — Final Report

Status: **REJECTED**  
Boundary: **RESEARCH_ONLY**

## Scope

This report records the terminal pre-final development qualification result for `candidate.multi_model.v0_2`. It is not a prospective market result and grants no paper, demo, live, production, execution, allocation, or capital authority.

Candidate v0.2 was frozen before this qualification. Under the approved Issue #61 governance, a genuine mandatory pre-final gate failure is terminal for v0.2. No post-evidence tuning or rescue is permitted; any redesign must be a separately governed Candidate v0.3.

## Frozen source and Stage 1 evidence

- Source commit: `6d0c78a33a760695e97cd330d97cb51fefdbdf46`
- Exact-main CI run: `31572606626` — success
- Stage 1 workflow: `Sealed BTCUSDT Dataset`
- Stage 1 workflow run: `31578211435` — success
- Stage 1 retrieval run ID: `6975e5b112f74e08b7c5884bc7596ec0`
- Dataset ID: `33cdaecbec6b1d90db46fde0e0ad1164b3dca2e6bd2fb858d73a1b177f6a007b`
- Stage 1 artifact ID: `9134048813`
- Stage 1 artifact name: `sealed-btcusdt-dataset-6d0c78a33a760695e97cd330d97cb51fefdbdf46-31578211435`
- Stage 1 artifact SHA-256: `62c194433bcb8c1084898b41e1ac88e87a239e320b813d20e2f40abdbb252438`
- Stage 1 handoff inventory root: `b16294161f0e3ca4d4753437bbc4c8273ec6281806c37400f691e55e8adb09a0`
- Canonical candles: `18,582`
- Raw pages: `19`
- Exchange closures: `20`
- Exclusions: `20`
- Segments: `21`
- Issue #61 dataset approval comment: `5264302105`

Stage 1 ingestion, deterministic replay, independent dataset verification, exact v4 handoff validation, and clean-worktree checks all passed before qualification dispatch.

## Qualification identity

- Workflow: `Candidate v0.2 Development Qualification`
- Workflow run: `31578725769`
- Workflow attempt: `1`
- Qualification ID: `3dfb513eacca7adef6e0742c02bbcfa8d80a47c17f8359907257aa6f636dde45`
- Qualification inventory root: `478870c75e79c19102ac11549f388040075900081a16b96e8bed372b1c36e943`
- Qualification artifact ID: `9136226961`
- Qualification artifact name: `candidate-v0.2-qualification-31578725769`
- Qualification artifact SHA-256: `3726b7ec4f84711d8fb9d4d0ccf6baadd67e1a0d3d56af3d04affe9ef3c273fe`
- Classification: **`REJECTED`**
- Promotable: **false**

The workflow's provider-free qualification verification reproduced the same qualification ID, inventory root, and `REJECTED` classification. The downloaded qualification artifact ZIP independently recomputed to the GitHub-declared SHA-256, and every file entry declared by `qualification-result.json` matched its recorded byte size and SHA-256.

## Mandatory gate result

Twenty-six mandatory qualification gates were evaluated. Twelve passed and fourteen failed.

### Passed structural and evidence gates

- integrity verification
- trend convergence and repeated-fit determinism across all 12 folds
- complete calibration evidence
- exact 12-fold development count
- shuffled-label negative control
- no-disagreement component control
- 1.5x-cost drawdown ceiling
- 2x-cost drawdown ceiling
- monotonic cost degradation
- sensitivity drawdown ceiling
- provider-free replay
- independent verification

### Failed mandatory gates

| Gate | Observed | Required |
|---|---:|---:|
| `development.positive_return_folds` | `0` | `>=0.60` |
| `development.baseline_rtd_folds` | `missing` | `>=0.60` |
| `development.profit_concentration` | `1` | `<=0.50` |
| `development.trade_count` | `3` | `>=60` |
| `control.delayed_features` | `False` | `true` |
| `control.no_volume` | `False` | `true` |
| `control.no_protection` | `False` | `true` |
| `cost.one_half_return` | `-0.261698903834488...` | `>0` |
| `cost.double_return` | `-0.267215529694676...` | `>=-0.05` |
| `sensitivity.positive_neighbors` | `0` | `>=7/10` |
| `sensitivity.median_return` | `-0.256141530177322...` | `>0` |
| `sensitivity.primary_stability` | `-0.256141530177322...` | locked stability rule |
| `uncertainty.bootstrap_median` | `-3.0636382267469537` | `>0` |
| `uncertainty.bootstrap_lower_bound` | `-16.790571706763753` | `>-0.02` |

## Primary development behavior

The frozen primary Candidate produced only **3 completed trades**, all in development fold 2.

- Fold 2 net return: approximately **`-25.61%`**
- Fold 2 maximum drawdown: approximately **`26.36%`**
- Fold 2 win rate: `1/3`
- Folds 1 and 3–12: `0` completed trades and `0` net return
- Positive-return development folds: `0/12`

This means the rejection is not attributable to the previous segment-boundary implementation defect. The remediation succeeded: chronology/integrity, convergence, determinism, calibration, replay, and independent-verification gates all passed. The terminal rejection comes from the frozen Candidate's development economics, trade sparsity, robustness, sensitivity, component-control, and uncertainty evidence.

## Cost, sensitivity, and uncertainty evidence

Aggregate development return degraded monotonically with higher costs, but remained materially negative:

- base cost: approximately `-25.61%`
- 1.5x cost: approximately `-26.17%`
- 2x cost: approximately `-26.72%`

None of the 10 locked sensitivity neighbors produced positive aggregate development return. The sensitivity median was approximately `-25.61%`.

The deterministic 1,000-replicate moving-block bootstrap also failed the locked uncertainty gates:

- median net-return difference: `-3.0636382267469537`
- 5th percentile net-return difference: `-16.790571706763753`
- 95th percentile net-return difference: `-0.07549586135846292`
- block length: `42`
- seed: `1788`

## Terminal disposition

Candidate v0.2 is **terminally REJECTED** under its preregistered development-only qualification contract.

Therefore:

- no prospective-final seal is created;
- no prospective-final market rows are accessed;
- no final-test evaluation is authorized;
- no threshold, feature, label, model family, solver, regularization, tolerance, iteration ceiling, risk rule, cost rule, split rule, or promotion gate may be changed to rescue v0.2;
- the qualification may not be rerun to seek a better result;
- any future redesign must use a new Candidate v0.3 identity and a separate design/governance gate before implementation or evaluation.

`future_profitability_not_established = true`  
`prospective_final_accessed = false`  
`execution_authorized = false`  
`research_only = true`
