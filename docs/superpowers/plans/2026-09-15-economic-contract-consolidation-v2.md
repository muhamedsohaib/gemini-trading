# Economic Contract Consolidation v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive v2 point-in-time economic evidence contract that supports reference intervals, publication events, evidenced availability precision, revision lineage, replay, and verification without changing v1 identities.

**Architecture:** Keep all v1 modules byte-compatible. Add focused v2 modules under `gemini_trading.economics.data`; dataset admission closes observations against publication and availability ledgers, while as-of APIs reject unresolved precision and lineage propagates maximum ancestor availability.

**Tech Stack:** Python 3.12, frozen uv environment, dataclasses, `Decimal`, SHA-256, compact JSONL, pytest, Ruff, strict Pyright.

**Spec:** `docs/superpowers/specs/2026-09-15-economic-contract-consolidation-v2-design.md`

## Global Constraints

- `RESEARCH_ONLY` remains in force.
- Candidate v0.4 is untouched and cannot consume macro/event data.
- Existing `economic-observation-v1` and `economic-dataset-v1` canonical bytes and identities remain unchanged.
- Never fabricate intraday `available_time` from date-only, vintage, retrieval, or file timestamps.
- Conflicting availability evidence fails closed.
- No provider client or model training enters Phase A.

---
### Task 1: Availability Evidence Contract

**Files:** Create `src/gemini_trading/economics/data/availability.py`; create `tests/unit/economics/data/test_availability.py`.

**Interfaces:** Produce `AvailabilityPrecision`, `AvailabilityStatus`, `EconomicAvailabilityEvidence`, `ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1`.

- [ ] **RED:** Test exact precision accepts an aware instant; `DATE_ONLY` requires only `available_date`; `INFERRED_INTERVAL` requires ordered aware bounds; `UNKNOWN` rejects all fabricated availability fields; malformed digests/blank identities fail.
- [ ] Run `uv run pytest tests/unit/economics/data/test_availability.py -q` and confirm failures are missing-contract failures.
- [ ] **GREEN:** Implement frozen dataclass/enums with exact precision-field compatibility and retrieval chronology validation.
- [ ] Run the focused test plus `uv run ruff check src/gemini_trading/economics/data/availability.py tests/unit/economics/data/test_availability.py`.
- [ ] Commit `feat: add evidenced economic availability contract`.

### Task 2: Publication Event Contract

**Files:** Create `src/gemini_trading/economics/data/publication.py`; create `tests/unit/economics/data/test_publication.py`.

**Interfaces:** Produce `RevisionClass`, `PublicationSequence`, `EconomicPublicationEvent`, `ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1`.

- [ ] **RED:** Test resolved exact/date-only events, one event with multiple evidence IDs, conflicted/unknown events with no admitted exact time, correction distinct from revision, and invalid resolved evidence closure.
- [ ] Run `uv run pytest tests/unit/economics/data/test_publication.py -q` and observe RED.
- [ ] **GREEN:** Implement immutable event validation; preserve provider-native sequence/source/version fields; require unique evidence IDs.
- [ ] Run focused test and Ruff.
- [ ] Commit `feat: add economic publication event contract`.
### Task 3: Observation v2 and Version Identity

**Files:** Create `src/gemini_trading/economics/data/observation_v2.py`; create `tests/unit/economics/data/test_observation_v2.py`.

**Interfaces:** Produce `EconomicObservationV2`, `ECONOMIC_OBSERVATION_SCHEMA_V2`, and `economic_observation_version_id(row) -> str`.

- [ ] **RED:** Test explicit ordered reference periods, four clocks, exact/date-only precision compatibility, resolved evidence linkage, predecessor identity, provider provenance, and invalid chronology/precision/reference intervals.
- [ ] Test version ID is deterministic, order-independent, SHA-256 shaped, and changes for meaningful value/timing/revision/provenance changes.
- [ ] Run `uv run pytest tests/unit/economics/data/test_observation_v2.py -q` and observe RED.
- [ ] **GREEN:** Implement the immutable row and derive `version_id` from canonical semantic payload; validate supplied `version_id` against the derived value.
- [ ] Run focused test and Ruff; commit `feat: add economic observation v2 contract`.

### Task 4: Deterministic v2 Serialization

**Files:** Create `src/gemini_trading/economics/data/serialization_v2.py`; create `tests/unit/economics/data/test_serialization_v2.py`.

**Interfaces:** Produce deterministic serializers for availability evidence, publication events, and v2 observations plus canonical identity keys.

- [ ] **RED:** Assert deterministic bytes under input permutation, explicit `null` optionals, ISO dates without fabricated time, UTC instant normalization, non-scientific Decimal output, and duplicate logical identity rejection.
- [ ] Run `uv run pytest tests/unit/economics/data/test_serialization_v2.py -q` and observe RED.
- [ ] **GREEN:** Implement explicit compact-JSON payloads and sort keys; reuse only v1 helpers that cannot alter v1 behavior.
- [ ] Run focused test and Ruff; commit `feat: serialize economic v2 evidence deterministically`.
### Task 5: Dataset v2 Admission and Revision Graph

**Files:** Create `src/gemini_trading/economics/data/dataset_v2.py`; create `tests/unit/economics/data/test_dataset_v2.py`.

**Interfaces:** Produce `EconomicDatasetV2`, `EconomicDatasetManifestV2`, `build_economic_dataset_v2(...)` and bundle write/load helpers.

- [ ] **RED:** Test event/evidence/raw closure, one event publishing multiple observations, observation↔event timing/precision/sequence/revision mismatch rejection, missing links, predecessor chain validity, cross-series/reference predecessor rejection, cycles, and deterministic dataset identity.
- [ ] Test meaningful changes to availability, evidence, event lineage, source version, revision class, or raw inventory change `dataset_id`; input permutation does not.
- [ ] Run `uv run pytest tests/unit/economics/data/test_dataset_v2.py -q` and observe RED.
- [ ] **GREEN:** Implement admission validation, revision-graph validation, component hashes, manifest identity, immutable bundle layout, and load-time canonical byte checks.
- [ ] Run focused test and Ruff; commit `feat: add content-addressed economic dataset v2`.

### Task 6: As-Of Reconstruction and Availability Lineage

**Files:** Create `src/gemini_trading/economics/data/asof_v2.py`, `src/gemini_trading/economics/data/lineage.py`; create `tests/unit/economics/data/test_asof_v2.py`, `tests/unit/economics/data/test_lineage.py`.

**Interfaces:** Produce exact `observations_as_of_v2`, `latest_visible_vintages_v2`, explicit coarse-date query path, `AvailabilityLineage`, `merge_availability_lineages`, and exact-cutoff admission helper.

- [ ] **RED:** Test one microsecond before/boundary/after exact release, date-only same-day intraday rejection, unresolved/conflicted exclusion, multiple vintages by reference interval, tied-version rejection, max-ancestor propagation, and unresolved ancestor fail-closed behavior.
- [ ] Run both focused files and observe RED.
- [ ] **GREEN:** Implement exact path using only resolved exact availability; keep coarse-date behavior separate and explicit; group revisions by `(series_id, reference_period_start, reference_period_end)`.
- [ ] Run focused tests and Ruff; commit `feat: add v2 as-of and ancestor availability semantics`.
### Task 7: Provider-Free Replay and Independent Verification

**Files:** Create `src/gemini_trading/economics/data/replay_v2.py`, `src/gemini_trading/economics/data/verification_v2.py`; create `tests/unit/economics/data/test_replay_v2.py`, `tests/unit/economics/data/test_verification_v2.py`; create `tests/integration/economics/test_economic_data_bundle_v2.py`.

**Interfaces:** Produce `replay_economic_bundle_v2(root)` and `verify_economic_bundle_v2(root)`.

- [ ] **RED:** Seal a synthetic multi-observation publication with initial/revision/correction cases; assert provider-free replay reproduces exact IDs and pre/post-release/pre/post-revision states.
- [ ] Add tamper tests for raw bytes, each canonical ledger, manifest, missing/undeclared raw files, and observation-event mismatch.
- [ ] Run focused replay/verification/integration tests and observe RED.
- [ ] **GREEN:** Implement replay through only sealed bytes, then independent hash/inventory/manifest closure verification without trusting replay success alone.
- [ ] Run focused tests and Ruff; commit `feat: replay and verify economic dataset v2`.

### Task 8: Compatibility and Phase-A Repository Gate

**Files:** Modify only tests/docs if required; do not change v1 production contracts.

- [ ] Run the original economics suite and assert v1 remains green: `uv run pytest tests/unit/economics tests/integration/economics -q`.
- [ ] Add a byte-level v1 regression only if existing tests do not already pin the required identity/serialization invariants; observe RED before any corrective code.
- [ ] Run `uv run ruff format --check src tests`; `uv run ruff check src tests`; `uv run pyright`; `uv run pytest`; `uv build`; `uv run pip-audit`.
- [ ] Run repository tracked-file policy, secret scan, and Gitleaks using the same commands/configuration as canonical CI.
- [ ] Re-read the design stop gate and compare it requirement-by-requirement against tests and code; repair only Phase-A gaps through RED→GREEN.
- [ ] Commit `test: close economic contract consolidation v2 gate`.

## Merge Gate

Push only the isolated branch, open a PR to `main`, and require exact-head CI green. Merge only if the PR head SHA verified by CI is the same SHA being merged. After merge, verify resulting `main` and stop Phase A before provider/model work unless the provider proof is begun as a separately versioned Phase B design.
