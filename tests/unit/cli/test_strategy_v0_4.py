"""Candidate v0.4 CLI identity tests."""

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from gemini_trading.cli import strategy
from gemini_trading.research.errors import InvalidExperimentConfigError

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_V0_4 = _PROJECT_ROOT / "tests" / "fixtures" / "strategy" / "candidate-v0.4-config.json"


def test_locked_candidate_v0_4_config_loads_exact_policy() -> None:
    assert _CONFIG_V0_4.is_file(), "Candidate v0.4 strategy fixture is missing"

    loaded = strategy.load_candidate_strategy_config(_CONFIG_V0_4)

    assert loaded.schema_version == "candidate-strategy-cli-v1"
    assert loaded.initial_cash == Decimal("10000")
    assert loaded.strategy_id == "candidate.multi_model.v0_4"
    assert loaded.policy_version == "candidate-multi-model-v0.4"
    assert loaded.simulation.promotable is True


def test_candidate_v0_4_config_rejects_cross_version_identity(tmp_path: Path) -> None:
    assert _CONFIG_V0_4.is_file(), "Candidate v0.4 strategy fixture is missing"
    payload = cast(dict[str, object], json.loads(_CONFIG_V0_4.read_text()))
    payload["strategy"] = {
        "id": "candidate.multi_model.v0_4",
        "policy_version": "candidate-multi-model-v0.3",
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(InvalidExperimentConfigError, match="policy version"):
        strategy.load_candidate_strategy_config(path)
