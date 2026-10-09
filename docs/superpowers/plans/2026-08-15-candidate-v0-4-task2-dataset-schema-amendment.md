# Candidate v0.4 Task 2 Dataset-Schema Amendment

- Date: 2026-08-15
- Parent plan: `docs/superpowers/plans/2026-08-15-candidate-multi-model-strategy-v0-4.md`
- Hourly closure amendment: `docs/superpowers/plans/2026-08-15-candidate-v0-4-task2-hourly-closure-amendment.md`
- Boundary: `RESEARCH_ONLY`
- Financial specification changed: **NO**

## Discovery

The shared `DatasetManifest` contract for `candle-dataset-v4` requires:

```text
exclusion_count == closure_count
segment_count == closure_count + 1
```

That is correct for the frozen Candidate v0.3 4h evidence because every declared closure contains exactly one partial 4h provider row.

The truthful Candidate v0.4 hourly derivation does not have that property. If an interruption occurs exactly at a completed hourly close, the corresponding hourly closure contains fully missing hours but **no partial hourly row to exclude**. Therefore the number of hourly closure intervals can legitimately exceed the number of excluded partial provider rows.

Changing the shared `candle-dataset-v4` invariant would widen the type/semantic surface for v0.1-v0.3 and is unnecessary.

## Corrected v0.4 dataset contract

Candidate v0.4 Stage 1 will use a version-isolated canonical dataset manifest:

`candidate-v0.4-candle-dataset-v1`

It preserves the existing deterministic dataset identity inputs and evidence categories:

- provider, instrument, interval, exact `[start,end)` window;
- first/last canonical opens and exact candle count;
- canonical candle JSONL SHA-256;
- derived hourly closure manifest SHA-256 and count;
- exact partial-row exclusion manifest SHA-256 and count;
- exact segment manifest SHA-256 and count;
- deterministic dataset ID over those content identities.

Its integrity invariants are:

```text
0 <= exclusion_count <= closure_count
segment_count == closure_count + 1
```

and every exclusion closure ID must correspond to a closure that actually declares a partial hourly slot. Every closure still creates one canonical segment break because every derived closure contains at least one unavailable hourly slot.

The existing shared `DatasetManifest`, `candle-dataset-v4`, v0.3 dataset IDs, readers, writers, replay, and verification behavior remain unchanged.

## Storage and replay

The v0.4 Stage 1 artifact may retain the established immutable path layout (`data/raw`, `data/canonical`, handoff inventory), but its dataset manifest and closure loading/verification are performed by version-isolated v0.4 code. Provider-free replay must reconstruct the same canonical candles, closure/exclusion/segment evidence, dataset ID, and inventory root from the bundle.

This amendment changes only evidence representation required by hourly outage truthfulness. It does not alter prices, features, labels, model families, thresholds, costs, risk, qualification gates, or prospective policy.
