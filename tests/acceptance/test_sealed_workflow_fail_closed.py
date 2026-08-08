from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DATASET = _ROOT / ".github" / "workflows" / "sealed-btcusdt-dataset.yml"
_STUDY = _ROOT / ".github" / "workflows" / "sealed-btcusdt-study.yml"
_SHELL = "defaults:\n  run:\n    shell: bash --noprofile --norc -e -o pipefail {0}\n"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_sealed_workflow_tee_pipeline_propagates_command_failures() -> None:
    for path in (_DATASET, _STUDY):
        assert _SHELL in _text(path)


def test_dataset_replay_step_requires_completed_exact_identity() -> None:
    text = _text(_DATASET)
    start = text.index("      - name: Replay stored dataset evidence")
    end = text.index("      - name: Independently verify dataset", start)
    replay_step = text[start:end]

    assert 'payload.get("status") != "completed"' in replay_step
    assert 'payload.get("run_id") != os.environ["EXPECTED_RUN_ID"]' in replay_step
    assert 'payload.get("dataset_id") != os.environ["EXPECTED_DATASET_ID"]' in replay_step
