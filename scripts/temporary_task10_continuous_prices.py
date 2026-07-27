"""Use one continuous deterministic price series on the fixed v4 timeline."""

from pathlib import Path


worker_path = Path("tests/candidate_strategy_e2e_worker.py")
worker = worker_path.read_text(encoding="utf-8")
old_worker = '''def synthetic_candidate_candles():
    """Return the deterministic synthetic Candidate acceptance candles."""

    return _synthetic_candles()
'''
new_worker = '''def synthetic_candidate_candles(count: int = 2250) -> tuple[Candle, ...]:
    """Return deterministic synthetic Candidate acceptance candles."""

    return _synthetic_candles(count)
'''
if worker.count(old_worker) != 1:
    raise SystemExit("unexpected synthetic candle helper structure")
worker_path.write_text(worker.replace(old_worker, new_worker, 1), encoding="utf-8")

integration_path = Path("tests/integration/test_sealed_historical_validation.py")
integration = integration_path.read_text(encoding="utf-8")
old_integration = '''    source_candles = synthetic_candidate_candles()
    if not source_candles:
        raise AssertionError("candidate fixture is empty")
    candles = tuple(
        replace(
            source_candles[index % len(source_candles)],
            instrument=fixed.instrument,
            timeframe=fixed.timeframe,
            open_time=fixed.open_time,
            close_time=fixed.close_time,
            source_provider=fixed.source_provider,
        )
        for index, fixed in enumerate(FIXED_CANDLES)
    )
'''
new_integration = '''    source_candles = synthetic_candidate_candles(EXPECTED_CANDLE_COUNT)
    candles = tuple(
        replace(
            source_candles[index],
            instrument=fixed.instrument,
            timeframe=fixed.timeframe,
            open_time=fixed.open_time,
            close_time=fixed.close_time,
            source_provider=fixed.source_provider,
        )
        for index, fixed in enumerate(FIXED_CANDLES)
    )
'''
if integration.count(old_integration) != 1:
    raise SystemExit("unexpected cycled price fixture structure")
integration_path.write_text(
    integration.replace(old_integration, new_integration, 1),
    encoding="utf-8",
)
