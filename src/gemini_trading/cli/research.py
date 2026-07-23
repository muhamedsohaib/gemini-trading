"""Safe read-only CLI handlers for deterministic research workflows."""

from __future__ import annotations

import json
import re
from argparse import Namespace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.research.artifacts import LocalResearchStore, build_artifacts
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.engine import run_backtest
from gemini_trading.research.errors import InvalidExperimentConfigError
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import build_experiment_manifest
from gemini_trading.research.replay import ReplayService, resolve_clean_git_commit
from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.safety.execution_mode import load_runtime_policy

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONFIG_KEYS = {"schema_version", "initial_cash", "random_seed", "simulation", "strategy"}
_SIMULATION_KEYS = {
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
_STRATEGY_KEYS = {"id", "entries"}
_ENTRY_KEYS = {"candle_index", "intents"}
_INTENT_KEYS = {"side", "order_type", "quantity", "limit_price", "time_in_force"}


def _object(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidExperimentConfigError(f"{description} must be a JSON object")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        raise InvalidExperimentConfigError(f"{description} keys must be strings")
    return cast(dict[str, object], mapping)


def _exact(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        raise InvalidExperimentConfigError(f"{description} fields do not match schema")


def _string(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _boolean(mapping: dict[str, object], key: str, description: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise InvalidExperimentConfigError(f"invalid {description} field: {key}")
    return value


def _decimal(value: object, field_name: str, description: str) -> Decimal:
    if not isinstance(value, str):
        raise InvalidExperimentConfigError(f"invalid {description} field: {field_name}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise InvalidExperimentConfigError(f"invalid {description} field: {field_name}") from None
    if not parsed.is_finite():
        raise InvalidExperimentConfigError(f"invalid {description} field: {field_name}")
    return parsed


def _load_config(path: Path) -> tuple[Decimal, int, SimulationConfig, ScriptedFixtureStrategy]:
    try:
        raw = path.read_bytes()
        loaded: object = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise InvalidExperimentConfigError(
            "research configuration could not be loaded safely"
        ) from None

    root = _object(loaded, "research configuration")
    _exact(root, _CONFIG_KEYS, "research configuration")
    if _string(root, "schema_version", "research configuration") != "research-cli-fixture-v1":
        raise InvalidExperimentConfigError("unsupported research configuration schema")

    simulation_mapping = _object(root.get("simulation"), "simulation configuration")
    _exact(simulation_mapping, _SIMULATION_KEYS, "simulation configuration")
    try:
        simulation = SimulationConfig(
            maker_fee_rate=_decimal(
                simulation_mapping.get("maker_fee_rate"),
                "maker_fee_rate",
                "simulation configuration",
            ),
            taker_fee_rate=_decimal(
                simulation_mapping.get("taker_fee_rate"),
                "taker_fee_rate",
                "simulation configuration",
            ),
            half_spread_bps=_decimal(
                simulation_mapping.get("half_spread_bps"),
                "half_spread_bps",
                "simulation configuration",
            ),
            slippage_bps=_decimal(
                simulation_mapping.get("slippage_bps"), "slippage_bps", "simulation configuration"
            ),
            latency_bars=_integer(simulation_mapping, "latency_bars", "simulation configuration"),
            price_tick=_decimal(
                simulation_mapping.get("price_tick"), "price_tick", "simulation configuration"
            ),
            quantity_step=_decimal(
                simulation_mapping.get("quantity_step"), "quantity_step", "simulation configuration"
            ),
            min_quantity=_decimal(
                simulation_mapping.get("min_quantity"), "min_quantity", "simulation configuration"
            ),
            min_notional=_decimal(
                simulation_mapping.get("min_notional"), "min_notional", "simulation configuration"
            ),
            max_volume_participation=_decimal(
                simulation_mapping.get("max_volume_participation"),
                "max_volume_participation",
                "simulation configuration",
            ),
            max_active_candles=_integer(
                simulation_mapping, "max_active_candles", "simulation configuration"
            ),
            timing_policy=TimingPolicy(
                _string(simulation_mapping, "timing_policy", "simulation configuration")
            ),
            limit_fill_policy=LimitFillPolicy(
                _string(simulation_mapping, "limit_fill_policy", "simulation configuration")
            ),
            default_time_in_force=TimeInForce(
                _string(simulation_mapping, "default_time_in_force", "simulation configuration")
            ),
            promotable=_boolean(simulation_mapping, "promotable", "simulation configuration"),
        )
    except ValueError as error:
        raise InvalidExperimentConfigError(f"invalid simulation configuration: {error}") from None

    strategy_mapping = _object(root.get("strategy"), "strategy configuration")
    _exact(strategy_mapping, _STRATEGY_KEYS, "strategy configuration")
    if _string(strategy_mapping, "id", "strategy configuration") != "fixture.scripted.v1":
        raise InvalidExperimentConfigError("unsupported research strategy identity")
    raw_entries = strategy_mapping.get("entries")
    if not isinstance(raw_entries, list):
        raise InvalidExperimentConfigError("invalid strategy configuration field: entries")
    script: list[tuple[int, tuple[OrderIntent, ...]]] = []
    for raw_entry in cast(list[object], raw_entries):
        entry = _object(raw_entry, "strategy entry")
        _exact(entry, _ENTRY_KEYS, "strategy entry")
        raw_intents = entry.get("intents")
        if not isinstance(raw_intents, list):
            raise InvalidExperimentConfigError("invalid strategy entry field: intents")
        intents: list[OrderIntent] = []
        for raw_intent in cast(list[object], raw_intents):
            intent = _object(raw_intent, "strategy intent")
            _exact(intent, _INTENT_KEYS, "strategy intent")
            limit_value = intent.get("limit_price")
            limit_price = (
                None
                if limit_value is None
                else _decimal(limit_value, "limit_price", "strategy intent")
            )
            try:
                intents.append(
                    OrderIntent(
                        side=OrderSide(_string(intent, "side", "strategy intent")),
                        order_type=OrderType(_string(intent, "order_type", "strategy intent")),
                        quantity=_decimal(intent.get("quantity"), "quantity", "strategy intent"),
                        limit_price=limit_price,
                        time_in_force=TimeInForce(
                            _string(intent, "time_in_force", "strategy intent")
                        ),
                    )
                )
            except ValueError as error:
                raise InvalidExperimentConfigError(f"invalid strategy intent: {error}") from None
        script.append((_integer(entry, "candle_index", "strategy entry"), tuple(intents)))

    return (
        _decimal(root.get("initial_cash"), "initial_cash", "research configuration"),
        _integer(root, "random_seed", "research configuration"),
        simulation,
        ScriptedFixtureStrategy(script=tuple(script)),
    )


def _path(value: object, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InvalidExperimentConfigError(f"invalid {description}")
    return Path(value).expanduser().resolve()


def _identity(value: object, description: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise InvalidExperimentConfigError(f"invalid {description}")
    return value


def run_research(arguments: Namespace) -> dict[str, object]:
    """Run one safe deterministic research command."""

    load_runtime_policy()
    command: object = getattr(arguments, "research_command", None)
    project_root = _path(getattr(arguments, "project_root", None), "project root")
    output_root = _path(getattr(arguments, "output_root", None), "output root")

    if command == "backtest":
        dataset_id = _identity(getattr(arguments, "dataset_id", None), "dataset identity")
        config_path = _path(getattr(arguments, "config", None), "configuration path")
        initial_cash, random_seed, config, strategy = _load_config(config_path)
        code_commit = resolve_clean_git_commit(project_root)
        dataset = load_verified_dataset(LocalImmutableStore(output_root), dataset_id)
        manifest = build_experiment_manifest(
            dataset=dataset,
            config=config,
            code_commit=code_commit,
            strategy_id=strategy.strategy_id,
            strategy_config=strategy.configuration(),
            initial_cash=initial_cash,
            random_seed=random_seed,
        )
        artifacts = build_artifacts(run_backtest(dataset, manifest, config, strategy), config)
        LocalResearchStore(output_root).write(artifacts)
        return {
            "experiment_id": artifacts.experiment_id,
            "promotable": artifacts.promotable,
            "result_id": artifacts.result_id,
            "status": artifacts.terminal_status,
        }

    experiment_id = _identity(getattr(arguments, "experiment_id", None), "experiment identity")
    commit_resolver = lambda: resolve_clean_git_commit(project_root)
    if command == "replay":
        artifacts = ReplayService(
            LocalImmutableStore(output_root),
            LocalResearchStore(output_root),
            current_commit_resolver=commit_resolver,
        ).replay(experiment_id)
        return {
            "experiment_id": artifacts.experiment_id,
            "promotable": artifacts.promotable,
            "result_id": artifacts.result_id,
            "status": artifacts.terminal_status,
        }
    if command == "verify":
        result = ResearchVerificationService(
            output_root,
            current_commit_resolver=commit_resolver,
        ).verify(experiment_id)
        return {
            "checks": list(result.checks),
            "experiment_id": result.experiment_id,
            "promotable": result.promotable,
            "result_id": result.result_id,
            "status": "verified",
        }
    raise InvalidExperimentConfigError("unsupported research command")


__all__ = ["run_research"]
