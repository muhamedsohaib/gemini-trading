from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement, found {count}")
    return text.replace(old, new)


def apply(root: Path) -> None:
    replay_path = root / "src/gemini_trading/data/ingestion/replay.py"
    replay = replay_path.read_text(encoding="utf-8")
    replay = replace_once(replay, "import hashlib\n", "import hashlib\nimport json\n", "json import")
    replay = replace_once(
        replay,
        "from typing import Protocol\n",
        "from typing import Protocol, cast\n",
        "cast import",
    )
    replay = replace_once(
        replay,
        "\n    def write_provenance(\n",
        "\n    def read_provenance(self, dataset_id: str, run_id: str) -> bytes: ...\n\n    def write_provenance(\n",
        "replay store read protocol",
    )
    helper_anchor = '''def _utc_milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)
'''
    helper = '''def _utc_milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def _existing_provenance_created_at(raw: bytes) -> datetime:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MarketDataError("existing dataset provenance is invalid") from None
    if not isinstance(loaded, dict):
        raise MarketDataError("existing dataset provenance is invalid")
    mapping = cast(dict[object, object], loaded)
    created_at = mapping.get("created_at")
    if not isinstance(created_at, str):
        raise MarketDataError("existing dataset provenance is invalid")
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        raise MarketDataError("existing dataset provenance is invalid") from None


def _replay_provenance_bytes(
    canonical_store: ReplayCanonicalStore,
    *,
    dataset_id: str,
    run_id: str,
    page_hashes: tuple[str, ...],
    retrieval_manifest_sha256: str,
    clock: Callable[[], datetime],
) -> bytes:
    try:
        existing = canonical_store.read_provenance(dataset_id, run_id)
    except FileNotFoundError:
        provenance = build_provenance(
            schema_version=_PROVENANCE_SCHEMA_VERSION,
            dataset_id=dataset_id,
            run_id=run_id,
            page_hashes=page_hashes,
            retrieval_manifest_sha256=retrieval_manifest_sha256,
            linked=True,
            created_at=clock(),
        )
        return serialize_provenance(provenance)
    except OSError:
        raise MarketDataError("replay failed to read existing provenance") from None

    try:
        expected = build_provenance(
            schema_version=_PROVENANCE_SCHEMA_VERSION,
            dataset_id=dataset_id,
            run_id=run_id,
            page_hashes=page_hashes,
            retrieval_manifest_sha256=retrieval_manifest_sha256,
            linked=True,
            created_at=_existing_provenance_created_at(existing),
        )
    except ValueError:
        raise MarketDataError("existing dataset provenance is invalid") from None
    if serialize_provenance(expected) != existing:
        raise MarketDataError("existing dataset provenance does not match replay")
    return existing
'''
    replay = replace_once(replay, helper_anchor, helper, "provenance helper")
    provenance_start = replay.index("        provenance = build_provenance(")
    provenance_end = replay.index("        return IngestionResult(", provenance_start)
    replay = (
        replay[:provenance_start]
        + '''        provenance_bytes = _replay_provenance_bytes(
            self.canonical_store,
            dataset_id=dataset_manifest.dataset_id,
            run_id=run_id,
            page_hashes=manifest.page_hashes,
            retrieval_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            clock=self.clock,
        )
        provenance_path = self.canonical_store.write_provenance(
            dataset_manifest.dataset_id,
            run_id,
            provenance_bytes,
        )
'''
        + replay[provenance_end:]
    )
    replay_path.write_text(replay, encoding="utf-8")

    dataset_path = root / ".github/workflows/sealed-btcusdt-dataset.yml"
    dataset = dataset_path.read_text(encoding="utf-8")
    dataset = replace_once(
        dataset,
        "permissions:\n  contents: read\n\njobs:\n",
        "permissions:\n  contents: read\n\ndefaults:\n  run:\n    shell: bash -o pipefail {0}\n\njobs:\n",
        "dataset pipefail default",
    )
    step_start = dataset.index("      - name: Replay stored dataset evidence\n")
    step_end = dataset.index("      - name: Independently verify dataset\n", step_start)
    replay_step = '''      - name: Replay stored dataset evidence
        env:
          EXPECTED_RUN_ID: ${{ steps.ingest.outputs.run_id }}
          EXPECTED_DATASET_ID: ${{ steps.ingest.outputs.dataset_id }}
        run: |
          uv run gemini-trading research dataset-replay \\
            --run-id "${EXPECTED_RUN_ID}" \\
            --output-root "${OUTPUT_ROOT}" | tee "${RUNNER_TEMP}/replay.json"
          python - <<'PY'
          import json
          import os
          from pathlib import Path

          payload = json.loads((Path(os.environ["RUNNER_TEMP"]) / "replay.json").read_text())
          if payload.get("status") != "completed":
              raise SystemExit("dataset replay did not complete")
          if payload.get("run_id") != os.environ["EXPECTED_RUN_ID"]:
              raise SystemExit("dataset replay run identity mismatch")
          if payload.get("dataset_id") != os.environ["EXPECTED_DATASET_ID"]:
              raise SystemExit("dataset replay dataset identity mismatch")
          PY
'''
    dataset = dataset[:step_start] + replay_step + dataset[step_end:]
    dataset_path.write_text(dataset, encoding="utf-8")

    study_path = root / ".github/workflows/sealed-btcusdt-study.yml"
    study = study_path.read_text(encoding="utf-8")
    study = replace_once(
        study,
        "concurrency:\n  group: sealed-btcusdt-study\n  cancel-in-progress: false\n\njobs:\n",
        "concurrency:\n  group: sealed-btcusdt-study\n  cancel-in-progress: false\n\ndefaults:\n  run:\n    shell: bash -o pipefail {0}\n\njobs:\n",
        "study pipefail default",
    )
    study_path.write_text(study, encoding="utf-8")

    test_path = root / "tests/acceptance/test_sealed_workflow_fail_closed.py"
    test = test_path.read_text(encoding="utf-8")
    test = replace_once(
        test,
        '''def test_every_sealed_workflow_tee_pipeline_propagates_command_failures() -> None:
    for path in (_DATASET, _STUDY):
        text = _text(path)
        assert text.count("set -o pipefail") == text.count("| tee ")
''',
        '''def test_every_sealed_workflow_tee_pipeline_propagates_command_failures() -> None:
    for path in (_DATASET, _STUDY):
        text = _text(path)
        assert "defaults:\\n  run:\\n    shell: bash -o pipefail {0}\\n" in text
''',
        "workflow pipefail assertion",
    )
    test_path.write_text(test, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_stage1_replay_fix.py TARGET_ROOT")
    apply(Path(sys.argv[1]).resolve())
