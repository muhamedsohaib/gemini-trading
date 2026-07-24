"""Deterministic fixtures shared by candidate-strategy tests."""

from decimal import Decimal

from gemini_trading.strategy.identity import StrategyStudyManifest


def example_study_manifest() -> StrategyStudyManifest:
    """Return one valid manifest with visibly distinct trust-boundary hashes."""

    return StrategyStudyManifest(
        schema_version="strategy-study-manifest-v1",
        dataset_id="a" * 64,
        canonical_sha256="b" * 64,
        code_commit="3" * 40,
        policy_id="c" * 64,
        simulation_config_id="d" * 64,
        feature_registry_id="e" * 64,
        label_policy_id="f" * 64,
        split_plan_id="1" * 64,
        random_seed_policy_id="2" * 64,
        initial_cash=Decimal("10000"),
    )
