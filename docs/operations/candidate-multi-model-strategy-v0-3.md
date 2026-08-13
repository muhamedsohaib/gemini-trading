# Candidate Multi-Model Strategy v0.3 — Operations Contract

## Boundary

Candidate v0.3 is `RESEARCH_ONLY`. Its canonical identities are `candidate.multi_model.v0_3` and `candidate-multi-model-v0.3`. This procedure grants no exchange execution authority, no paper/demo/live order authority, no credentials authority, and no capital authority.

Candidate v0.2 remains terminally rejected and immutable. Candidate v0.3 is a separate candidate; observed v0.3 evidence may never be used to rescue or retune v0.3. Any post-evidence redesign is Candidate v0.4.

## Frozen development contract

The immutable development window is `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`. Qualification must use one fresh Stage 1 dataset generated from the exact protected merged-main implementation source. A v0.2 Stage 1 artifact is not reusable for v0.3.

Entry selectivity is calibration-only and fold-local. The primary rule is q75 with effective floor `0.50` and at least `40 eligible calibration scores` for the active specialist. The preregistered sensitivity neighbors are q70 and q80. Companion-specialist probability and cross-specialist disagreement are diagnostic controls, not entry vetoes. Expected gross edge must still clear modeled costs plus the locked extra edge hurdle. The locked ablation is `no-percentile-selectivity`.

The simulator, next-candle timing, long/cash restriction, transaction costs, position sizing, stop/trailing-stop rules, purge/embargo chronology, model families, features, labels, regime classifier, negative controls, deterministic bootstrap, replay, and independent verification remain governed by the approved v0.3 design.

## Protected implementation sequence

1. Merge the reviewed implementation only after exact-head CI is completely green.
2. Verify exact merged-main CI. No Stage 1 dispatch is allowed before that succeeds.
3. Generate exactly one fresh Stage 1 dataset from the merged source for `[2018-01-01T00:00:00Z, 2026-08-01T00:00:00Z)`.
4. Independently verify the Stage 1 handoff, source SHA, workflow run ID, dataset ID, inventory root, candle count, closure/exclusion/segment evidence, and cutoff.
5. Record one owner-authored approval on Issue #69 using the exact marker:
   `<!-- candidate-v0.3-dataset-approved:<source_commit>:<dataset_run_id>:<dataset_id> -->`
6. Dispatch `.github/workflows/candidate-v0.3-qualification.yml` once with the exact merged-main SHA and the approved fresh Stage 1 artifact identities.
7. The workflow runs `strategy-v0-3-qualify` and then `strategy-v0-3-verify-qualification`. It does not create a seal automatically.
8. Preserve the portable qualification bundle and its qualification ID/inventory root.

## Qualification outcomes

The only terminal pre-final classifications are `QUALIFIED`, `REJECTED`, and `INCONCLUSIVE` as defined by the frozen v0.3 qualification contract.

- `QUALIFIED`: every mandatory pre-final gate passed and independent verification succeeded. This permits only an optional future-window seal. It does not authorize trading or capital.
- `REJECTED`: a mandatory scientific/economic/control gate failed. The candidate is terminally rejected. Do not tune or rerun it as v0.3.
- `INCONCLUSIVE`: required evidence is incomplete or cannot support the frozen conclusion. Do not tune or rerun it as a rescue.

There are **no prospective-final performance peeks**. No final-period market row may be read, predicted, simulated, materialized, summarized, or used for decisions before the seal's future final start.

## Optional prospective seal

A v0.3 prospective seal may be created only from an independently verified `QUALIFIED` qualification artifact. The sealing command internally observes the verification/seal milestone; there is no user-supplied backdated verification timestamp.

The seal binds the source SHA, dataset ID, Stage 1 inventory identity, v0.3 policy SHA, entry-selectivity policy SHA, qualification ID/inventory root, development cutoff `2026-08-01T00:00:00Z`, bridge interval, and future final boundaries. The final begins at the first UTC calendar-month boundary strictly after successful verification and spans exactly 18 calendar months.

The seal is an identity document only. It contains no market rows or performance evidence and confers no execution authority or capital authority.
