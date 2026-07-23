"""Content identities for deterministic research experiments."""

import hashlib
from decimal import Decimal

from gemini_trading.domain.experiment import ExperimentManifest
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.serialization import canonical_json_bytes

_EXPERIMENT_SCHEMA_VERSION = "research-experiment-v1"
_ENGINE_VERSION = "research-engine-v1"


def build_experiment_manifest(
    *,
    dataset: VerifiedDataset,
    config: SimulationConfig,
    code_commit: str,
    strategy_id: str,
    strategy_config: tuple[tuple[str, str], ...],
    initial_cash: Decimal,
    random_seed: int,
) -> ExperimentManifest:
    """Build an immutable manifest linking every result-shaping input."""

    config_sha256 = hashlib.sha256(serialize_simulation_config(config)).hexdigest()
    return ExperimentManifest(
        schema_version=_EXPERIMENT_SCHEMA_VERSION,
        dataset_id=dataset.manifest.dataset_id,
        canonical_sha256=dataset.manifest.canonical_sha256,
        code_commit=code_commit,
        engine_version=_ENGINE_VERSION,
        strategy_id=strategy_id,
        strategy_config=strategy_config,
        initial_cash=initial_cash,
        timing_policy=config.timing_policy,
        limit_fill_policy=config.limit_fill_policy,
        default_time_in_force=config.default_time_in_force,
        max_active_candles=config.max_active_candles,
        random_seed=random_seed,
        simulation_config_sha256=config_sha256,
    )


def serialize_experiment_manifest(manifest: ExperimentManifest) -> bytes:
    """Return canonical manifest bytes independent of config pair ordering."""

    normalized_strategy_config = [list(item) for item in sorted(manifest.strategy_config)]
    return canonical_json_bytes(
        {
            "schema_version": manifest.schema_version,
            "dataset_id": manifest.dataset_id,
            "canonical_sha256": manifest.canonical_sha256,
            "code_commit": manifest.code_commit,
            "engine_version": manifest.engine_version,
            "strategy_id": manifest.strategy_id,
            "strategy_config": normalized_strategy_config,
            "initial_cash": manifest.initial_cash,
            "timing_policy": manifest.timing_policy.value,
            "limit_fill_policy": manifest.limit_fill_policy.value,
            "default_time_in_force": manifest.default_time_in_force.value,
            "max_active_candles": manifest.max_active_candles,
            "random_seed": manifest.random_seed,
            "simulation_config_sha256": manifest.simulation_config_sha256,
        }
    )


def experiment_id(manifest: ExperimentManifest) -> str:
    """Return the SHA-256 identity of canonical experiment-manifest bytes."""

    return hashlib.sha256(serialize_experiment_manifest(manifest)).hexdigest()
