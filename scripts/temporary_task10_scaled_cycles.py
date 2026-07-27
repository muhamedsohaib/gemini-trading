"""Use smooth scale-adjusted repetitions of the proven synthetic price pattern."""

from pathlib import Path


worker_path = Path("tests/candidate_strategy_e2e_worker.py")
worker = worker_path.read_text(encoding="utf-8")
old_worker = '''def synthetic_candidate_candles(count: int = 2250) -> tuple[Candle, ...]:
    """Return deterministic synthetic Candidate acceptance candles."""

    return _synthetic_candles(count)
'''
new_worker = '''def synthetic_candidate_candles() -> tuple[Candle, ...]:
    """Return the deterministic synthetic Candidate acceptance candles."""

    return _synthetic_candles()
'''
if worker.count(old_worker) != 1:
    raise SystemExit("unexpected synthetic candle helper structure")
worker_path.write_text(worker.replace(old_worker, new_worker, 1), encoding="utf-8")

integration_path = Path("tests/integration/test_sealed_historical_validation.py")
integration = integration_path.read_text(encoding="utf-8")
old_integration = '''    source_candles = synthetic_candidate_candles(EXPECTED_CANDLE_COUNT)
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
new_integration = '''    source_candles = synthetic_candidate_candles()
    first_open = source_candles[0].open
    cycle_factor = source_candles[-1].close / first_open
    price_quantum = Decimal("0.01")
    candles = tuple(
        replace(
            source_candles[index % len(source_candles)],
            instrument=fixed.instrument,
            timeframe=fixed.timeframe,
            open_time=fixed.open_time,
            close_time=fixed.close_time,
            open=(
                source_candles[index % len(source_candles)].open
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            high=(
                source_candles[index % len(source_candles)].high
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            low=(
                source_candles[index % len(source_candles)].low
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            close=(
                source_candles[index % len(source_candles)].close
                * (cycle_factor ** (index // len(source_candles)))
            ).quantize(price_quantum),
            source_provider=fixed.source_provider,
        )
        for index, fixed in enumerate(FIXED_CANDLES)
    )
'''
if integration.count(old_integration) != 1:
    raise SystemExit("unexpected continuous price fixture structure")
integration_path.write_text(
    integration.replace(old_integration, new_integration, 1),
    encoding="utf-8",
)
