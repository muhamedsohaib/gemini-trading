# Sealed BTCUSDT Historical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and operate a two-stage, fail-closed GitHub Actions pipeline that creates one verified Binance Spot BTCUSDT 4-hour dataset for `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)` and then performs one sealed Candidate Multi-Model Strategy v0.1 historical evaluation.

**Architecture:** Stage 1 ingests, replays, verifies, inventories, and uploads immutable dataset evidence. Stage 2 validates that handoff, completes all pre-final work, persists and uploads a durable final-test access receipt, evaluates the last 18 calendar months once, and then replays and independently verifies the 22-file study. The implementation separates pre-final preparation from final access so a rerun cannot silently reopen the sealed partition.

**Tech Stack:** Python 3.12, dataclasses, `Decimal`, canonical JSON/JSONL serialization, immutable local filesystem stores, argparse CLI, pytest, Pyright, Ruff, GitHub Actions, `actions/upload-artifact`, and `actions/download-artifact`.

## Global Constraints

- Safety level remains `RESEARCH_ONLY`.
- Provider is public Binance Spot only; no credentials or private endpoints.
- Instrument is exactly `BTCUSDT`, base `BTC`, quote `USDT`, completed `4h` candles.
- Historical window is exactly `[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)`.
- Strategy identity is exactly `candidate.multi_model.v0_1` with policy `candidate-multi-model-v0.1`.
- Configuration is exactly `tests/fixtures/strategy/candidate-v0.1-config.json`.
- Position state remains long or cash only.
- Final untouched test is the last 18 calendar months and may be accessed once.
- A second final-test access, changed identity, missing evidence, ambiguous resume, or tamper condition fails closed.
- Generated raw data, canonical data, pre-final evidence, access receipts, and full studies remain untracked workflow artifacts.
- No result authorizes paper, demo, live, production, exchange submission, leverage, futures, shorting, portfolio allocation, or real capital.
- All implementation changes go through protected `main`; exact reviewed-head and exact merged-main verification are mandatory.

---

## File Structure

### New source files

- `src/gemini_trading/strategy/handoff.py` — canonical dataset handoff manifest, file inventory, root hash, parsing, and validation.
- `src/gemini_trading/strategy/final_access.py` — durable access receipt, exclusive receipt storage, access authorization, and exact-resume decision.
- `src/gemini_trading/strategy/pre_final.py` — immutable pre-final artifact contract, canonical storage, loading, and identity verification.
- `src/gemini_trading/cli/historical_validation.py` — safe CLI handlers used by the two workflows.

### New workflows

- `.github/workflows/sealed-btcusdt-dataset.yml` — manually dispatched Stage 1 dataset production.
- `.github/workflows/sealed-btcusdt-study.yml` — manually dispatched Stage 2 preparation, receipt, final evaluation, replay, and verification.

### Modified source files

- `src/gemini_trading/strategy/evaluator.py` — split the current all-at-once evaluator into pre-final preparation and final completion while preserving `evaluate_candidate_strategy_study()` as a compatibility wrapper.
- `src/gemini_trading/strategy/study.py` — remove in-memory-only access authorization from the operational path and accept a durable, identity-bound access receipt.
- `src/gemini_trading/strategy/artifacts.py` — include the durable receipt identity and pre-final identity in the final study manifest without changing the 22-file name contract.
- `src/gemini_trading/strategy/verification.py` — verify durable receipt bytes, pre-final identity, handoff references, and exact-resume classification.
- `src/gemini_trading/strategy/replay.py` — reconstruct final artifacts from immutable pre-final and final evidence without provider access.
- `src/gemini_trading/cli/main.py` — register the historical-validation subcommands.
- `.gitignore` — explicitly ignore `data/historical-validation/`.

### New tests

- `tests/unit/strategy/test_handoff.py`
- `tests/unit/strategy/test_final_access.py`
- `tests/unit/strategy/test_pre_final.py`
- `tests/unit/cli/test_historical_validation.py`
- `tests/integration/test_sealed_historical_validation.py`
- `tests/regression/test_durable_final_test_access.py`
- `tests/acceptance/test_sealed_historical_validation_workflows.py`
- `tests/acceptance/test_sealed_historical_validation_documentation.py`

### New documentation and reports

- `docs/operations/sealed-btcusdt-historical-validation.md`
- `reports/verification/sealed-btcusdt-historical-validation-progress.md`
- `reports/verification/sealed-btcusdt-historical-validation-final.md` after the real operation completes.

---

### Task 1: Add the historical-validation failure taxonomy and file inventory primitives

**Files:**
- Modify: `src/gemini_trading/strategy/errors.py`
- Create: `src/gemini_trading/strategy/handoff.py`
- Test: `tests/unit/strategy/test_handoff.py`

**Interfaces:**
- Produces: `ArtifactInventoryEntry`, `build_artifact_inventory(root, relative_paths)`, `inventory_root_sha256(entries)`, and strict relative-path validation.
- Consumed by: Tasks 2, 4, 7, 8, and 10.

- [ ] **Step 1: Write failing tests for safe inventory creation**

```python
from pathlib import Path

import pytest

from gemini_trading.strategy.errors import HistoricalValidationError
from gemini_trading.strategy.handoff import (
    build_artifact_inventory,
    inventory_root_sha256,
)


def test_inventory_is_sorted_and_content_addressed(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_bytes(b"beta\n")
    (tmp_path / "a.txt").write_bytes(b"alpha\n")

    entries = build_artifact_inventory(tmp_path, ("b.txt", "a.txt"))

    assert tuple(item.path for item in entries) == ("a.txt", "b.txt")
    assert len(inventory_root_sha256(entries)) == 64


@pytest.mark.parametrize("path", ("../escape", "/absolute", "a/../../b", "a\\b"))
def test_inventory_rejects_unsafe_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(HistoricalValidationError, match="artifact-relative path"):
        build_artifact_inventory(tmp_path, (path,))
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `uv run pytest tests/unit/strategy/test_handoff.py -q`

Expected: import failure because `handoff.py` and `HistoricalValidationError` do not exist.

- [ ] **Step 3: Add explicit fail-closed errors**

Add to `src/gemini_trading/strategy/errors.py`:

```python
class HistoricalValidationError(StrategyStudyError):
    """Base error for sealed historical-validation evidence."""


class DatasetHandoffError(HistoricalValidationError):
    """Raised when a dataset handoff is missing, mismatched, or tampered."""


class FinalAccessError(HistoricalValidationError):
    """Raised when final-test access or exact resume is not authorized."""


class PreFinalArtifactError(HistoricalValidationError):
    """Raised when pre-final evidence is incomplete or inconsistent."""
```

- [ ] **Step 4: Implement canonical inventory primitives**

Create `src/gemini_trading/strategy/handoff.py` with:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import HistoricalValidationError


@dataclass(frozen=True, slots=True)
class ArtifactInventoryEntry:
    path: str
    size_bytes: int
    sha256: str


def validate_artifact_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HistoricalValidationError("invalid artifact-relative path")
    return path.as_posix()


def build_artifact_inventory(
    root: Path,
    relative_paths: tuple[str, ...],
) -> tuple[ArtifactInventoryEntry, ...]:
    normalized = tuple(validate_artifact_relative_path(item) for item in relative_paths)
    if len(set(normalized)) != len(normalized):
        raise HistoricalValidationError("duplicate artifact-relative path")
    entries: list[ArtifactInventoryEntry] = []
    for relative in sorted(normalized):
        content = (root / relative).read_bytes()
        entries.append(
            ArtifactInventoryEntry(
                path=relative,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    return tuple(entries)


def inventory_root_sha256(entries: tuple[ArtifactInventoryEntry, ...]) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "schema_version": "artifact-inventory-v1",
                "files": [
                    {
                        "path": item.path,
                        "size_bytes": item.size_bytes,
                        "sha256": item.sha256,
                    }
                    for item in entries
                ],
            }
        )
    ).hexdigest()
```

- [ ] **Step 5: Run focused tests and static checks**

Run:

```bash
uv run pytest tests/unit/strategy/test_handoff.py -q
uv run ruff check src/gemini_trading/strategy/handoff.py tests/unit/strategy/test_handoff.py
uv run pyright src/gemini_trading/strategy/handoff.py
```

Expected: all pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/gemini_trading/strategy/errors.py src/gemini_trading/strategy/handoff.py tests/unit/strategy/test_handoff.py
git commit -m "feat: add historical validation inventory primitives"
```

---

### Task 2: Implement the strict dataset handoff manifest

**Files:**
- Modify: `src/gemini_trading/strategy/handoff.py`
- Modify: `tests/unit/strategy/test_handoff.py`

**Interfaces:**
- Produces: `DatasetHandoffManifest`, `serialize_dataset_handoff()`, `load_dataset_handoff()`, `verify_dataset_handoff()`.
- Consumes: Task 1 inventory entries and canonical serialization.
- Consumed by: Stage 1 packaging, Stage 2 validation, and independent verification.

- [ ] **Step 1: Add failing round-trip and mismatch tests**

```python
from gemini_trading.strategy.handoff import (
    DatasetHandoffManifest,
    load_dataset_handoff,
    serialize_dataset_handoff,
    verify_dataset_handoff,
)


def _manifest(entries: tuple[ArtifactInventoryEntry, ...]) -> DatasetHandoffManifest:
    return DatasetHandoffManifest(
        schema_version="sealed-dataset-handoff-v1",
        repository="muhamedsohaib/gemini-trading",
        source_commit="a" * 40,
        workflow_name="sealed-btcusdt-dataset",
        workflow_run_id=123,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="4h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-07-01T00:00:00Z",
        run_id="run-123",
        dataset_id="b" * 64,
        candle_count=18628,
        first_open_time="2018-01-01T00:00:00Z",
        last_open_time="2026-06-30T20:00:00Z",
        replay_status="completed",
        verification_status="verified",
        files=entries,
        inventory_root_sha256=inventory_root_sha256(entries),
    )


def test_handoff_round_trip_is_byte_stable(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    entries = build_artifact_inventory(tmp_path, ("data.txt",))
    manifest = _manifest(entries)

    raw = serialize_dataset_handoff(manifest)

    assert serialize_dataset_handoff(load_dataset_handoff(raw)) == raw
    verify_dataset_handoff(manifest, tmp_path)


def test_handoff_rejects_wrong_dataset_id(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_bytes(b"evidence\n")
    manifest = _manifest(build_artifact_inventory(tmp_path, ("data.txt",)))

    with pytest.raises(DatasetHandoffError, match="dataset identity"):
        verify_dataset_handoff(manifest, tmp_path, expected_dataset_id="c" * 64)
```

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/unit/strategy/test_handoff.py -q`

Expected: missing manifest interfaces.

- [ ] **Step 3: Implement exact fields and invariants**

Add a frozen dataclass with the fields shown in the test. In `__post_init__`, enforce:

```python
if self.schema_version != "sealed-dataset-handoff-v1":
    raise DatasetHandoffError("unsupported dataset handoff schema")
if self.repository != "muhamedsohaib/gemini-trading":
    raise DatasetHandoffError("dataset handoff repository mismatch")
if self.source_commit == "" or len(self.source_commit) != 40:
    raise DatasetHandoffError("invalid source commit")
if (self.symbol, self.base_asset, self.quote_asset, self.interval) != (
    "BTCUSDT", "BTC", "USDT", "4h"
):
    raise DatasetHandoffError("dataset handoff market scope mismatch")
if (self.start, self.end_exclusive) != (
    "2018-01-01T00:00:00Z", "2026-07-01T00:00:00Z"
):
    raise DatasetHandoffError("dataset handoff historical window mismatch")
if self.replay_status != "completed" or self.verification_status != "verified":
    raise DatasetHandoffError("dataset handoff is not verified")
```

Use exact-field parsing; reject missing and extra keys. Serialize with `canonical_json_bytes()` and include the file inventory as ordered dictionaries.

- [ ] **Step 4: Implement full evidence verification**

`verify_dataset_handoff()` must:

```python
def verify_dataset_handoff(
    manifest: DatasetHandoffManifest,
    artifact_root: Path,
    *,
    expected_commit: str | None = None,
    expected_dataset_id: str | None = None,
    expected_run_id: int | None = None,
) -> None:
    if expected_commit is not None and manifest.source_commit != expected_commit:
        raise DatasetHandoffError("source commit mismatch")
    if expected_dataset_id is not None and manifest.dataset_id != expected_dataset_id:
        raise DatasetHandoffError("dataset identity mismatch")
    if expected_run_id is not None and manifest.workflow_run_id != expected_run_id:
        raise DatasetHandoffError("source workflow run mismatch")
    rebuilt = build_artifact_inventory(
        artifact_root,
        tuple(item.path for item in manifest.files),
    )
    if rebuilt != manifest.files:
        raise DatasetHandoffError("dataset artifact inventory mismatch")
    if inventory_root_sha256(rebuilt) != manifest.inventory_root_sha256:
        raise DatasetHandoffError("dataset inventory root mismatch")
```

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/unit/strategy/test_handoff.py -q`

Expected: pass, including tamper, extra-field, duplicate-path, commit, run, and dataset mismatch tests.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/gemini_trading/strategy/handoff.py tests/unit/strategy/test_handoff.py
git commit -m "feat: add verified dataset handoff contract"
```

---

### Task 3: Add a durable final-test access receipt and exact-resume policy

**Files:**
- Create: `src/gemini_trading/strategy/final_access.py`
- Test: `tests/unit/strategy/test_final_access.py`
- Test: `tests/regression/test_durable_final_test_access.py`

**Interfaces:**
- Produces: `FinalAccessIdentity`, `DurableFinalAccessReceipt`, `FinalAccessStore.authorize()`, `load_receipt()`, and `assess_exact_resume()`.
- Consumed by: Tasks 5, 6, 8, and 10.

- [ ] **Step 1: Write failing tests for write-before-read and single use**

```python
from pathlib import Path

import pytest

from gemini_trading.strategy.errors import FinalAccessError
from gemini_trading.strategy.final_access import (
    FinalAccessIdentity,
    FinalAccessStore,
    assess_exact_resume,
)


def _identity() -> FinalAccessIdentity:
    return FinalAccessIdentity(
        code_commit="a" * 40,
        dataset_id="b" * 64,
        configuration_sha256="c" * 64,
        policy_sha256="d" * 64,
        split_plan_sha256="e" * 64,
        pre_final_id="f" * 64,
        workflow_run_id=456,
        workflow_run_attempt=1,
    )


def test_authorize_writes_one_immutable_receipt(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)

    receipt = store.authorize(_identity())

    assert store.load(receipt.receipt_id) == receipt
    with pytest.raises(FinalAccessError, match="already exists"):
        store.authorize(_identity())


def test_changed_run_attempt_cannot_reuse_receipt(tmp_path: Path) -> None:
    store = FinalAccessStore(tmp_path)
    receipt = store.authorize(_identity())
    changed = FinalAccessIdentity(**{**_identity().__dict__, "workflow_run_attempt": 2})

    with pytest.raises(FinalAccessError, match="identity mismatch"):
        store.require(receipt.receipt_id, changed)
```

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/unit/strategy/test_final_access.py tests/regression/test_durable_final_test_access.py -q`

Expected: missing module.

- [ ] **Step 3: Implement canonical identities and receipt storage**

Create `src/gemini_trading/strategy/final_access.py` with frozen dataclasses:

```python
@dataclass(frozen=True, slots=True)
class FinalAccessIdentity:
    code_commit: str
    dataset_id: str
    configuration_sha256: str
    policy_sha256: str
    split_plan_sha256: str
    pre_final_id: str
    workflow_run_id: int
    workflow_run_attempt: int


@dataclass(frozen=True, slots=True)
class DurableFinalAccessReceipt:
    schema_version: str
    identity: FinalAccessIdentity
    evaluation_count: int
    receipt_id: str
```

The receipt ID is the SHA-256 of canonical bytes excluding `receipt_id`. Store it beneath:

```text
data/historical-validation/final-access/<receipt-id>/final-access-receipt.json
```

Use `write_immutable()` and reject an existing final-access directory even when bytes are identical. This is stricter than ordinary artifact idempotence because a repeated authorization is itself prohibited.

- [ ] **Step 4: Implement exact-resume assessment**

```python
class ResumeDecision(StrEnum):
    ALLOWED = "allowed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ExactResumeAssessment:
    decision: ResumeDecision
    checks: tuple[str, ...]


def assess_exact_resume(
    *,
    receipt: DurableFinalAccessReceipt,
    identity: FinalAccessIdentity,
    completed_final_files: tuple[ArtifactInventoryEntry, ...],
    artifact_root: Path,
) -> ExactResumeAssessment:
    if receipt.identity != identity:
        return ExactResumeAssessment(ResumeDecision.INCONCLUSIVE, ("identity_mismatch",))
    if not completed_final_files:
        return ExactResumeAssessment(ResumeDecision.INCONCLUSIVE, ("final_outputs_missing",))
    rebuilt = build_artifact_inventory(
        artifact_root,
        tuple(item.path for item in completed_final_files),
    )
    if rebuilt != completed_final_files:
        return ExactResumeAssessment(ResumeDecision.INCONCLUSIVE, ("final_outputs_tampered",))
    return ExactResumeAssessment(
        ResumeDecision.ALLOWED,
        ("identity_match", "final_outputs_complete", "provider_free_resume_only"),
    )
```

- [ ] **Step 5: Prove rows cannot be returned before receipt persistence**

In the regression test, inject a failing receipt writer into a small guard function and assert that the supplied final-row loader is never called. The operational API must have this order:

```python
def authorize_then_load_final(
    store: FinalAccessStore,
    identity: FinalAccessIdentity,
    final_loader: Callable[[], tuple[int, ...]],
) -> tuple[DurableFinalAccessReceipt, tuple[int, ...]]:
    receipt = store.authorize(identity)
    return receipt, final_loader()
```

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/unit/strategy/test_final_access.py tests/regression/test_durable_final_test_access.py -q
git add src/gemini_trading/strategy/final_access.py tests/unit/strategy/test_final_access.py tests/regression/test_durable_final_test_access.py
git commit -m "feat: add durable final test access guard"
```

---

### Task 4: Define immutable pre-final evidence

**Files:**
- Create: `src/gemini_trading/strategy/pre_final.py`
- Test: `tests/unit/strategy/test_pre_final.py`

**Interfaces:**
- Produces: `PreFinalArtifacts`, `build_pre_final_artifacts()`, `LocalPreFinalStore`, and `verify_pre_final_artifacts()`.
- Consumes: dataset, policy, configuration, split-plan, prediction bundles, development experiment references, and Task 1 inventory primitives.
- Consumed by: Tasks 5, 6, 8, and 10.

- [ ] **Step 1: Write failing tests for exact file contract**

The required pre-final files are:

```python
REQUIRED_PRE_FINAL_NAMES = (
    "configuration.json",
    "development-experiments.jsonl",
    "handoff-reference.json",
    "policy.json",
    "pre-final-manifest.json",
    "pre-final-result-manifest.json",
    "split-plan.json",
)
```

Tests must assert exact sorted names, deterministic identity, immutable writes, and tamper rejection.

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/unit/strategy/test_pre_final.py -q`

- [ ] **Step 3: Implement the pre-final artifact model**

```python
@dataclass(frozen=True, slots=True)
class PreFinalArtifacts:
    pre_final_id: str
    files: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        if tuple(name for name, _ in self.files) != REQUIRED_PRE_FINAL_NAMES:
            raise PreFinalArtifactError("pre-final artifact names are incomplete")
```

`pre_final_id` must bind:

- dataset ID;
- handoff inventory root;
- code commit;
- policy SHA-256;
- configuration SHA-256;
- split-plan SHA-256;
- all completed development experiment IDs and evidence hashes;
- required development case list.

Store beneath:

```text
data/historical-validation/pre-final/<pre-final-id>/
```

- [ ] **Step 4: Implement independent verification**

`verify_pre_final_artifacts()` must parse every file, recompute every hash and identity, require all development folds and case IDs, and reject any final-phase record in pre-final evidence.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/strategy/test_pre_final.py -q
git add src/gemini_trading/strategy/pre_final.py tests/unit/strategy/test_pre_final.py
git commit -m "feat: add immutable pre-final study evidence"
```

---

### Task 5: Split Candidate evaluation into pre-final preparation and one-time completion

**Files:**
- Modify: `src/gemini_trading/strategy/evaluator.py`
- Modify: `src/gemini_trading/strategy/study.py`
- Modify: `src/gemini_trading/strategy/study_execution.py`
- Modify: `src/gemini_trading/strategy/artifacts.py`
- Test: `tests/integration/test_sealed_historical_validation.py`
- Test: `tests/regression/test_final_test_seal.py`

**Interfaces:**
- Produces:
  - `prepare_candidate_strategy_study(...) -> PreFinalArtifacts`
  - `complete_candidate_strategy_study(..., receipt: DurableFinalAccessReceipt) -> StrategyStudyArtifacts`
  - compatibility wrapper `evaluate_candidate_strategy_study(...)` for synthetic existing tests only.
- Consumes: Tasks 3 and 4.

- [ ] **Step 1: Write a failing integration test proving pre-final isolation**

```python
def test_prepare_does_not_materialize_final_phase(tmp_path: Path) -> None:
    dataset = verified_strategy_dataset(tmp_path)

    pre_final = prepare_candidate_strategy_study(
        dataset=dataset,
        simulation=official_simulation(),
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit="a" * 40,
        handoff=verified_handoff(tmp_path, dataset),
    )

    experiments = load_jsonl(pre_final.artifact_bytes("development-experiments.jsonl"))
    assert {row["phase"] for row in experiments} == {"development"}
    assert not (tmp_path / "data" / "strategy-studies").exists()
```

- [ ] **Step 2: Write a failing integration test proving receipt-gated final completion**

```python
def test_complete_requires_matching_durable_receipt(tmp_path: Path) -> None:
    pre_final = prepared_evidence(tmp_path)
    identity = final_identity_for(pre_final, workflow_run_id=900, workflow_run_attempt=1)
    receipt = FinalAccessStore(tmp_path).authorize(identity)

    artifacts = complete_candidate_strategy_study(
        pre_final=pre_final,
        receipt=receipt,
        dataset=verified_dataset(tmp_path),
        simulation=official_simulation(),
        initial_cash=Decimal("10000"),
        output_root=tmp_path,
        code_commit="a" * 40,
    )

    assert artifacts.names == REQUIRED_STUDY_ARTIFACT_NAMES
    assert artifacts.classification.value in {"PASS", "REJECTED", "INCONCLUSIVE"}
```

- [ ] **Step 3: Confirm RED**

Run: `uv run pytest tests/integration/test_sealed_historical_validation.py -q`

- [ ] **Step 4: Extract shared preparation state**

Introduce an internal frozen object in `evaluator.py`:

```python
@dataclass(frozen=True, slots=True)
class CandidatePreparation:
    policy: CandidatePolicy
    registry: FeatureRegistry
    matrix: FeatureMatrix
    labels: LabelSet
    split_plan: ChronologicalSplitPlan
    bundles: Mapping[tuple[StudyPhase, int | None], PredictionBundle]
    plans: Mapping[tuple[StudyPhase, int | None, str], CasePlan]
    policy_sha256: str
    configuration_sha256: str
    history_requirement_met: bool
```

`_build_preparation(..., include_final: bool)` must never fit final bundles or call `prepare_phase(StudyPhase.FINAL, ...)` when `include_final=False`.

- [ ] **Step 5: Implement `prepare_candidate_strategy_study()`**

It must:

1. validate locked instrument and timeframe;
2. compute features and labels;
3. build the split plan;
4. fit development bundles only;
5. execute every required development case;
6. build and write `PreFinalArtifacts`;
7. return without reading `split_plan.final_test_indices` through any final execution path.

- [ ] **Step 6: Implement `complete_candidate_strategy_study()`**

It must:

1. independently verify pre-final evidence;
2. rebuild the exact preparation identities;
3. require the durable receipt to match code, dataset, configuration, policy, split, pre-final, run, and attempt;
4. only then fit the final bundle and prepare final cases;
5. execute all required final cases once;
6. build the existing 22-file study;
7. include `pre_final_id`, `dataset_handoff_inventory_root`, and `durable_final_access_receipt_id` in `study-manifest.json`;
8. preserve `promotable:false` at the CLI boundary.

- [ ] **Step 7: Preserve existing compatibility behavior**

Keep `evaluate_candidate_strategy_study()` for current synthetic tests by implementing it as:

```python
def evaluate_candidate_strategy_study(...):
    pre_final = prepare_candidate_strategy_study(..., handoff=synthetic_local_handoff(...))
    identity = build_local_final_access_identity(pre_final, workflow_run_id=0, workflow_run_attempt=1)
    receipt = FinalAccessStore(output_root).authorize(identity)
    return complete_candidate_strategy_study(..., pre_final=pre_final, receipt=receipt)
```

The compatibility path must be marked diagnostic and must not be used by the sealed workflows.

- [ ] **Step 8: Run focused and existing regression suites**

```bash
uv run pytest tests/integration/test_sealed_historical_validation.py tests/regression/test_final_test_seal.py tests/acceptance/test_candidate_strategy_end_to_end.py -q
uv run pyright src/gemini_trading/strategy/evaluator.py src/gemini_trading/strategy/study.py
```

- [ ] **Step 9: Commit Task 5**

```bash
git add src/gemini_trading/strategy/evaluator.py src/gemini_trading/strategy/study.py src/gemini_trading/strategy/study_execution.py src/gemini_trading/strategy/artifacts.py tests/integration/test_sealed_historical_validation.py tests/regression/test_final_test_seal.py
git commit -m "feat: separate pre-final and final candidate evaluation"
```

---

### Task 6: Add safe historical-validation CLI commands

**Files:**
- Create: `src/gemini_trading/cli/historical_validation.py`
- Modify: `src/gemini_trading/cli/main.py`
- Test: `tests/unit/cli/test_historical_validation.py`
- Test: `tests/acceptance/test_strategy_cli.py`

**Interfaces:**
- Produces these commands under `research`:
  - `strategy-handoff`
  - `strategy-prepare`
  - `strategy-authorize-final`
  - `strategy-finalize`
  - `strategy-resume`
- Consumed by: Tasks 7 and 8 workflows.

- [ ] **Step 1: Write parser and handler tests**

The accepted command shapes are fixed:

```text
gemini-trading research strategy-handoff --run-id ... --dataset-id ... --source-commit ... --workflow-run-id ... --workflow-run-attempt ... --output-root ...
gemini-trading research strategy-prepare --handoff ... --config tests/fixtures/strategy/candidate-v0.1-config.json --project-root ... --output-root ...
gemini-trading research strategy-authorize-final --pre-final-id ... --workflow-run-id ... --workflow-run-attempt ... --project-root ... --output-root ...
gemini-trading research strategy-finalize --pre-final-id ... --receipt-id ... --project-root ... --output-root ...
gemini-trading research strategy-resume --study-id ... --receipt-id ... --project-root ... --output-root ...
```

Tests must reject arbitrary symbol, date-window, config override, path traversal, malformed IDs, unknown mode, and run-attempt mismatch.

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/unit/cli/test_historical_validation.py -q`

- [ ] **Step 3: Implement strict handlers**

`run_historical_validation(arguments)` must call `load_runtime_policy()` first and return compact sorted JSON-compatible mappings containing only safe IDs, relative paths, counts, checks, and classifications.

Required output shapes:

```python
# strategy-handoff
{
    "dataset_id": str,
    "handoff_path": str,
    "inventory_root_sha256": str,
    "status": "verified",
}

# strategy-prepare
{
    "pre_final_id": str,
    "status": "prepared",
}

# strategy-authorize-final
{
    "pre_final_id": str,
    "receipt_id": str,
    "status": "authorized",
}

# strategy-finalize / strategy-resume
{
    "classification": str,
    "promotable": False,
    "status": "completed" | "verified" | "inconclusive",
    "study_id": str,
    "study_result_id": str,
}
```

- [ ] **Step 4: Register commands in `cli/main.py`**

Route only the five exact command names to `run_historical_validation()`. Keep existing `strategy-evaluate`, `strategy-replay`, and `strategy-verify` unchanged.

- [ ] **Step 5: Run CLI tests and commit**

```bash
uv run pytest tests/unit/cli/test_historical_validation.py tests/acceptance/test_strategy_cli.py -q
git add src/gemini_trading/cli/historical_validation.py src/gemini_trading/cli/main.py tests/unit/cli/test_historical_validation.py tests/acceptance/test_strategy_cli.py
git commit -m "feat: add sealed historical validation CLI"
```

---

### Task 7: Add the manually dispatched Stage 1 dataset workflow

**Files:**
- Create: `.github/workflows/sealed-btcusdt-dataset.yml`
- Modify: `.gitignore`
- Test: `tests/acceptance/test_sealed_historical_validation_workflows.py`

**Interfaces:**
- Produces artifact: `sealed-btcusdt-dataset-${{ github.sha }}-${{ github.run_id }}`.
- Artifact contains `data/raw/`, `data/canonical/`, and `data/historical-validation/handoff/`.
- Consumed by: Stage 2 workflow.

- [ ] **Step 1: Write a failing workflow-contract test**

Parse YAML with `yaml.safe_load()` and assert:

- only `workflow_dispatch` trigger;
- `permissions.contents == "read"`;
- fixed symbol, assets, interval, start, and end;
- checkout uses full history;
- Python 3.12 and pinned `uv` setup;
- no secrets other than GitHub-provided token references;
- ingest, replay, verify, and handoff commands occur in that order;
- retention is explicit;
- artifact name contains commit and run ID;
- no shell interpolation from arbitrary workflow inputs.

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/acceptance/test_sealed_historical_validation_workflows.py -q`

- [ ] **Step 3: Implement the workflow**

The workflow must have one `dataset` job and these steps:

```yaml
name: Sealed BTCUSDT Dataset
on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  dataset:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    env:
      GEMINI_TRADING_MODE: research
      OUTPUT_ROOT: ${{ github.workspace }}/sealed-output
    steps:
      - uses: actions/checkout@v6.0.2
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b
        with:
          version: "0.11.25"
          enable-cache: true
      - uses: actions/setup-python@v6.2.0
        with:
          python-version: "3.12"
      - run: uv sync --all-groups --frozen
      - name: Assert exact clean commit
        run: |
          test "$(git rev-parse HEAD)" = "${GITHUB_SHA}"
          test -z "$(git status --porcelain)"
      - name: Ingest fixed BTCUSDT history
        run: |
          uv run gemini-trading market-data ingest \
            --symbol BTCUSDT --base-asset BTC --quote-asset USDT \
            --interval 4h \
            --start 2018-01-01T00:00:00Z \
            --end 2026-07-01T00:00:00Z \
            --output-root "${OUTPUT_ROOT}" | tee ingest.json
      - name: Replay and verify
        run: uv run python scripts/run_sealed_dataset_verification.py ingest.json "${OUTPUT_ROOT}"
      - name: Build handoff
        run: uv run python scripts/build_sealed_dataset_handoff.py ingest.json "${OUTPUT_ROOT}"
      - uses: actions/upload-artifact@v4
        with:
          name: sealed-btcusdt-dataset-${{ github.sha }}-${{ github.run_id }}
          path: sealed-output/
          if-no-files-found: error
          retention-days: 90
          compression-level: 6
```

Implement the two small scripts as thin CLI wrappers only when quoting JSON fields in shell would be unsafe. Alternatively, use the Task 6 CLI directly and pass IDs through `$GITHUB_OUTPUT`; do not use `jq` to infer or mutate identities.

- [ ] **Step 4: Explicitly ignore generated output**

Add:

```gitignore
# Sealed historical-validation workflow evidence
data/historical-validation/
data/strategy-studies/
```

- [ ] **Step 5: Run contract tests and commit**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_workflows.py -q
git add .github/workflows/sealed-btcusdt-dataset.yml .gitignore tests/acceptance/test_sealed_historical_validation_workflows.py scripts/
git commit -m "ci: add sealed BTCUSDT dataset workflow"
```

---

### Task 8: Add the manually dispatched Stage 2 sealed-study workflow

**Files:**
- Create: `.github/workflows/sealed-btcusdt-study.yml`
- Modify: `tests/acceptance/test_sealed_historical_validation_workflows.py`

**Interfaces:**
- Inputs: exact Stage 1 run ID, artifact name, dataset ID, and source commit.
- Produces:
  - pre-final artifact;
  - durable receipt artifact;
  - final study artifact or `INCONCLUSIVE` evidence;
  - compact safe job summary.

- [ ] **Step 1: Extend contract tests for narrow dispatch inputs**

Assert exact inputs:

```yaml
source_commit:
  required: true
  type: string
dataset_run_id:
  required: true
  type: string
dataset_artifact_name:
  required: true
  type: string
dataset_id:
  required: true
  type: string
```

Reject symbol, dates, arbitrary config, command, output path, or strategy parameter inputs.

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/acceptance/test_sealed_historical_validation_workflows.py -q`

- [ ] **Step 3: Implement four jobs with explicit barriers**

1. `validate-dataset`
   - checkout `inputs.source_commit`;
   - download Stage 1 artifact with `actions/download-artifact@v4`, `run-id`, and GitHub token;
   - verify the handoff, commit, run ID, artifact inventory, and dataset ID;
   - upload a normalized validated-dataset artifact for the current run.

2. `prepare`
   - download validated dataset;
   - run `strategy-prepare`;
   - independently verify pre-final evidence;
   - upload `sealed-pre-final-${{ github.run_id }}`.

3. `authorize-final`
   - download pre-final evidence;
   - run `strategy-authorize-final` with `${{ github.run_id }}` and `${{ github.run_attempt }}`;
   - upload `sealed-final-access-${{ github.run_id }}` with `overwrite: false`;
   - this job must not load final-test rows.

4. `finalize`
   - require all previous jobs;
   - download dataset, pre-final, and receipt artifacts;
   - reject when receipt attempt differs from `${{ github.run_attempt }}`;
   - run `strategy-finalize`;
   - run provider-free `strategy-replay` and `strategy-verify`;
   - upload `sealed-candidate-study-${{ github.run_id }}` with `if: always()`;
   - emit `INCONCLUSIVE` evidence when final access occurred but completion evidence is missing.

Use `concurrency`:

```yaml
concurrency:
  group: sealed-btcusdt-study
  cancel-in-progress: false
```

This prevents concurrent sealed evaluations but does not treat cancellation as a safe retry.

- [ ] **Step 4: Enforce rerun rejection**

The `authorize-final` job must reject `github.run_attempt != 1`. The `finalize` job must require the receipt attempt to equal the current attempt. A rerun therefore cannot reopen the final partition. Exact resume occurs only through the provider-free `strategy-resume` command after complete immutable final outputs exist.

- [ ] **Step 5: Run contract tests and commit**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_workflows.py -q
git add .github/workflows/sealed-btcusdt-study.yml tests/acceptance/test_sealed_historical_validation_workflows.py
git commit -m "ci: add sealed candidate study workflow"
```

---

### Task 9: Extend replay and independent verification for the new evidence chain

**Files:**
- Modify: `src/gemini_trading/strategy/replay.py`
- Modify: `src/gemini_trading/strategy/verification.py`
- Modify: `tests/unit/strategy/test_strategy_verification.py`
- Modify: `tests/integration/test_strategy_replay_without_network.py`
- Modify: `tests/regression/test_tampered_strategy_artifacts.py`

**Interfaces:**
- Produces verification checks:
  - `dataset_handoff_verified`
  - `pre_final_identity_verified`
  - `durable_final_access_verified`
  - `single_final_access_verified`
  - `exact_resume_policy_verified`
- Consumes: Tasks 2–5.

- [ ] **Step 1: Write failing verification tests**

Add cases for:

- missing handoff reference;
- wrong handoff inventory root;
- changed pre-final ID;
- missing receipt;
- wrong run attempt;
- second receipt;
- receipt written after final output timestamp field ordering is claimed;
- final output tamper;
- provider construction during replay.

- [ ] **Step 2: Confirm RED**

Run:

```bash
uv run pytest tests/unit/strategy/test_strategy_verification.py tests/integration/test_strategy_replay_without_network.py tests/regression/test_tampered_strategy_artifacts.py -q
```

- [ ] **Step 3: Verify the entire identity chain**

The final verifier must establish:

```text
source commit
  -> verified dataset handoff inventory root
  -> dataset ID
  -> policy/config/split identities
  -> pre-final ID
  -> durable receipt ID and one access
  -> final experiment evidence
  -> 22-file study result ID
```

No verification check may be inferred from a status string alone; every referenced byte sequence and SHA-256 must be recomputed.

- [ ] **Step 4: Restrict exact resume**

`StrategyStudyReplayService` may package, replay, compare, or upload already-complete final outputs. It must never fit models, regenerate final predictions, rerun final cases, or call a market-data provider.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/strategy/test_strategy_verification.py tests/integration/test_strategy_replay_without_network.py tests/regression/test_tampered_strategy_artifacts.py -q
git add src/gemini_trading/strategy/replay.py src/gemini_trading/strategy/verification.py tests/unit/strategy/test_strategy_verification.py tests/integration/test_strategy_replay_without_network.py tests/regression/test_tampered_strategy_artifacts.py
git commit -m "feat: verify sealed historical evidence chain"
```

---

### Task 10: Add deterministic end-to-end acceptance without opening real history

**Files:**
- Modify: `tests/integration/test_sealed_historical_validation.py`
- Create: `tests/acceptance/test_sealed_historical_validation_end_to_end.py`
- Modify: `tests/candidate_strategy_e2e_worker.py`

**Interfaces:**
- Produces a fixture-based proof of Stage 1 packaging, Stage 2 preparation, one durable access, finalization, replay, verification, and tamper rejection.
- Does not use Binance network or claim profitability.

- [ ] **Step 1: Build a deterministic synthetic acceptance fixture**

Use `calendar_candles()` with sufficient synthetic dates to exercise the final boundary but mark `real_seven_year_run_claimed: false`. Build a verified local dataset through production writers rather than mocking the dataset manifest.

- [ ] **Step 2: Run the complete two-stage path twice in separate roots**

Assert:

- identical dataset ID;
- identical handoff bytes and inventory root after normalizing informational workflow IDs where required by the schema;
- identical pre-final ID;
- identical study and result IDs;
- identical 22 final file hashes;
- one receipt per isolated run;
- no network/provider call during preparation replay or study replay.

- [ ] **Step 3: Add interruption scenarios**

Test:

1. failure before receipt — correction is rerunnable;
2. failure while persisting receipt — final loader is never called;
3. failure after receipt but before final outputs — classification path is `INCONCLUSIVE`;
4. complete final outputs plus failed upload — exact resume allows packaging/upload only;
5. changed run attempt — fresh final evaluation is rejected.

- [ ] **Step 4: Run focused acceptance**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_end_to_end.py -q
```

Expected: all pass with no live API marker enabled.

- [ ] **Step 5: Commit Task 10**

```bash
git add tests/integration/test_sealed_historical_validation.py tests/acceptance/test_sealed_historical_validation_end_to_end.py tests/candidate_strategy_e2e_worker.py
git commit -m "test: prove sealed historical validation end to end"
```

---

### Task 11: Add operator documentation and documentation acceptance

**Files:**
- Create: `docs/operations/sealed-btcusdt-historical-validation.md`
- Create: `reports/verification/sealed-btcusdt-historical-validation-progress.md`
- Create: `tests/acceptance/test_sealed_historical_validation_documentation.py`
- Modify: `README.md`

**Interfaces:**
- Documents exact implementation and operating sequence.
- Consumed by human review before real workflow dispatch.

- [ ] **Step 1: Write failing documentation acceptance tests**

Require the operator guide to contain:

- exact fixed window;
- exact workflow names;
- exact dispatch inputs;
- Stage 1 inspection procedure;
- required Issue #22 approval comment before Stage 2;
- final-test access semantics;
- rerun prohibition;
- exact-resume restriction;
- artifact retention warning;
- independent download and hash verification;
- result semantics;
- safety and non-authorization language.

- [ ] **Step 2: Confirm RED**

Run: `uv run pytest tests/acceptance/test_sealed_historical_validation_documentation.py -q`

- [ ] **Step 3: Write the operator guide**

Include the exact sequence:

1. merge implementation through protected `main`;
2. verify exact merged-main SHA;
3. dispatch `Sealed BTCUSDT Dataset` against that SHA;
4. download and independently verify Stage 1 artifact;
5. record source SHA, run ID, artifact name, run ID, dataset ID, candle count, and inventory root on Issue #22;
6. obtain explicit approval for those exact identities;
7. dispatch `Sealed BTCUSDT Study` once;
8. download receipt and study artifacts immediately;
9. replay and independently verify offline;
10. create a separate compact closure-report PR;
11. close Issue #22 only after exact verification.

- [ ] **Step 4: Update README and progress report**

State that implementation exists but no real historical result exists until the two workflows complete and artifacts verify.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/acceptance/test_sealed_historical_validation_documentation.py -q
git add docs/operations/sealed-btcusdt-historical-validation.md reports/verification/sealed-btcusdt-historical-validation-progress.md tests/acceptance/test_sealed_historical_validation_documentation.py README.md
git commit -m "docs: add sealed historical validation operations"
```

---

### Task 12: Run cumulative implementation verification and prepare PR #23 for review

**Files:**
- Modify: PR #23 body
- Modify: `reports/verification/sealed-btcusdt-historical-validation-progress.md` with observed head and run IDs only after they exist.

**Interfaces:**
- Produces one exact reviewed implementation head eligible for protected merge.

- [ ] **Step 1: Run the complete local quality suite**

```bash
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run python -m build
uv run pip-audit
uv run pre-commit run --all-files
```

Expected: all pass; bounded live API tests remain skipped unless explicitly enabled.

- [ ] **Step 2: Prove generated evidence is untracked**

```bash
git ls-files data/raw data/canonical data/research data/strategy-studies data/historical-validation
```

Expected: no output.

- [ ] **Step 3: Review the cumulative diff**

Verify no strategy thresholds, feature definitions, labels, model settings, baselines, gates, or configuration values changed except the minimum evaluator refactor required for phase isolation.

- [ ] **Step 4: Push and wait for protected CI**

Record exact PR head and CI run. Required checks: `quality` and `gitleaks`.

- [ ] **Step 5: Update PR #23**

The PR body must list:

- exact fixed scope;
- tasks completed;
- focused acceptance results;
- exact reviewed head;
- exact CI run;
- proof that real Stage 1 and Stage 2 have not yet run;
- `RESEARCH_ONLY` boundary;
- Issue #22 remains open.

- [ ] **Step 6: Commit any report-only update and rerun exact-head CI**

Do not merge an unverified report update.

---

### Task 13: Merge implementation and verify the exact merged-main SHA

**Files:**
- Temporary verification workflow or PR only when required by connector limitations.
- Update Issue #22 and PR #23 with exact evidence.

**Interfaces:**
- Produces exact merged-main implementation SHA approved for the real Stage 1 workflow.

- [ ] **Step 1: Merge through protected `main` with expected head SHA**

Use the repository-supported merge method and pin the expected reviewed head.

- [ ] **Step 2: Verify exact merged-main**

The exact merge SHA must pass:

- frozen sync;
- Ruff format and lint;
- strict Pyright;
- complete pytest;
- build;
- pip-audit;
- tracked-file policy;
- detect-secrets;
- workflow contract tests;
- historical-validation CLI help surfaces;
- Gitleaks;
- clean tree and unchanged exact HEAD.

- [ ] **Step 3: Record the approved operational SHA on Issue #22**

State that only this SHA is authorized for Stage 1. Do not authorize Stage 2 yet.

---

### Task 14: Execute and independently verify Stage 1

**Files:**
- No source changes.
- Update Issue #22 comment with observed identities.

**Interfaces:**
- Produces one verified dataset artifact and exact approved dataset ID.

- [ ] **Step 1: Dispatch `Sealed BTCUSDT Dataset` against exact merged main**

Because the available GitHub connector does not expose workflow dispatch, use the GitHub Actions UI:

```text
Actions -> Sealed BTCUSDT Dataset -> Run workflow -> main
```

The workflow itself asserts the exact checked-out SHA. Do not use a newer `main` commit without a new approval comment.

- [ ] **Step 2: Inspect job steps**

Require successful ingestion, replay, independent verification, handoff construction, and artifact upload.

- [ ] **Step 3: Download the artifact immediately**

Independently recompute the inventory and handoff hashes with the repository CLI.

- [ ] **Step 4: Record exact identities on Issue #22**

Record:

- source commit;
- Stage 1 workflow run ID and attempt;
- artifact name and artifact ID;
- run ID;
- dataset ID;
- candle count;
- first and last open timestamps;
- inventory root SHA-256;
- replay and verification checks.

- [ ] **Step 5: Obtain explicit approval for Stage 2 exact inputs**

Stage 2 must remain undispatched until those identities are approved in Issue #22.

---

### Task 15: Execute the sealed Stage 2 exactly once

**Files:**
- No source changes during operation.
- Update Issue #22 with observed receipt and study identities.

**Interfaces:**
- Produces one final classification and immutable study evidence.

- [ ] **Step 1: Dispatch `Sealed BTCUSDT Study` with approved exact inputs**

Use only the approved source commit, Stage 1 run ID, artifact name, and dataset ID.

- [ ] **Step 2: Confirm pre-final completion before access**

The `validate-dataset` and `prepare` jobs must pass. Stop if any required development control is absent.

- [ ] **Step 3: Preserve the durable receipt**

After `authorize-final` succeeds, immediately download the receipt artifact. From that point, no rerun, threshold change, code change, or new final evaluation is permitted.

- [ ] **Step 4: Observe final outcome without intervention**

Valid outcomes are `PASS`, `REJECTED`, or `INCONCLUSIVE`. A failed strategy gate is not an infrastructure defect and must not be rerun.

- [ ] **Step 5: Download all final artifacts immediately**

Preserve the receipt, pre-final evidence, study evidence, job logs, and artifact metadata.

- [ ] **Step 6: Replay and independently verify offline**

Use only immutable downloaded evidence and the exact source commit. No provider may be constructed.

- [ ] **Step 7: Record identities and limitations on Issue #22**

Record dataset ID, pre-final ID, receipt ID, study ID, study-result ID, gate counts, classification, verification checks, and artifact root hashes.

---

### Task 16: Commit the compact closure report and close Issue #22

**Files:**
- Create: `reports/verification/sealed-btcusdt-historical-validation-final.md`
- Modify: `reports/verification/sealed-btcusdt-historical-validation-progress.md`
- Modify: `README.md`

**Interfaces:**
- Produces permanent compact repository evidence without raw data or generated study arrays.

- [ ] **Step 1: Write the compact final report**

Include exact source SHA, workflow runs, artifact IDs, dataset ID, pre-final ID, receipt ID, study/result IDs, inventory roots, verification checks, gate counts, classification, and limitations.

- [ ] **Step 2: State the authority boundary**

For every outcome, state:

```text
RESEARCH_ONLY. No execution or capital authority is granted.
```

For `PASS`, state only that a separate paper-trading design gate may be proposed. For `REJECTED` or `INCONCLUSIVE`, preserve the outcome without tuning the sealed test.

- [ ] **Step 3: Open a separate closure-report PR**

Run the full CI suite and exact merged-main verification again.

- [ ] **Step 4: Close Issue #22 only after the closure report merges and verifies**

Use state reason `completed` only when both workflows and all independent verification succeeded. When final evidence is `INCONCLUSIVE`, the milestone may still be operationally completed, but the report must preserve the inconclusive research classification.

---

## Plan Self-Review

- Spec coverage: architecture, handoff, pre-final isolation, durable access, exact resume, workflows, testing, operation, artifact retention, and closure are each assigned to a task.
- Placeholder scan: the plan contains no unresolved implementation placeholders.
- Type consistency: `DatasetHandoffManifest`, `PreFinalArtifacts`, `FinalAccessIdentity`, `DurableFinalAccessReceipt`, `prepare_candidate_strategy_study()`, and `complete_candidate_strategy_study()` are named consistently across tasks.
- Scope: strategy policy, thresholds, labels, model settings, and promotion gates remain unchanged; the plan is limited to evidence transport, access control, evaluator phase separation, workflow operation, and verification.
