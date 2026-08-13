# Candidate Multi-Model Strategy v0.3 — Step Verification

Use this checklist as an evidence ledger, not as permission to change the candidate. Boundary: `RESEARCH_ONLY`.

## A. Implementation gate

- Confirm the exact reviewed implementation identifies itself only as `candidate.multi_model.v0_3` / `candidate-multi-model-v0.3`.
- Confirm the development cutoff is exactly `2026-08-01T00:00:00Z` and no later candle is admitted.
- Confirm q75 is the primary calibration-only percentile, with floor `0.50` and minimum `40 eligible calibration scores`.
- Confirm q70 and q80 are the only entry-percentile sensitivity neighbors.
- Confirm companion/disagreement remain diagnostics and the `no-percentile-selectivity` ablation is present.
- Confirm expected-edge, cost, risk, long/cash, chronology, replay, bootstrap, and negative-control rules remain frozen.
- Run exact-head format, lint, Pyright, pytest, build, dependency audit, tracked-file policy, secret scan, and Gitleaks.

## B. Protected merge and merged-main gate

- Merge only after review-complete exact-head CI success.
- Record the resulting merged-main SHA on Issue #69.
- Require complete exact merged-main CI success before any Stage 1 run.

## C. Fresh Stage 1 gate

- Generate one fresh Stage 1 dataset from the exact merged-main SHA for `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`.
- Do not reuse Candidate v0.2 Stage 1 evidence.
- Independently verify source SHA, Stage 1 run ID, dataset ID, inventory root, candle count, completion state, closure/exclusion evidence, segment evidence, and end-exclusive cutoff.
- Confirm no market row with open time at or after `2026-08-01T00:00:00Z` is present.

## D. Owner approval gate

On Issue #69, the repository owner records exactly one approval marker bound to the verified source, Stage 1 run, and dataset:

`<!-- candidate-v0.3-dataset-approved:<source_commit>:<dataset_run_id>:<dataset_id> -->`

No matching owner-authored marker means no qualification dispatch.

## E. Qualification gate

Dispatch `.github/workflows/candidate-v0.3-qualification.yml` manually with the exact merged-main SHA, fresh Stage 1 run ID, artifact name, and dataset ID.

The workflow must:

1. check out exact `main` at the requested source SHA;
2. use frozen dependencies;
3. verify the clean exact source;
4. verify the Issue #69 owner approval marker;
5. download and verify the exact fresh Stage 1 artifact;
6. recheck the development cutoff;
7. run `strategy-v0-3-qualify`;
8. run `strategy-v0-3-verify-qualification` independently;
9. upload a portable qualification bundle;
10. stop without automatically creating a future seal.

Capture the qualification ID, qualification inventory root, policy SHA, entry-selectivity policy SHA, Stage 1 identities, bootstrap sampled-start identity, threshold artifacts, fold diagnostics, experiment receipts, and gate results.

## F. Classification gate

- `QUALIFIED`: all mandatory gates pass. Optional future-window sealing may proceed, but no execution authority or capital authority exists.
- `REJECTED`: terminal candidate rejection. Any redesign becomes Candidate v0.4.
- `INCONCLUSIVE`: evidence is insufficient for qualification. Do not rescue or tune v0.3.

No outcome may alter v0.3 parameters, thresholds, models, features, labels, costs, risk rules, or gates.

## G. Optional seal gate

Only after independent verification returns `QUALIFIED`, run `strategy-v0-3-create-prospective-seal` manually. The command does not accept a user-selected verification timestamp. It binds the observed verification/seal milestone and creates the first UTC month boundary strictly after that milestone, then exactly 18 calendar months of future final era.

The bridge begins at `2026-08-01T00:00:00Z`. The seal contains no market rows and performs no prediction, simulation, return calculation, or order action.

There are **no prospective-final performance peeks** before the future final start.

## H. Explicit prohibitions

This process provides no private exchange access, no paper/demo/live order submission, no leverage, no shorting, no portfolio allocation, no credentials authority, no execution authority, and no capital authority.
