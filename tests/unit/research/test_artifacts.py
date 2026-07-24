"""Tests for canonical research artifacts and immutable local persistence."""

import json
from pathlib import Path

import pytest
from test_metrics import known_config, known_evidence

from gemini_trading.research.artifacts import LocalResearchStore, build_artifacts
from gemini_trading.research.errors import ArtifactConflictError

_REQUIRED_ARTIFACTS = {
    "experiment-manifest.json",
    "simulation-config.json",
    "decisions.jsonl",
    "orders.jsonl",
    "rejections.jsonl",
    "fills.jsonl",
    "cash-ledger.jsonl",
    "account-series.jsonl",
    "trades.jsonl",
    "metrics.json",
    "verification.json",
    "result-manifest.json",
}


def test_identical_evidence_produces_byte_identical_artifacts() -> None:
    first = build_artifacts(known_evidence(), known_config())
    second = build_artifacts(known_evidence(), known_config())

    assert first == second
    assert first.result_id == second.result_id
    assert {name for name, _ in first.files} == _REQUIRED_ARTIFACTS


def test_result_manifest_contains_sorted_hashes_and_self_excluding_identity() -> None:
    artifacts = build_artifacts(known_evidence(), known_config())
    payload = json.loads(artifacts.artifact_bytes("result-manifest.json"))

    assert payload["schema_version"] == "research-result-v2"
    assert payload["experiment_id"] == artifacts.experiment_id
    assert payload["result_id"] == artifacts.result_id
    assert payload["terminal_status"] == "completed"
    assert payload["promotable"] is True
    assert payload["artifacts"] == sorted(payload["artifacts"], key=lambda item: item[0])
    assert "result-manifest.json" not in {item[0] for item in payload["artifacts"]}


def test_v2_trade_and_metric_artifacts_include_expanded_fields() -> None:
    artifacts = build_artifacts(known_evidence(), known_config())
    trade = json.loads(artifacts.artifact_bytes("trades.jsonl").decode("utf-8").strip())
    metrics = json.loads(artifacts.artifact_bytes("metrics.json"))

    assert {
        "entry_candle_index",
        "exit_candle_index",
        "hold_candles",
        "gross_return",
        "net_return",
    } <= set(trade)
    assert {
        "observed_periods",
        "annualized_geometric_return",
        "annualized_volatility",
        "downside_deviation",
        "sortino_ratio",
        "return_to_drawdown",
        "turnover",
        "exposure_adjusted_return",
        "profit_factor",
    } <= set(metrics)


def test_local_store_accepts_identical_rerun_and_rejects_conflicting_bytes(
    tmp_path: Path,
) -> None:
    artifacts = build_artifacts(known_evidence(), known_config())
    store = LocalResearchStore(tmp_path)

    first_paths = store.write(artifacts)
    second_paths = store.write(artifacts)
    assert first_paths == second_paths

    metrics_path = tmp_path / "data" / "research" / artifacts.experiment_id / "metrics.json"
    metrics_path.write_bytes(b"{}\n")

    with pytest.raises(ArtifactConflictError, match=r"metrics\.json"):
        store.write(artifacts)
