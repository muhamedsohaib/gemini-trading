"""Safe CLI handlers for immutable Candidate strategy studies."""

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from gemini_trading.cli.market_data import CliUsageError
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import TimeInForce
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.errors import InvalidExperimentConfigError
from gemini_trading.research.replay import resolve_clean_git_commit
from gemini_trading.safety.execution_mode import load_runtime_policy
from gemini_trading.strategy.artifacts import (
    REQUIRED_STUDY_ARTIFACT_NAMES,
    LocalStrategyStudyStore,
    StrategyStudyArtifacts,
)
from gemini_trading.strategy.errors import StudyArtifactError
from gemini_trading.strategy.replay import StrategyStudyReplayService
from gemini_trading.strategy.verification import StrategyStudyVerificationService

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_FIELDS = {"schema_version", "initial_cash", "simulation", "strategy"}
_SIMULATION_FIELDS = {
    "maker_fee_rate",
    "taker_fee_rate",
    "half_spread_bps",
    "slippage_bps",
    "latency_bars",
    "price_tick",
    "quantity_step",
    "min_quantity",
    "min_notional",
    "max_volume_participation",
    "max_active_candles",
    "timing_policy",
    "limit_fill_policy",
    "default_time_in_force",
    "promotable",
}
_STRATEGY_FIELDS = {"id", "policy_version"}
_SCHEMA_VERSION = "candidate-strategy-cli-v1"
_STRATEGY_ID = "candidate.multi_model.v0_1"
_POLICY_VERSION = "candidate-multi-model-v0.1"


@dataclass(frozen=True, slots=True)
class CandidateStrategyCliConfig:
    """Strict user-supplied non-structural inputs for Candidate v0.1."""

    schema_version: str
    initial_cash: Decimal
    simulation: SimulationConfig
    strategy_id: str
    policy_version: str


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidExperimentConfigError(f"{description} must be a JSON object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise InvalidExperimentConfigError(f"{description} keys must be strings")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: Mapping[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        raise InvalidExperimentConfigError(f"invalid {description} fields")


def _string(mapping: Mapping[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _integer(mapping: Mapping[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _boolean(mapping: Mapping[str, object], key: str, description: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _decimal(mapping: Mapping[str, object], key: str, description: str) -> Decimal:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}") from None
    if not parsed.is_finite():
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return parsed


def load_candidate_strategy_config(path: Path) -> CandidateStrategyCliConfig:
    """Load one exact Candidate v0.1 CLI configuration and reject unsafe variants."""

    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise InvalidExperimentConfigError(
            "unable to read candidate strategy configuration"
        ) from None
    except json.JSONDecodeError:
        raise InvalidExperimentConfigError(
            "invalid candidate strategy configuration JSON"
        ) from None
    top = _mapping(loaded, "candidate strategy configuration")
    _exact_fields(top, _TOP_LEVEL_FIELDS, "candidate strategy configuration")
    schema_version = _string(top, "schema_version", "candidate strategy configuration")
    if schema_version != _SCHEMA_VERSION:
        raise InvalidExperimentConfigError("unsupported candidate strategy configuration schema")
    initial_cash = _decimal(top, "initial_cash", "candidate strategy configuration")
    if initial_cash <= 0:
        raise InvalidExperimentConfigError("initial_cash must be finite and positive")

    strategy = _mapping(top.get("strategy"), "candidate strategy identity")
    _exact_fields(strategy, _STRATEGY_FIELDS, "candidate strategy identity")
    strategy_id = _string(strategy, "id", "candidate strategy identity")
    if strategy_id != _STRATEGY_ID:
        raise InvalidExperimentConfigError("candidate strategy identity is not approved")
    policy_version = _string(strategy, "policy_version", "candidate strategy identity")
    if policy_version != _POLICY_VERSION:
        raise InvalidExperimentConfigError("candidate policy version is not approved")

    simulation_mapping = _mapping(top.get("simulation"), "candidate simulation configuration")
    _exact_fields(simulation_mapping, _SIMULATION_FIELDS, "candidate simulation configuration")
    try:
        timing_policy = TimingPolicy(
            _string(simulation_mapping, "timing_policy", "candidate simulation configuration")
        )
    except ValueError:
        raise InvalidExperimentConfigError("candidate study requires next-candle timing") from None
    if timing_policy is not TimingPolicy.NEXT_CANDLE:
        raise InvalidExperimentConfigError("candidate study requires next-candle timing")
    try:
        limit_fill_policy = LimitFillPolicy(
            _string(simulation_mapping, "limit_fill_policy", "candidate simulation configuration")
        )
    except ValueError:
        raise InvalidExperimentConfigError("candidate study requires conservative fills") from None
    if limit_fill_policy is not LimitFillPolicy.CONSERVATIVE:
        raise InvalidExperimentConfigError("candidate study requires conservative fills")
    try:
        time_in_force = TimeInForce(
            _string(
                simulation_mapping,
                "default_time_in_force",
                "candidate simulation configuration",
            )
        )
    except ValueError as error:
        raise InvalidExperimentConfigError(str(error)) from None
    simulation = SimulationConfig.official(
        maker_fee_rate=_decimal(
            simulation_mapping, "maker_fee_rate", "candidate simulation configuration"
        ),
        taker_fee_rate=_decimal(
            simulation_mapping, "taker_fee_rate", "candidate simulation configuration"
        ),
        half_spread_bps=_decimal(
            simulation_mapping, "half_spread_bps", "candidate simulation configuration"
        ),
        slippage_bps=_decimal(
            simulation_mapping, "slippage_bps", "candidate simulation configuration"
        ),
        latency_bars=_integer(
            simulation_mapping, "latency_bars", "candidate simulation configuration"
        ),
        price_tick=_decimal(simulation_mapping, "price_tick", "candidate simulation configuration"),
        quantity_step=_decimal(
            simulation_mapping, "quantity_step", "candidate simulation configuration"
        ),
        min_quantity=_decimal(
            simulation_mapping, "min_quantity", "candidate simulation configuration"
        ),
        min_notional=_decimal(
            simulation_mapping, "min_notional", "candidate simulation configuration"
        ),
        max_volume_participation=_decimal(
            simulation_mapping,
            "max_volume_participation",
            "candidate simulation configuration",
        ),
        max_active_candles=_integer(
            simulation_mapping, "max_active_candles", "candidate simulation configuration"
        ),
        timing_policy=timing_policy,
        limit_fill_policy=limit_fill_policy,
        default_time_in_force=time_in_force,
        promotable=_boolean(simulation_mapping, "promotable", "candidate simulation configuration"),
    )
    if not simulation.promotable:
        raise InvalidExperimentConfigError(
            "candidate study requires promotable simulation evidence"
        )
    if any(
        value <= 0
        for value in (
            simulation.maker_fee_rate,
            simulation.taker_fee_rate,
            simulation.half_spread_bps,
            simulation.slippage_bps,
        )
    ):
        raise InvalidExperimentConfigError("candidate study requires non-zero trading costs")
    return CandidateStrategyCliConfig(
        schema_version=schema_version,
        initial_cash=initial_cash,
        simulation=simulation,
        strategy_id=strategy_id,
        policy_version=policy_version,
    )


def _argument(arguments: argparse.Namespace, name: str) -> str:
    value: object = getattr(arguments, name, None)
    if not isinstance(value, str) or not value:
        raise CliUsageError(f"missing command-line argument: --{name.replace('_', '-')}")
    return value


def _sha256_argument(arguments: argparse.Namespace, name: str) -> str:
    value = _argument(arguments, name)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise CliUsageError(f"--{name.replace('_', '-')} must be a lowercase SHA-256 digest")
    return value


def _root(arguments: argparse.Namespace, name: str) -> Path:
    return Path(_argument(arguments, name)).resolve(strict=False)


def evaluate_candidate_strategy(
    *,
    dataset_id: str,
    config: CandidateStrategyCliConfig,
    project_root: Path,
    output_root: Path,
    code_commit: str,
) -> StrategyStudyArtifacts:
    """Run the concrete Candidate evaluator; implemented by the study execution layer."""

    del dataset_id, config, project_root, output_root, code_commit
    raise StudyArtifactError("candidate strategy evaluation service is unavailable")


def _summary(artifacts: StrategyStudyArtifacts, status: str) -> dict[str, object]:
    return {
        "classification": artifacts.classification.value,
        "promotable": False,
        "status": status,
        "study_id": artifacts.study_id,
        "study_result_id": artifacts.study_result_id,
    }


def run_strategy(arguments: argparse.Namespace) -> dict[str, object]:
    """Run one safe Candidate strategy-study command."""

    load_runtime_policy()
    command = _argument(arguments, "research_command")
    project_root = _root(arguments, "project_root")
    output_root = _root(arguments, "output_root")
    if command == "strategy-evaluate":
        dataset_id = _sha256_argument(arguments, "dataset_id")
        config = load_candidate_strategy_config(Path(_argument(arguments, "config")))
        code_commit = resolve_clean_git_commit(project_root)
        artifacts = evaluate_candidate_strategy(
            dataset_id=dataset_id,
            config=config,
            project_root=project_root,
            output_root=output_root,
            code_commit=code_commit,
        )
        LocalStrategyStudyStore(output_root).write(artifacts)
        return _summary(artifacts, "completed")
    study_id = _sha256_argument(arguments, "study_id")
    if command == "strategy-replay":
        artifacts = StrategyStudyReplayService(
            root=output_root,
            current_commit_resolver=lambda: resolve_clean_git_commit(project_root),
        ).replay(study_id)
        return _summary(artifacts, "completed")
    if command == "strategy-verify":
        result = StrategyStudyVerificationService(
            root=output_root,
            current_commit_resolver=lambda: resolve_clean_git_commit(project_root),
        ).verify(study_id)
        return {
            "checks": list(result.checks),
            "classification": result.classification.value,
            "promotable": False,
            "status": "verified",
            "study_id": result.study_id,
            "study_result_id": result.study_result_id,
        }
    raise CliUsageError("unsupported strategy research command")


__all__ = [
    "REQUIRED_STUDY_ARTIFACT_NAMES",
    "CandidateStrategyCliConfig",
    "evaluate_candidate_strategy",
    "load_candidate_strategy_config",
    "run_strategy",
]
