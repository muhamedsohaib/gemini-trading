"""Contract tests for the two manually dispatched sealed workflows."""

from pathlib import Path
from typing import cast

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_DATASET = _ROOT / ".github" / "workflows" / "sealed-btcusdt-dataset.yml"
_STUDY = _ROOT / ".github" / "workflows" / "sealed-btcusdt-study.yml"


def _workflow(path: Path) -> dict[str, object]:
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    mapping = cast(dict[object, object], loaded)
    return {str(key): value for key, value in mapping.items()}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dataset_workflow_is_manual_fixed_scope_and_least_privilege() -> None:
    workflow = _workflow(_DATASET)
    text = _text(_DATASET)

    assert workflow["on"] == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read"}
    jobs = cast(dict[str, object], workflow["jobs"])
    assert set(jobs) == {"dataset"}
    assert "fetch-depth: 0" in text
    assert 'python-version: "3.12"' in text
    assert 'version: "0.11.25"' in text
    assert "--symbol BTCUSDT" in text
    assert "--base-asset BTC" in text
    assert "--quote-asset USDT" in text
    assert "--interval 4h" in text
    assert "--start 2018-01-01T00:00:00Z" in text
    assert "--end 2026-07-01T00:00:00Z" in text
    assert text.index("market-data ingest") < text.index("market-data replay")
    assert text.index("market-data replay") < text.index("market-data verify")
    assert text.index("market-data verify") < text.index("strategy-handoff")
    assert "sealed-btcusdt-dataset-${{ github.sha }}-${{ github.run_id }}" in text
    assert "retention-days: 90" in text
    assert "secrets." not in text
    assert "workflow_dispatch:\n    inputs:" not in text


def test_study_workflow_has_exact_narrow_inputs_and_barriers() -> None:
    workflow = _workflow(_STUDY)
    text = _text(_STUDY)
    trigger = cast(dict[str, object], workflow["on"])
    dispatch = cast(dict[str, object], trigger["workflow_dispatch"])
    inputs = cast(dict[str, object], dispatch["inputs"])

    assert set(inputs) == {
        "source_commit",
        "dataset_run_id",
        "dataset_artifact_name",
        "dataset_id",
    }
    for value in inputs.values():
        definition = cast(dict[str, object], value)
        assert definition == {"required": True, "type": "string"}
    forbidden = {
        "symbol",
        "start",
        "end",
        "interval",
        "config",
        "command",
        "output_root",
        "strategy",
    }
    assert forbidden.isdisjoint(inputs)
    assert workflow["concurrency"] == {
        "group": "sealed-btcusdt-study",
        "cancel-in-progress": False,
    }
    jobs = cast(dict[str, object], workflow["jobs"])
    assert set(jobs) == {
        "validate-dataset",
        "prepare",
        "authorize-final",
        "finalize",
    }
    assert 'test "${GITHUB_RUN_ATTEMPT}" = "1"' in text
    assert "receipt.identity.workflow_run_attempt" in text
    assert "receipt.identity.workflow_run_id" in text
    assert "strategy-prepare" in text
    assert "strategy-authorize-final" in text
    assert "strategy-finalize" in text
    assert "strategy-replay" in text
    assert "strategy-verify" in text
    assert "if: always()" in text
    assert "sealed-pre-final-${{ github.run_id }}" in text
    assert "sealed-final-access-${{ github.run_id }}" in text
    assert "sealed-candidate-study-${{ github.run_id }}" in text
    assert "overwrite: false" in text
    assert "retention-days: 90" in text
    assert "secrets.GITHUB_TOKEN" in text
    assert "api.binance.com" not in text
