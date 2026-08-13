from pathlib import Path

execution = Path("src/gemini_trading/strategy/qualification_execution_v0_3.py")
text = execution.read_text()
anchor = '_SPECIALIST_IDS = ("trend.specialist.v1", "mean_reversion.specialist.v1")\n'
addition = '''_SPECIALIST_IDS = ("trend.specialist.v1", "mean_reversion.specialist.v1")
V03_INITIAL_CASH = Decimal("10000")


def locked_v0_3_simulation_config() -> SimulationConfig:
    """Return the exact frozen simulation/cost assumptions for Candidate v0.3."""

    return SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.000001"),
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        max_volume_participation=Decimal("0.01"),
    )


def validate_v0_3_qualification_parameters(
    simulation: SimulationConfig,
    initial_cash: Decimal,
) -> None:
    """Fail closed unless Candidate v0.3 uses the exact preregistered economics."""

    if simulation != locked_v0_3_simulation_config():
        raise StudyArtifactError("v0.3 qualification simulation configuration changed")
    if initial_cash != V03_INITIAL_CASH:
        raise StudyArtifactError("v0.3 qualification initial cash changed")
'''
if "def locked_v0_3_simulation_config()" not in text:
    text = text.replace(anchor, addition)
old = '''    if not simulation.promotable:
        raise StudyArtifactError("v0.3 qualification requires promotable simulation evidence")
    if not initial_cash.is_finite() or initial_cash <= _ZERO:
        raise StudyArtifactError("v0.3 qualification initial cash must be finite and positive")
'''
text = text.replace(old, "    validate_v0_3_qualification_parameters(simulation, initial_cash)\n")
old_exports = '''    "AggregatePathMetrics",
    "V03QualificationRun",
    "aggregate_path_metrics",
    "execute_candidate_v0_3_qualification",
    "qualification_case_ids",
'''
new_exports = '''    "AggregatePathMetrics",
    "V03_INITIAL_CASH",
    "V03QualificationRun",
    "aggregate_path_metrics",
    "execute_candidate_v0_3_qualification",
    "locked_v0_3_simulation_config",
    "qualification_case_ids",
    "validate_v0_3_qualification_parameters",
'''
text = text.replace(old_exports, new_exports)
execution.write_text(text)

verification = Path("src/gemini_trading/strategy/qualification_verification_v0_3.py")
text = verification.read_text()
text = text.replace(
    "from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes\n",
    "from gemini_trading.research.config import serialize_simulation_config\n"
    "from gemini_trading.research.serialization import canonical_json_bytes, canonical_jsonl_bytes\n",
)
text = text.replace(
    "from gemini_trading.strategy.qualification_execution_v0_3 import qualification_case_ids\n",
    "from gemini_trading.strategy.qualification_execution_v0_3 import (\n"
    "    V03_INITIAL_CASH,\n"
    "    locked_v0_3_simulation_config,\n"
    "    qualification_case_ids,\n"
    ")\n",
)
text = text.replace(
    "def _verify_locked_identities(mapping: dict[str, bytes]) -> None:\n",
    "def _verify_locked_identities(\n"
    "    mapping: dict[str, bytes], artifacts: V03QualificationArtifacts\n"
    ") -> None:\n",
)
old_config = '''    config = cast(dict[str, object], config_obj)
    if (
        config.get("schema_version") != "candidate-v0.3-qualification-config-v1"
        or config.get("development_start") != "2018-01-01T00:00:00Z"
        or config.get("development_end_exclusive") != "2026-08-01T00:00:00Z"
        or config.get("strategy_id") != "candidate.multi_model.v0_3"
        or config.get("policy_version") != "candidate-multi-model-v0.3"
    ):
        raise StudyArtifactError("v0.3 qualification configuration boundary changed")
    expected_selectivity_sha = hashlib.sha256(expected_selectivity).hexdigest()
'''
new_config = '''    config = cast(dict[str, object], config_obj)
    expected_simulation_sha = hashlib.sha256(
        serialize_simulation_config(locked_v0_3_simulation_config())
    ).hexdigest()
    if (
        config.get("schema_version") != "candidate-v0.3-qualification-config-v1"
        or config.get("dataset_id") != artifacts.context.dataset_id
        or config.get("development_start") != "2018-01-01T00:00:00Z"
        or config.get("development_end_exclusive") != "2026-08-01T00:00:00Z"
        or config.get("initial_cash") != str(V03_INITIAL_CASH)
        or config.get("simulation_sha256") != expected_simulation_sha
        or config.get("strategy_id") != "candidate.multi_model.v0_3"
        or config.get("policy_version") != "candidate-multi-model-v0.3"
    ):
        raise StudyArtifactError("v0.3 qualification configuration boundary changed")
    expected_selectivity_sha = hashlib.sha256(expected_selectivity).hexdigest()
'''
text = text.replace(old_config, new_config)
text = text.replace(
    "    _verify_locked_identities(mapping)\n",
    "    _verify_locked_identities(mapping, artifacts)\n",
)
verification.write_text(text)
