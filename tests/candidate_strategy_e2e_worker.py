"""Subprocess worker for deterministic Candidate v0.1 end-to-end acceptance."""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import urllib.request
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import NoReturn, cast
from unittest.mock import patch

from gemini_trading.cli import strategy
from gemini_trading.cli.main import main
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.artifacts import LocalResearchStore
from gemini_trading.research.replay import ReplayService
from gemini_trading.strategy.artifacts import (
    REQUIRED_STUDY_ARTIFACT_NAMES,
    LocalStrategyStudyStore,
)
from gemini_trading.strategy.evaluator import reconstruct_study_strategy
from gemini_trading.strategy.verification import (
    StrategyStudyVerificationResult,
    StrategyStudyVerificationService,
)

_CODE_COMMIT = "a" * 40


def _synthetic_candles(count: int = 2250) -> tuple[Candle, ...]:
    instrument = Instrument("BTCUSDT", "BTC", "USDT")
    start = datetime(2024, 1, 1, tzinfo=UTC)
    price = Decimal("30000")
    candles: list[Candle] = []
    for index in range(count):
        phase = (index // 36) % 4
        if phase == 0:
            candle_return = Decimal("0.0050")
        elif phase == 1:
            candle_return = Decimal("-0.0042")
        elif phase == 2:
            candle_return = Decimal("0.0025") if index % 6 < 3 else Decimal("-0.0010")
        else:
            candle_return = Decimal("-0.0025") if index % 6 < 3 else Decimal("0.0010")
        opening = price
        close = (opening * (Decimal("1") + candle_return)).quantize(Decimal("0.01"))
        wick = (opening * Decimal("0.002")).quantize(Decimal("0.01"))
        opened = start + timedelta(hours=4 * index)
        candles.append(
            Candle(
                instrument=instrument,
                timeframe=Timeframe.H4,
                open_time=opened,
                close_time=opened + timedelta(hours=4) - timedelta(milliseconds=1),
                open=opening,
                high=max(opening, close) + wick,
                low=min(opening, close) - wick,
                close=close,
                volume=Decimal("100000") + Decimal(index * 10),
                completed=True,
                source_provider="binance_spot",
            )
        )
        price = close
    return tuple(candles)


def _store_dataset(root: Path) -> str:
    candles = _synthetic_candles()
    canonical_bytes = serialize_candles(candles)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=Timeframe.H4,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time + timedelta(milliseconds=1),
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return manifest.dataset_id


def _forbid_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("Candidate acceptance attempted provider or network access")


def _fixed_commit(_root: Path) -> str:
    return _CODE_COMMIT


def _invoke(argv: list[str]) -> dict[str, object]:
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"command failed: {stderr.getvalue()}")
    if stderr.getvalue() != "":
        raise AssertionError("successful command emitted stderr")
    loaded: object = json.loads(stdout.getvalue())
    if not isinstance(loaded, dict):
        raise AssertionError("command output is not a JSON object")
    return cast(dict[str, object], loaded)


def _evaluate_args(dataset_id: str, root: Path, project_root: Path, config: Path) -> list[str]:
    return [
        "research",
        "strategy-evaluate",
        "--dataset-id",
        dataset_id,
        "--config",
        str(config),
        "--project-root",
        str(project_root),
        "--output-root",
        str(root),
    ]


def _artifact_hashes(store: LocalStrategyStudyStore, study_id: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (name, hashlib.sha256(store.read_artifact(study_id, name)).hexdigest())
        for name in REQUIRED_STUDY_ARTIFACT_NAMES
    )


@dataclass(frozen=True, slots=True)
class _VerifiedResearchResult:
    result_id: str


def run(root: Path, project_root: Path, config: Path) -> dict[str, object]:
    dataset_id = _store_dataset(root)
    strategy.resolve_clean_git_commit = _fixed_commit
    with (
        patch.object(socket, "create_connection", _forbid_network),
        patch.object(urllib.request, "urlopen", _forbid_network),
        patch.object(BinanceSpotProvider, "__init__", _forbid_network),
    ):
        first = _invoke(_evaluate_args(dataset_id, root, project_root, config))
        study_id = cast(str, first["study_id"])
        store = LocalStrategyStudyStore(root)
        first_hashes = _artifact_hashes(store, study_id)
        second = _invoke(_evaluate_args(dataset_id, root, project_root, config))
        second_hashes = _artifact_hashes(store, study_id)
        if first != second or first_hashes != second_hashes:
            raise AssertionError("repeated Candidate evaluation changed deterministic evidence")

        raw_experiments = store.read_artifact(study_id, "experiments.jsonl").decode("utf-8")
        experiment_rows = tuple(
            cast(dict[str, object], json.loads(line)) for line in raw_experiments.splitlines()
        )
        first_experiment_id = cast(str, experiment_rows[0]["experiment_id"])
        replayed_experiment = ReplayService(
            canonical_store=LocalImmutableStore(root),
            research_store=LocalResearchStore(root),
            current_commit_resolver=lambda: _CODE_COMMIT,
            strategy_reconstructor=reconstruct_study_strategy,
        ).replay(first_experiment_id)
        if replayed_experiment.experiment_id != first_experiment_id:
            raise AssertionError("referenced research experiment did not replay")

        replayed = _invoke(
            [
                "research",
                "strategy-replay",
                "--study-id",
                study_id,
                "--project-root",
                str(project_root),
                "--output-root",
                str(root),
            ]
        )
        if replayed != first:
            raise AssertionError("strategy-study replay summary changed")

        def verify_research_reference(experiment_id: str) -> _VerifiedResearchResult:
            raw = LocalResearchStore(root).read_artifact(experiment_id, "result-manifest.json")
            mapping = cast(dict[str, object], json.loads(raw))
            return _VerifiedResearchResult(cast(str, mapping["result_id"]))

        class _BoundedVerifier:
            def __init__(self, **kwargs: object) -> None:
                commit_resolver = cast(Callable[[], str], kwargs["current_commit_resolver"])
                self._service = StrategyStudyVerificationService(
                    root=cast(Path, kwargs["root"]),
                    current_commit_resolver=commit_resolver,
                    research_verifier=verify_research_reference,
                    research_strategy_reconstructor=reconstruct_study_strategy,
                )

            def verify(self, supplied_study_id: str) -> StrategyStudyVerificationResult:
                return self._service.verify(supplied_study_id)

        strategy.StrategyStudyVerificationService = _BoundedVerifier  # type: ignore[assignment]
        verified = _invoke(
            [
                "research",
                "strategy-verify",
                "--study-id",
                study_id,
                "--project-root",
                str(project_root),
                "--output-root",
                str(root),
            ]
        )
        checks = cast(list[object], verified["checks"])
        if checks != sorted(checks):
            raise AssertionError("verification checks are not sorted")
        if "replay_equivalent" not in checks or "referenced_experiments_verified" not in checks:
            raise AssertionError("verification checks are incomplete")

        artifact_path = root / "data" / "strategy-studies" / study_id / "feature-registry.json"
        artifact_path.write_bytes(b"{}\n")
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            tampered_code = main(
                [
                    "research",
                    "strategy-verify",
                    "--study-id",
                    study_id,
                    "--project-root",
                    str(project_root),
                    "--output-root",
                    str(root),
                ]
            )
        if tampered_code != 2 or stdout.getvalue() != "" or "Traceback" in stderr.getvalue():
            raise AssertionError("tampered study did not fail closed safely")

    return {
        "artifact_hashes": [list(item) for item in first_hashes],
        "checks": checks,
        "classification": first["classification"],
        "promotable": first["promotable"],
        "study_id": first["study_id"],
        "study_result_id": first["study_result_id"],
        "tamper_rejected": True,
    }


def main_worker() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: worker ROOT PROJECT_ROOT CONFIG")
    warnings.filterwarnings("ignore", category=FutureWarning)
    result = run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_worker())
