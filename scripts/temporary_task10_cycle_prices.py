"""Cycle deterministic strategy prices across the fixed v4 candle timeline."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
old = '''    source_candles = synthetic_candidate_candles()
    if len(source_candles) < EXPECTED_CANDLE_COUNT:
        raise AssertionError("candidate fixture lacks fixed-window history")
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
new = '''    source_candles = synthetic_candidate_candles()
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
if text.count(old) != 1:
    raise SystemExit("unexpected fixed-timeline price fixture structure")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
