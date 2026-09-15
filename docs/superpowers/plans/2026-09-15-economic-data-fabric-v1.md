# Economic Data Fabric v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-neutral, vintage-aware, point-in-time economic dataset contract with deterministic identity, immutable evidence, as-of visibility, provider-free replay, and independent verification.

**Architecture:** Add an isolated `gemini_trading.economics.data` namespace so the new economic program cannot alter historical candle or Candidate identities. Store immutable raw receipts, canonical series definitions, canonical observation JSONL, a deterministic raw-evidence inventory, and a content-addressed manifest. The only visibility authority is each observation's `available_time`.

**Tech Stack:** Python 3.12, stdlib dataclasses/enums/pathlib/hashlib/json, `Decimal`, existing `canonical_json_bytes`, pytest, Ruff, strict Pyright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-economic-data-fabric-v1-design.md`

## Global Constraints

- Entire milestone is `RESEARCH_ONLY`.
- No provider/network client is added.
- No credentials, exchange submission, paper/live execution, leverage, derivatives, portfolio allocation, or capital authority is added.
- Candidate v0.1-v0.4 serialized behavior and evidence contracts must remain unchanged.
- `available_time` is the sole as-of visibility authority.
- Every datetime is timezone-aware and serialized in UTC.
- Every numeric value is finite `Decimal` and serialized as a non-scientific string.
- Every production behavior follows RED -> verify RED -> minimal GREEN -> focused verification -> commit.
- No existing candle dataset schema or identity function is modified unless a separately failing regression proves a version-neutral utility is required; the default implementation requires no such change.

## File Structure

```text
src/gemini_trading/economics/
  __init__.py
  data/
    __init__.py
    observation.py        # immutable observation and chronology validation
    series.py             # canonical series definitions and registry
    serialization.py      # deterministic payload/JSONL encoding
    storage.py            # immutable raw receipts and evidence inventory
    dataset.py            # dataset manifest, builder, content identity, bundle IO
    asof.py               # no-leakage point-in-time visibility APIs
    replay.py             # provider-free deterministic reconstruction
    verification.py       # independent tamper/integrity verification

tests/unit/economics/data/
  test_observation.py
  test_series.py
  test_serialization.py
  test_storage.py
  test_dataset.py
  test_asof.py
  test_replay.py
  test_verification.py

tests/integration/economics/
  test_economic_data_bundle.py

docs/operations/economic-data-fabric-v1.md
```

---

### Task 1: Freeze the Economic Observation Contract

**Files:**
- Create: `src/gemini_trading/economics/__init__.py`
- Create: `src/gemini_trading/economics/data/__init__.py`
- Create: `src/gemini_trading/economics/data/observation.py`
- Create: `tests/unit/economics/data/test_observation.py`

**Interfaces:**
- Produces: `ECONOMIC_OBSERVATION_SCHEMA_V1: Final[str]`
- Produces: `EconomicObservation`
- Produces: `EconomicDataError`, `EconomicChronologyError`

- [ ] **Step 1: Write the failing observation-construction tests**

```python
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicObservation,
)


def test_observation_accepts_point_in_time_revision_row() -> None:
    row = EconomicObservation(
        schema_version="economic-observation-v1",
        series_id="macro.us.cpi.all_items.index",
        observation_time=datetime(2026, 7, 1, tzinfo=UTC),
        available_time=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        vintage_time=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        retrieved_time=datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        source_id="fixture.macro.v1",
        value=Decimal("324.100"),
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        release_id="cpi-2026-08",
        raw_sha256="a" * 64,
    )
    assert row.available_time > row.observation_time


def test_observation_rejects_value_visible_before_reference_time() -> None:
    with pytest.raises(EconomicChronologyError, match="available_time"):
        EconomicObservation(
            schema_version="economic-observation-v1",
            series_id="macro.test",
            observation_time=datetime(2026, 8, 1, tzinfo=UTC),
            available_time=datetime(2026, 7, 31, tzinfo=UTC),
            vintage_time=None,
            retrieved_time=datetime(2026, 8, 1, tzinfo=UTC),
            source_id="fixture",
            value=Decimal("1"),
            unit="index",
            scale=Decimal("1"),
            frequency="monthly",
            release_id=None,
            raw_sha256="b" * 64,
        )
```

Add one focused test each for naive datetimes, `retrieved_time < available_time`, `vintage_time > retrieved_time`, non-finite value, zero scale, empty identifiers, and malformed SHA-256.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
uv run pytest tests/unit/economics/data/test_observation.py -v
```

Expected: collection/import failure because `gemini_trading.economics.data.observation` does not exist.

- [ ] **Step 3: Implement the minimal immutable contract**

`observation.py` must contain:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

ECONOMIC_OBSERVATION_SCHEMA_V1: Final[str] = "economic-observation-v1"


class EconomicDataError(ValueError):
    """Base error for economic data contract violations."""


class EconomicChronologyError(EconomicDataError):
    """Raised when point-in-time chronology is invalid."""


@dataclass(frozen=True, slots=True)
class EconomicObservation:
    schema_version: str
    series_id: str
    observation_time: datetime
    available_time: datetime
    vintage_time: datetime | None
    retrieved_time: datetime
    source_id: str
    value: Decimal
    unit: str
    scale: Decimal
    frequency: str
    release_id: str | None
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_OBSERVATION_SCHEMA_V1:
            raise EconomicDataError("unsupported economic observation schema")
        for name, value in (
            ("series_id", self.series_id),
            ("source_id", self.source_id),
            ("unit", self.unit),
            ("frequency", self.frequency),
        ):
            if not value.strip():
                raise EconomicDataError(f"{name} must not be empty")
        for name, value in (
            ("observation_time", self.observation_time),
            ("available_time", self.available_time),
            ("retrieved_time", self.retrieved_time),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise EconomicChronologyError(f"{name} must be timezone-aware")
        if self.vintage_time is not None and (
            self.vintage_time.tzinfo is None or self.vintage_time.utcoffset() is None
        ):
            raise EconomicChronologyError("vintage_time must be timezone-aware")
        if self.available_time < self.observation_time:
            raise EconomicChronologyError("available_time precedes observation_time")
        if self.retrieved_time < self.available_time:
            raise EconomicChronologyError("retrieved_time precedes available_time")
        if self.vintage_time is not None and self.vintage_time > self.retrieved_time:
            raise EconomicChronologyError("vintage_time exceeds retrieved_time")
        if not self.value.is_finite():
            raise EconomicDataError("value must be finite")
        if not self.scale.is_finite() or self.scale == 0:
            raise EconomicDataError("scale must be finite and nonzero")
        if len(self.raw_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.raw_sha256):
            raise EconomicDataError("raw_sha256 must be lowercase SHA-256 hex")
```

Do not silently mutate incoming datetime timezone objects in `__post_init__`; canonicalization is a serialization concern.

- [ ] **Step 4: Verify GREEN and static quality**

```bash
uv run pytest tests/unit/economics/data/test_observation.py -v
uv run pyright src/gemini_trading/economics/data/observation.py tests/unit/economics/data/test_observation.py
uv run ruff check src/gemini_trading/economics tests/unit/economics
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics tests/unit/economics/data/test_observation.py
git commit -m "feat: define point-in-time economic observations"
```

---

### Task 2: Freeze Series Semantics and Canonical Registry

**Files:**
- Create: `src/gemini_trading/economics/data/series.py`
- Create: `tests/unit/economics/data/test_series.py`

**Interfaces:**
- Produces: `EconomicDomain`, `RevisionPolicy`, `EconomicSeriesDefinition`
- Produces: `EconomicSeriesRegistry`
- Consumes: no provider code

- [ ] **Step 1: Write RED tests for semantic identity and duplicate rejection**

```python
from decimal import Decimal

import pytest

from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)


def test_registry_rejects_two_definitions_for_one_series_id() -> None:
    first = EconomicSeriesDefinition(
        schema_version="economic-series-v1",
        series_id="macro.us.cpi.all_items.index",
        title="US CPI All Items",
        domain=EconomicDomain.MACRO,
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        observation_semantics="reference-month start",
        availability_semantics="public release timestamp",
        revision_policy=RevisionPolicy.REVISIONED,
    )
    second = EconomicSeriesDefinition(
        **{**first.__dict__, "title": "Conflicting title"}
    )
    with pytest.raises(ValueError, match="duplicate series_id"):
        EconomicSeriesRegistry((first, second))
```

Because slotted frozen dataclasses do not expose `__dict__`, construct the conflicting definition explicitly in the actual test rather than relying on this shorthand.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_series.py -v
```

Expected: import failure because `series.py` does not exist.

- [ ] **Step 3: Implement enums, definition validation, and sorted registry**

Use exact enum values:

```python
class EconomicDomain(StrEnum):
    MARKET = "MARKET"
    MACRO = "MACRO"
    EVENT = "EVENT"
    ALTERNATIVE = "ALTERNATIVE"


class RevisionPolicy(StrEnum):
    NONE = "NONE"
    REVISIONED = "REVISIONED"
    SOURCE_DEPENDENT = "SOURCE_DEPENDENT"
```

`EconomicSeriesRegistry` stores definitions sorted by `series_id`, rejects duplicates, exposes `by_id(series_id)`, and fails if empty.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest tests/unit/economics/data/test_series.py -v
uv run pyright src/gemini_trading/economics/data/series.py
uv run ruff check src/gemini_trading/economics/data/series.py tests/unit/economics/data/test_series.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/series.py tests/unit/economics/data/test_series.py
git commit -m "feat: define canonical economic series registry"
```

---

### Task 3: Add Deterministic Economic Serialization

**Files:**
- Create: `src/gemini_trading/economics/data/serialization.py`
- Create: `tests/unit/economics/data/test_serialization.py`

**Interfaces:**
- Consumes: `EconomicObservation`, `EconomicSeriesRegistry`
- Produces: `serialize_observations(...) -> bytes`
- Produces: `serialize_series_registry(...) -> bytes`
- Produces: `observation_identity_key(...)`

- [ ] **Step 1: Write RED tests for ordering, UTC normalization, decimals, and conflicting duplicates**

Create two observations in reverse input order and assert exact JSONL output order. Include an observation expressed with a `+04:00` timezone and assert the serialized timestamp is the equivalent UTC `Z` instant.

Assert `Decimal("1.2300")` serializes as the exact non-scientific string `"1.2300"`.

Create two rows with the same logical identity key but different `value` and assert serialization fails closed.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_serialization.py -v
```

- [ ] **Step 3: Implement explicit payload construction**

The observation payload key order must be exactly:

```text
schema_version
series_id
observation_time
available_time
vintage_time
retrieved_time
source_id
value
unit
scale
frequency
release_id
raw_sha256
```

Use `json.dumps(..., ensure_ascii=False, separators=(",", ":")) + "\n"` for JSONL rows. Normalize datetimes to UTC with millisecond precision. Do not sort JSON keys dynamically because explicit payload order is part of the byte contract.

The logical duplicate key is:

```python
(
    row.series_id,
    row.observation_time.astimezone(UTC),
    row.available_time.astimezone(UTC),
    row.source_id,
    row.release_id or "",
)
```

Two byte-identical rows may be deduplicated only if the implementation makes that behavior explicit and tested. Prefer fail-closed duplicate rejection in v1.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest tests/unit/economics/data/test_serialization.py -v
uv run pyright src/gemini_trading/economics/data/serialization.py
uv run ruff check src/gemini_trading/economics/data/serialization.py tests/unit/economics/data/test_serialization.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/serialization.py tests/unit/economics/data/test_serialization.py
git commit -m "feat: serialize economic evidence deterministically"
```

---

### Task 4: Add Immutable Raw Evidence Storage and Inventory

**Files:**
- Create: `src/gemini_trading/economics/data/storage.py`
- Create: `tests/unit/economics/data/test_storage.py`

**Interfaces:**
- Produces: `RawEvidenceReceipt`
- Produces: `RawEvidenceInventory`
- Produces: `LocalEconomicEvidenceStore`

- [ ] **Step 1: Write RED tests for idempotency, conflict, traversal, and inventory root stability**

```python
def test_same_receipt_same_bytes_is_idempotent(tmp_path: Path) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)
    first = store.put(source_id="fixture", receipt_id="release-1", payload=b"abc")
    second = store.put(source_id="fixture", receipt_id="release-1", payload=b"abc")
    assert first == second


def test_same_receipt_different_bytes_fails_closed(tmp_path: Path) -> None:
    store = LocalEconomicEvidenceStore(tmp_path)
    store.put(source_id="fixture", receipt_id="release-1", payload=b"abc")
    with pytest.raises(EconomicStorageError, match="immutable"):
        store.put(source_id="fixture", receipt_id="release-1", payload=b"xyz")
```

Also reject `source_id="../escape"`, `receipt_id="../../escape"`, empty payload, and malformed path segments.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_storage.py -v
```

- [ ] **Step 3: Implement immutable storage**

Store at:

```text
<root>/raw/<source_id>/<receipt_id>.bin
```

Allow only path-segment characters `[A-Za-z0-9._-]` and reject `.`/`..` as whole segments.

`RawEvidenceReceipt` contains `schema_version="economic-raw-receipt-v1"`, `source_id`, `receipt_id`, `relative_path`, `byte_length`, and `sha256`.

`RawEvidenceInventory` sorts receipts by `(source_id, receipt_id, sha256)`, serializes canonically, and exposes `inventory_root_sha256` as SHA-256 of those bytes.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest tests/unit/economics/data/test_storage.py -v
uv run pyright src/gemini_trading/economics/data/storage.py
uv run ruff check src/gemini_trading/economics/data/storage.py tests/unit/economics/data/test_storage.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/storage.py tests/unit/economics/data/test_storage.py
git commit -m "feat: store immutable economic raw evidence"
```

---

### Task 5: Build Content-Addressed Economic Datasets

**Files:**
- Create: `src/gemini_trading/economics/data/dataset.py`
- Create: `tests/unit/economics/data/test_dataset.py`

**Interfaces:**
- Consumes: registry bytes, canonical observation bytes, raw inventory
- Produces: `EconomicDatasetManifest`
- Produces: `EconomicDataset`
- Produces: `build_economic_dataset(...) -> EconomicDataset`
- Produces: `write_economic_bundle(...) -> EconomicDatasetManifest`
- Produces: `load_economic_bundle(...) -> EconomicDataset`

- [ ] **Step 1: Write RED tests for exact identity and evidence closure**

Tests must prove:

- identical semantic inputs in different input order produce the same dataset ID;
- changing one observation value changes the dataset ID;
- changing one `available_time` changes the dataset ID;
- changing registry semantics changes the dataset ID;
- every observation `raw_sha256` must exist in the raw inventory;
- a dataset with an observation series missing from the registry fails.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_dataset.py -v
```

- [ ] **Step 3: Implement manifest identity**

The identity payload passed to `canonical_json_bytes()` must contain exactly:

```python
{
    "schema_version": "economic-dataset-v1",
    "canonical_observations_sha256": ...,
    "series_registry_sha256": ...,
    "raw_inventory_root_sha256": ...,
    "observation_count": ...,
    "series_count": ...,
    "minimum_observation_time": ...,
    "maximum_observation_time": ...,
    "minimum_available_time": ...,
    "maximum_available_time": ...,
}
```

`dataset_id = sha256(canonical_json_bytes(identity_payload)).hexdigest()`.

`write_economic_bundle()` writes exact paths from the spec and refuses to overwrite conflicting existing bytes. Use atomic temp-file replacement only inside the bundle root; do not create mutable latest aliases.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest tests/unit/economics/data/test_dataset.py -v
uv run pyright src/gemini_trading/economics/data/dataset.py
uv run ruff check src/gemini_trading/economics/data/dataset.py tests/unit/economics/data/test_dataset.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/dataset.py tests/unit/economics/data/test_dataset.py
git commit -m "feat: build content-addressed economic datasets"
```

---

### Task 6: Enforce As-Of No-Leakage Visibility

**Files:**
- Create: `src/gemini_trading/economics/data/asof.py`
- Create: `tests/unit/economics/data/test_asof.py`

**Interfaces:**
- Consumes: `EconomicDataset`
- Produces: `observations_as_of(dataset, cutoff, *, series_id=None)`
- Produces: `latest_visible_vintages(dataset, cutoff, *, series_id=None)`

- [ ] **Step 1: Write the critical RED revision-leakage test**

Construct one reference period with:

- initial value `100.0`, available `2026-02-01T12:00Z`;
- revised value `101.0`, available `2026-03-01T12:00Z`.

Assert:

```python
pre_revision = latest_visible_vintages(dataset, datetime(2026, 2, 15, tzinfo=UTC))
assert pre_revision[0].value == Decimal("100.0")

post_revision = latest_visible_vintages(dataset, datetime(2026, 3, 15, tzinfo=UTC))
assert post_revision[0].value == Decimal("101.0")
```

Also assert a row with `available_time` one microsecond after the cutoff is invisible.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_asof.py -v
```

- [ ] **Step 3: Implement visibility with no full-dataset fallback**

`observations_as_of` filters only `row.available_time <= cutoff` and returns canonical ordering.

`latest_visible_vintages` groups by `(series_id, observation_time)`, selects greatest visible `available_time`, and raises `EconomicDataError` if two non-identical rows tie at the same greatest `available_time` for one group.

Reject naive cutoff timestamps.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest tests/unit/economics/data/test_asof.py -v
uv run pyright src/gemini_trading/economics/data/asof.py
uv run ruff check src/gemini_trading/economics/data/asof.py tests/unit/economics/data/test_asof.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/asof.py tests/unit/economics/data/test_asof.py
git commit -m "feat: enforce point-in-time economic visibility"
```

---

### Task 7: Add Provider-Free Replay and Independent Verification

**Files:**
- Create: `src/gemini_trading/economics/data/replay.py`
- Create: `src/gemini_trading/economics/data/verification.py`
- Create: `tests/unit/economics/data/test_replay.py`
- Create: `tests/unit/economics/data/test_verification.py`

**Interfaces:**
- Produces: `replay_economic_bundle(root: Path) -> EconomicDataset`
- Produces: `verify_economic_bundle(root: Path) -> EconomicDatasetManifest`

- [ ] **Step 1: Write RED exact-replay and tamper tests**

A valid bundle must replay to the exact original dataset ID.

Independently mutate copied fixtures for one test each:

- raw byte;
- canonical value;
- canonical `available_time`;
- series registry title/semantics;
- raw inventory SHA;
- manifest dataset ID;
- missing raw file;
- observation referencing unknown raw digest.

Each must fail with a deterministic economic-data/verification exception.

- [ ] **Step 2: Verify RED**

```bash
uv run pytest tests/unit/economics/data/test_replay.py tests/unit/economics/data/test_verification.py -v
```

- [ ] **Step 3: Implement replay without provider imports**

Replay reads only the bundle root. It verifies raw receipts and registry/observation structure, reconstructs canonical bytes, rebuilds the dataset through `build_economic_dataset`, and compares the manifest byte-relevant fields.

`verification.py` performs a second top-level integrity walk and returns the verified manifest only after exact replay succeeds.

No module under `gemini_trading.data.providers` may be imported.

- [ ] **Step 4: Prove provider independence and GREEN**

Add a test that injects a sentinel into `sys.modules` or monkeypatches any accidental provider import path to raise immediately; replay must still succeed.

```bash
uv run pytest tests/unit/economics/data/test_replay.py tests/unit/economics/data/test_verification.py -v
uv run pyright src/gemini_trading/economics/data/replay.py src/gemini_trading/economics/data/verification.py
uv run ruff check src/gemini_trading/economics/data/replay.py src/gemini_trading/economics/data/verification.py tests/unit/economics/data/test_replay.py tests/unit/economics/data/test_verification.py
```

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/economics/data/replay.py src/gemini_trading/economics/data/verification.py tests/unit/economics/data/test_replay.py tests/unit/economics/data/test_verification.py
git commit -m "feat: replay and verify economic datasets provider-free"
```

---

### Task 8: Prove the Full Synthetic Revisioned Bundle and Document Operations

**Files:**
- Create: `tests/integration/economics/test_economic_data_bundle.py`
- Create: `docs/operations/economic-data-fabric-v1.md`

**Interfaces:**
- Consumes every v1 economic-data component
- Produces one end-to-end synthetic evidence proof

- [ ] **Step 1: Write RED integration test before any fixture helper extraction**

The test must:

1. store at least three immutable raw receipts;
2. define one non-revisioned market series and one revisioned monthly macro series;
3. create at least four observations, including two vintages for one macro reference period;
4. build and write the bundle;
5. replay and verify the bundle;
6. assert exact dataset-ID equality across build/replay/verify;
7. assert the pre-revision as-of view exposes only the initial macro value;
8. assert the post-revision view exposes the revised value;
9. assert the market series remains visible according to its own availability time.

- [ ] **Step 2: Verify RED if any integration surface is missing**

```bash
uv run pytest tests/integration/economics/test_economic_data_bundle.py -v
```

Expected: fail only for any integration gap exposed by real composition. If it passes immediately because all component APIs already compose correctly, retain the test and proceed; do not add unnecessary production code merely to manufacture a failure.

- [ ] **Step 3: Make only minimal integration corrections and verify GREEN**

```bash
uv run pytest tests/unit/economics tests/integration/economics -v
```

Expected: PASS.

- [ ] **Step 4: Write the operator document**

`docs/operations/economic-data-fabric-v1.md` must state:

- v1 is provider-neutral and synthetic-fixture proven;
- exact bundle layout;
- observation/availability/vintage semantics;
- dataset identity formula;
- replay and verification behavior;
- the revision-leakage example;
- `RESEARCH_ONLY` and no execution authority;
- next milestone is a separately specified real provider adapter, not model training.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/economics/test_economic_data_bundle.py docs/operations/economic-data-fabric-v1.md
git commit -m "docs: prove Economic Data Fabric v1 end to end"
```

---

### Task 9: Full Repository Regression and Merge Readiness

**Files:**
- No new production behavior.
- Modify only formatting/docs discovered by the exact gate.

**Interfaces:**
- Produces the exact-head merge evidence for Economic Data Fabric v1.

- [ ] **Step 1: Run focused economic-data verification**

```bash
uv run pytest tests/unit/economics tests/integration/economics -v
uv run pyright src/gemini_trading/economics tests/unit/economics tests/integration/economics
uv run ruff format --check --diff src/gemini_trading/economics tests/unit/economics tests/integration/economics
uv run ruff check src/gemini_trading/economics tests/unit/economics tests/integration/economics
```

Expected: all PASS.

- [ ] **Step 2: Run the full repository gate exactly**

```bash
uv sync --all-groups --frozen
uv run ruff format --check --diff .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run python -c "import subprocess; from gemini_trading.safety.repository_policy import validate_tracked_paths; validate_tracked_paths(subprocess.check_output(['git','ls-files'], text=True).splitlines())"
uv run pre-commit run detect-secrets --all-files
```

GitHub Actions must additionally pass Gitleaks on the exact PR head.

- [ ] **Step 3: Prove legacy isolation**

Run the existing candle dataset and Candidate regression suites selected by their current paths. At minimum, all existing repository tests are already covered by `uv run pytest`; explicitly inspect the diff to confirm no files under `src/gemini_trading/strategy/` and no existing candle identity functions changed.

- [ ] **Step 4: Record exact-head evidence in the PR**

The PR body or final comment records:

- exact head SHA;
- focused test count/result;
- full pytest result;
- Pyright/Ruff/build/audit/secrets results;
- GitHub CI run IDs;
- statement that no provider or execution capability was added.

- [ ] **Step 5: Merge through the repository's protected process**

After required checks are green and review threads are resolved, merge. The next branch begins from the exact merged main SHA and designs the first real vintage-aware provider adapter.

---

## Self-Review Result

Spec coverage: complete for observation chronology, semantic registry, deterministic serialization, raw evidence, content identity, as-of visibility, replay, verification, end-to-end proof, and regression isolation.

Placeholder scan: no TBD/TODO/"implement later" instructions are part of this plan.

Type consistency: later tasks consume the exact class/function names introduced earlier.

Scope: provider clients, forecast models, state estimation, and trading integration are intentionally excluded and require separate specs.
