# Economic Contract Consolidation v2 Design

Status: APPROVED PROGRAM SUBSYSTEM DESIGN
Date: 2026-09-15
Parent: `docs/architecture/economic-forecasting-source-of-truth.md`
Boundary: `RESEARCH_ONLY`
Supersedes: no prior sealed data contract; Economic Data Fabric v1 remains replayable

## Objective

Extend the Economic Data Fabric only where required to admit real heterogeneous macroeconomic evidence without weakening the existing v1 truth layer.

The scientific question is whether Gemini Trading can represent and later reconstruct exactly what was knowable at historical forecast origins, including release timing, revisions, corrections, evidence precision, and publication lineage.

This phase does not add forecasting models, trading logic, private credentials, execution authority, leverage, or capital allocation.

## Compatibility Strategy

Economic Data Fabric v1 is frozen as a replay-compatible legacy schema. Existing `economic-observation-v1` and `economic-dataset-v1` bundles must continue to load, replay, verify, and retain their original content identities.

The forward provider contract is additive and versioned. New real-provider evidence uses v2 observation/dataset contracts plus first-class publication and availability-evidence ledgers. No v1 bundle is silently upgraded in place.

Candidate v0.4 remains completely isolated. No v2 macro/event contract is imported by Candidate v0.4 code or tests.

## Package Boundary

Add focused modules beside, not inside, the frozen v1 contracts:

```text
src/gemini_trading/economics/data/
  availability.py
  publication.py
  observation_v2.py
  serialization_v2.py
  dataset_v2.py
  asof_v2.py
  lineage.py
  replay_v2.py
  verification_v2.py
```

Existing v1 modules remain behaviorally stable except for narrowly scoped shared helpers that are proven byte-for-byte regression safe.

## Temporal Precision

Introduce `AvailabilityPrecision` with these semantic classes:

- `EXACT_SECOND`
- `EXACT_MINUTE`
- `EXACT_HOUR`
- `DATE_ONLY`
- `INFERRED_INTERVAL`
- `UNKNOWN`

Precision is evidence, not formatting. A date-only claim must not be converted to midnight, noon, end-of-day, or any other fabricated timestamp.

## Availability Evidence Contract

`EconomicAvailabilityEvidence` is an immutable claim about observability, backed by retained raw evidence.

Required fields:

- `schema_version`: `economic-availability-evidence-v1`
- `evidence_id`: stable deterministic identity within the dataset
- `publication_event_id`: event whose availability this evidence supports
- `source_id`: source contract that supplied the evidence
- `consumer_class`: defined Gemini observer class, initially `public`
- `availability_channel`: explicit channel such as official publisher, official API/file, archival provider, or exchange feed
- `availability_precision`: `AvailabilityPrecision`
- `available_time`: timezone-aware instant when precision supports an instant, otherwise `None`
- `available_date`: calendar date only for `DATE_ONLY`, otherwise `None`
- `interval_start` / `interval_end`: optional aware bounds for `INFERRED_INTERVAL`
- `source_timezone`: optional source-declared timezone identifier when evidenced
- `source_utc_offset_minutes`: optional evidenced offset used only for coarse-date boundary reasoning
- `retrieved_time`: aware Gemini acquisition time
- `raw_sha256`: exact raw evidence digest

Validation is fail-closed. Precision and temporal fields must agree exactly; unknown precision cannot carry a fabricated instant. Retrieval must not predate an exact evidenced availability instant.

Multiple evidence rows may point to one publication event. Disagreement is retained rather than overwritten.

## Publication Event Contract

Introduce immutable `EconomicPublicationEvent` with schema `economic-publication-event-v1`.

A publication event is distinct from every observation it publishes. One event may publish or revise many observations.

Required event fields:

- `event_id`
- `publisher`
- `source_id`
- `event_type`
- optional `scheduled_time`
- optional `published_time`
- canonical `available_time` or `available_date`, never fabricated
- `consumer_class`
- `availability_channel`
- `availability_precision`
- all `availability_evidence_ids`
- optional singular `availability_evidence_id` only when the event has an unambiguous admitted claim
- `availability_status`: `RESOLVED`, `CONFLICTED`, or `UNKNOWN`
- `publication_sequence`
- `revision_class`
- optional `provider_native_event_id`
- optional `provider_native_source_id`
- optional `source_version`
- optional `predecessor_event_id`
- `retrieved_time`
- `raw_sha256`

`RevisionClass` distinguishes at minimum `INITIAL`, `ROUTINE_REVISION`, `SEASONAL_REVISION`, `BENCHMARK_REVISION`, `METHODOLOGY_REVISION`, `CORRECTION`, and `OTHER`.

`PublicationSequence` preserves normalized sequence semantics while optional `provider_native_publication_sequence` retains agency terminology where necessary.

A `CORRECTION` is never silently normalized to an economic revision. A correction may supersede a prior publication without asserting that the underlying economic estimate was newly revised.

## Economic Observation v2

Introduce `EconomicObservationV2` with schema `economic-observation-v2`.

It preserves the four canonical clocks while making unsupported precision explicit:

- `observation_time`: aware canonical anchor
- `available_time`: aware exact/admitted instant or `None`
- `vintage_time`: aware source vintage instant or `None`
- `retrieved_time`: aware Gemini acquisition instant

Additional temporal fields:

- `reference_period_start`
- `reference_period_end`
- optional `available_date` when only date-level availability is proven
- optional `vintage_date` when the provider supplies only a vintage date

Additional provenance/lineage fields:

- `version_id`: deterministic canonical observation-version identity
- `publication_event_id`
- `availability_evidence_id` when resolved
- `availability_channel`
- `availability_precision`
- `provider_native_source_id` where supplied
- `source_version` where supplied
- `publication_sequence`
- `revision_class`
- optional `predecessor_version_id`
- `raw_sha256`

The original value/unit/scale/frequency/source fields remain provider-neutral and immutable.

For interval-based macro series, reference-period start and end are mandatory and ordered. They are economic intervals, not synthetic release timestamps.

## Observation ↔ Event Closure

Dataset admission validates every v2 observation against exactly one publication event.

The observation and event must agree on admitted availability, evidence identity, channel, precision, publication sequence, and revision class. A mismatch is a dataset error.

An event with `CONFLICTED` or `UNKNOWN` availability cannot lend an exact `available_time` to an observation. A linked observation may be retained as unresolved evidence, but it is not historically admissible until the conflict is resolved by new retained evidence.

## Revision Graph

Observation versions are append-only. A deterministic version identity is derived from canonical semantic identity fields rather than file order.

For one series/reference period:

- initial publication has no predecessor and uses `RevisionClass.INITIAL`;
- later economic revisions reference the immediately superseded version;
- corrections reference the corrected predecessor and remain `CORRECTION`;
- successors are derived from predecessor links rather than stored as mutable back-pointers;
- cross-series or cross-reference-period predecessor links fail closed;
- cycles and missing predecessors fail closed.

Publication-event predecessor lineage is independently validated when provided.

## Deterministic Serialization

v2 serialization remains UTF-8 compact JSON Lines with explicit payload construction, UTC normalization for true instants, non-scientific Decimal strings, and deterministic row order.

Date-only values serialize as ISO calendar dates, not timestamps. Optional values serialize explicitly as `null`.

Canonical bytes are produced separately for observations, publication events, availability evidence, series registry, and raw-evidence inventory.

## Economic Dataset v2

Introduce `economic-dataset-v2` without mutating `economic-dataset-v1` identity rules.

The v2 manifest binds at minimum:

- canonical observations SHA-256
- publication-event ledger SHA-256
- availability-evidence ledger SHA-256
- series-registry SHA-256
- raw-evidence inventory root SHA-256
- observation/event/evidence counts
- series count
- observation/reference bounds
- exact availability bounds where exact timestamps exist

Dataset identity is SHA-256 over canonical manifest identity fields. Any economically meaningful timing, revision, event, lineage, provenance, or evidence change changes the dataset ID.

Logical v2 bundle layout:

```text
raw/<source_id>/<receipt_id>.bin
registry/series.jsonl
canonical/observations-v2.jsonl
events/publication-events.jsonl
availability/evidence.jsonl
inventory/raw-evidence.jsonl
manifest.json
```

Raw receipt semantics remain storage-neutral and immutable.

## As-Of Semantics

Exact intraday visibility uses only admitted exact availability instants. The boundary rule remains `available_time <= cutoff`.

Adversarial release behavior is therefore:

- one instant before an exact release: invisible;
- exact admissible release boundary: visible;
- one instant after: visible.

Date-only evidence is never converted to an instant. For an intraday cutoff on the same evidenced local calendar date, use is rejected. After the evidenced date is fully past under retained offset semantics, coarse evidence may be admitted only through the explicit coarse-precision path; it must never masquerade as exact intraday evidence.

`INFERRED_INTERVAL`, `UNKNOWN`, and conflicted availability fail closed for exact intraday use.

Latest-visible-vintage selection groups by canonical series plus explicit reference period, not by a fabricated monthly/quarterly instant. Tied admissible versions remain errors.

## Availability Disagreement

Cross-provider disagreement is preserved in the availability-evidence ledger.

The system must not choose the earliest timestamp merely because it is earlier. If candidate evidence rows for one event disagree materially:

1. retain all evidence rows and raw digests;
2. mark the event `CONFLICTED`;
3. clear singular admitted availability fields;
4. prohibit historical use through exact as-of APIs;
5. require new evidence or an explicitly versioned resolution rule before admission.

Semantically equivalent duplicate evidence may coexist, but deterministic normalization must not alter its provenance.

## Runtime Ancestor Availability Lineage

Introduce immutable `AvailabilityLineage` for future derived features/states.

For exact ancestors it carries `max_ancestor_available_time`. Merging lineages takes the maximum exact ancestor time. If any ancestor is date-only, conflicted, interval-only, or unknown, exact lineage is marked unresolved rather than fabricating a timestamp.

A future forecast input with exact cutoff `T` is admissible only when lineage is resolved and `max_ancestor_available_time <= T`.
## V1 Compatibility Proof

Phase A must prove that the additive v2 work does not reinterpret or rewrite v1 evidence.

Required regressions:

- existing `economic-observation-v1` serialization bytes remain unchanged;
- existing `economic-dataset-v1` manifest and dataset ID construction remain unchanged;
- existing v1 replay and independent verification continue to pass without invoking v2 loaders;
- no v2 publication, availability, or lineage field is injected into v1 canonical bytes;
- the v1 synthetic revision integration proof remains green.

A v1 bundle may be read only by the v1 path unless an explicit future migration tool is separately designed. This phase does not provide such a migration.

## Dataset Admission Rules

A v2 dataset is admitted only when every canonical observation is closed by raw evidence and linked to a declared publication event.

For `RESOLVED` event availability, the linked availability evidence must exist, point to the same event, and semantically equal the event/observation admission fields. For `CONFLICTED` or `UNKNOWN` availability, observations may be retained only as non-admissible historical evidence with no exact `available_time`.

Provider-native identifiers and `source_version` are provenance. They may be absent only when the provider does not supply them; adapters must not invent them.

Correction/revision semantics are source-declared facts. When the provider cannot establish the distinction, the adapter must use the conservative normalized class rather than guessing a correction or economic revision.
## Fail-Closed Test Matrix

Phase A must add adversarial tests for at least:

- exact release: one microsecond before is invisible;
- exact release: the boundary itself is visible;
- exact release: one microsecond after is visible;
- date-only availability used for same-day intraday reconstruction is rejected;
- unknown precision cannot carry `available_time`;
- conflicting availability evidence yields `CONFLICTED` and no exact admission;
- multiple vintages for one explicit reference period preserve each version;
- initial release and later revision have correct predecessor lineage;
- correction remains distinguishable from an economic revision;
- one publication event may affect multiple observations;
- observation/event availability mismatch is rejected;
- observation/event sequence or revision-class mismatch is rejected;
- missing event/evidence/raw ancestry is rejected;
- predecessor links across series/reference periods are rejected;
- revision cycles are rejected;
- raw evidence tampering is rejected;
- deterministic input reordering leaves identities unchanged;
- meaningful timing/provenance/lineage changes alter the dataset ID;
- provider-free replay reproduces all v2 canonical ledgers and dataset identity;
- independent verification detects ledger, manifest, raw, or undeclared-file tampering;
- exact ancestor lineage propagates the maximum available time;
- unresolved ancestor lineage remains unresolved and fails exact-cutoff admission.

Tests must establish provider-neutral semantics only. No provider-specific behavior may be guessed into Phase A fixtures.
## Phase A Non-Goals

Contract consolidation does not include:

- ALFRED/FRED HTTP clients or credentials;
- BLS or BEA acquisition adapters;
- provider-specific release parsing;
- broad macro-series coverage;
- calendar forecasting;
- feature engineering or ragged-edge panel construction;
- Forecast Benchmark Arena code;
- model fitting, calibration, or scoring;
- Candidate v0.4 changes;
- trading, paper trading, order submission, leverage, or capital allocation.

The phase may add only the provider-neutral contracts and bundle machinery required for the first real provider proof.

## Phase B Handoff Contract

The first real provider proof must consume the v2 contracts rather than defining new timing semantics inside adapters.

Provider adapters will be responsible for retaining exact returned bytes and mapping source-declared facts into:

1. `EconomicAvailabilityEvidence`;
2. `EconomicPublicationEvent`;
3. linked `EconomicObservationV2` rows;
4. immutable raw receipts;
5. a content-addressed v2 dataset.

ALFRED/FRED may supply archival vintage history, but direct official BLS/BEA evidence must establish release timing or revision semantics where the archive does not prove them. No adapter may promote a vintage/retrieval/file timestamp into exact availability without retained evidence.
## Phase A Stop Gate

Contract Consolidation v2 is complete only when the schema can represent without ambiguity:

- a CPI seasonal revision;
- a payroll benchmark publication affecting multiple observations;
- staged GDP releases such as advance and later estimates;
- a source-declared correction distinct from an economic revision;
- a date-only archival vintage that is prohibited from same-day intraday use;
- an official release with defensible exact publication availability;
- conflicting availability evidence that remains unusable until resolved.

Completion also requires:

- all required adversarial tests green;
- frozen v1 replay/identity regressions green;
- Ruff format and lint green;
- strict Pyright green;
- full pytest green;
- package build green;
- dependency audit green without suppressions;
- tracked-file policy, secret scan, and Gitleaks green;
- exact-head CI green before merge.

Only after this gate may Phase B admit real provider data. Passing Phase A does not authorize model training.

## Governance

`RESEARCH_ONLY` remains mandatory. This design introduces only public/research economic evidence contracts. It grants no private-provider credential use, exchange credential use, execution authority, paper/demo trading authority, leverage, or capital allocation.

Candidate v0.4 remains a separate one-shot BTC-only experiment and may not consume these contracts as economic inputs.
