"""RED tests for Candidate v0.3 calibration-only entry selectivity."""

import importlib.util


def test_entry_selectivity_module_exists_before_behavior_is_implemented() -> None:
    assert importlib.util.find_spec("gemini_trading.strategy.entry_selectivity") is not None, (
        "Candidate v0.3 entry_selectivity module must exist"
    )
