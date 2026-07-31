"""Acceptance gate for the sealed historical-validation operator guide."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "operations" / "sealed-btcusdt-historical-validation.md"
_README = _ROOT / "README.md"


def test_operator_guide_locks_scope_sequence_and_failure_policy() -> None:
    text = _GUIDE.read_text(encoding="utf-8")

    required = (
        "[2018-01-01T00:00:00Z, 2026-07-01T00:00:00Z)",
        "Sealed BTCUSDT Dataset",
        "Sealed BTCUSDT Candidate Study",
        "source_commit",
        "dataset_run_id",
        "dataset_artifact_name",
        "dataset_id",
        "Issue #22",
        "sealed-dataset-approved:<source-commit>:<dataset-run-id>:<dataset-id>",
        "sealed-final-access:<pre-final-id>",
        "comment author is the repository owner",
        "github-actions[bot]",
        "stable run-independent seal",
        "result is `INCONCLUSIVE`",
        "access receipt is written before final-test rows",
        "fresh final evaluation is prohibited",
        "Exact resume",
        "90 days",
        "Download the artifact immediately",
        "independently recompute",
        "PASS",
        "REJECTED",
        "INCONCLUSIVE",
        "RESEARCH_ONLY",
        "No classification authorizes execution or capital",
        "candle-dataset-v4",
        "exchange-closure-manifest-v3",
        "candle-exclusion-manifest-v1",
        "candle-segment-manifest-v1",
        "sealed-dataset-handoff-v4",
        "20 structurally valid partial-candle provider rows",
        "16 fully absent canonical opens",
        "36 unavailable canonical `4h` slots",
        "20 ordered exact exclusions",
        "21 maximal continuous segments",
        "18,582 completed canonical candles",
        "2018-01-01T00:00:00Z",
        "2026-06-30T20:00:00Z",
        "zero fully missing opens",
        "never inserts, forward-fills, interpolates, zero-fills",
        "Feature warm-up restarts",
        "noncash account or active order",
        "dataset-ingest",
        "dataset-replay",
        "dataset-verify",
        "Earlier v1-v3 datasets and handoffs are invalid",
        "completely new Stage 1 v4",
    )
    for phrase in required:
        assert phrase in text
    assert "candle-dataset-v3" not in text
    assert "exchange-closure-manifest-v2" not in text
    assert "18,617" not in text
    assert "(1, 1, 2)" not in text


def test_documentation_states_no_real_result_exists_before_operation() -> None:
    guide = _GUIDE.read_text(encoding="utf-8")
    readme = _README.read_text(encoding="utf-8")

    statement = "no real historical Candidate result"
    assert statement in guide
    assert statement in readme
    assert "does not prove future profitability" in guide
    assert "no credentials" in guide
    assert "no real-capital authorization" in guide
    assert "candle-dataset-v4" in readme
    assert "18,582" in readme
    assert "completely new Stage 1 v4" in readme
