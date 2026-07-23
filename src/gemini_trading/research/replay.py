"""Provider-free deterministic backtest replay from immutable local evidence."""

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.experiment import ExperimentManifest, LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.research.artifacts import LocalResearchStore, ResearchArtifacts, build_artifacts
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.engine import run_backtest
from gemini_trading.research.errors import ReplayMismatchError
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import experiment_id, serialize_experiment_manifest

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_EXPERIMENT_KEYS = {
    "schema_version",
    "dataset_id",
    "canonical_sha256",
    "code_commit",
    "engine_version",
    "strategy_id",
    "strategy_config",
    "initial_cash",
    "timing_policy",
    "limit_fill_policy",
    "default_time_in_force",
    "max_active_candles",
    "random_seed",
    "simulation_config_sha256",
}
_CONFIG_KEYS = {
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
    "timing_policy",
    "limit_fill_policy",
    "default_time_in_force",
    "max_active_candles",
    "promotable",
}


def _json_object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReplayMismatchError(f"invalid {description} JSON") from None
    if not isinstance(loaded, dict):
        raise ReplayMismatchError(f"invalid {description} JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise ReplayMismatchError(f"invalid {description} JSON object")
    return cast(dict[str, object], mapping)


def _required_str(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ReplayMismatchError(f"invalid {description} field: {key}")
    return value


def _required_int(mapping: dict[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplayMismatchError(f"invalid {description} field: {key}")
    return value


def _required_bool(mapping: dict[str, object], key: str, description: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ReplayMismatchError(f"invalid {description} field: {key}")
    return value


def _decimal(value: object, field_name: str, description: str) -> Decimal:
    if not isinstance(value, str):
        raise ReplayMismatchError(f"invalid {description} field: {field_name}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ReplayMismatchError(f"invalid {description} field: {field_name}") from None
    if not parsed.is_finite():
        raise ReplayMismatchError(f"invalid {description} field: {field_name}")
    return parsed


def parse_experiment_manifest(raw: bytes) -> ExperimentManifest:
    """Parse and canonically validate one stored experiment manifest."""

    mapping = _json_object(raw, "experiment manifest")
    if set(mapping) != _EXPERIMENT_KEYS:
        raise ReplayMismatchError("experiment manifest fields do not match schema")
    raw_strategy_config = mapping.get("strategy_config")
    if not isinstance(raw_strategy_config, list):
        raise ReplayMismatchError("invalid experiment manifest field: strategy_config")
    strategy_config: list[tuple[str, str]] = []
    for raw_item in cast(list[object], raw_strategy_config):
        if not isinstance(raw_item, list):
            raise ReplayMismatchError("invalid experiment manifest strategy configuration")
        pair = cast(list[object], raw_item)
        if len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            raise ReplayMismatchError("invalid experiment manifest strategy configuration")
        strategy_config.append((cast(str, pair[0]), cast(str, pair[1])))
    try:
        manifest = ExperimentManifest(
            schema_version=_required_str(mapping, "schema_version", "experiment manifest"),
            dataset_id=_required_str(mapping, "dataset_id", "experiment manifest"),
            canonical_sha256=_required_str(mapping, "canonical_sha256", "experiment manifest"),
            code_commit=_required_str(mapping, "code_commit", "experiment manifest"),
            engine_version=_required_str(mapping, "engine_version", "experiment manifest"),
            strategy_id=_required_str(mapping, "strategy_id", "experiment manifest"),
            strategy_config=tuple(strategy_config),
            initial_cash=_decimal(
                mapping.get("initial_cash"),
                "initial_cash",
                "experiment manifest",
            ),
            timing_policy=TimingPolicy(
                _required_str(mapping, "timing_policy", "experiment manifest")
            ),
            limit_fill_policy=LimitFillPolicy(
                _required_str(mapping, "limit_fill_policy", "experiment manifest")
            ),
            default_time_in_force=TimeInForce(
                _required_str(mapping, "default_time_in_force", "experiment manifest")
            ),
            max_active_candles=_required_int(
                mapping,
                "max_active_candles",
                "experiment manifest",
            ),
            random_seed=_required_int(mapping, "random_seed", "experiment manifest"),
            simulation_config_sha256=_required_str(
                mapping,
                "simulation_config_sha256",
                "experiment manifest",
            ),
        )
    except ValueError as error:
        raise ReplayMismatchError(f"invalid experiment manifest: {error}") from None
    if serialize_experiment_manifest(manifest) != raw:
        raise ReplayMismatchError("experiment manifest canonical bytes do not match")
    return manifest


def parse_simulation_config(raw: bytes) -> SimulationConfig:
    """Parse and canonically validate one stored simulation configuration."""

    mapping = _json_object(raw, "simulation configuration")
    if set(mapping) != _CONFIG_KEYS:
        raise ReplayMismatchError("simulation configuration fields do not match schema")
    try:
        config = SimulationConfig(
            maker_fee_rate=_decimal(
                mapping.get("maker_fee_rate"),
                "maker_fee_rate",
                "simulation configuration",
            ),
            taker_fee_rate=_decimal(
                mapping.get("taker_fee_rate"),
                "taker_fee_rate",
                "simulation configuration",
            ),
            half_spread_bps=_decimal(
                mapping.get("half_spread_bps"),
                "half_spread_bps",
                "simulation configuration",
            ),
            slippage_bps=_decimal(
                mapping.get("slippage_bps"),
                "slippage_bps",
                "simulation configuration",
            ),
            latency_bars=_required_int(
                mapping,
                "latency_bars",
                "simulation configuration",
            ),
            price_tick=_decimal(
                mapping.get("price_tick"),
                "price_tick",
                "simulation configuration",
            ),
            quantity_step=_decimal(
                mapping.get("quantity_step"),
                "quantity_step",
                "simulation configuration",
            ),
            min_quantity=_decimal(
                mapping.get("min_quantity"),
                "min_quantity",
                "simulation configuration",
            ),
            min_notional=_decimal(
                mapping.get("min_notional"),
                "min_notional",
                "simulation configuration",
            ),
            max_volume_participation=_decimal(
                mapping.get("max_volume_participation"),
                "max_volume_participation",
                "simulation configuration",
            ),
            timing_policy=TimingPolicy(
                _required_str(mapping, "timing_policy", "simulation configuration")
            ),
            limit_fill_policy=LimitFillPolicy(
                _required_str(mapping, "limit_fill_policy", "simulation configuration")
            ),
            default_time_in_force=TimeInForce(
                _required_str(
                    mapping,
                    "default_time_in_force",
                    "simulation configuration",
                )
            ),
            max_active_candles=_required_int(
                mapping,
                "max_active_candles",
                "simulation configuration",
            ),
            promotable=_required_bool(mapping, "promotable", "simulation configuration"),
        )
    except ValueError as error:
        raise ReplayMismatchError(f"invalid simulation configuration: {error}") from None
    if serialize_simulation_config(config) != raw:
        raise ReplayMismatchError("simulation configuration canonical bytes do not match")
    return config


def _intent_from_mapping(mapping: dict[str, object]) -> OrderIntent:
    expected = {"side", "order_type", "quantity", "limit_price", "time_in_force"}
    if set(mapping) != expected:
        raise ReplayMismatchError("fixture strategy intent fields do not match schema")
    limit_value = mapping.get("limit_price")
    limit_price = (
        None
        if limit_value is None
        else _decimal(limit_value, "limit_price", "fixture strategy intent")
    )
    try:
        return OrderIntent(
            side=OrderSide(_required_str(mapping, "side", "fixture strategy intent")),
            order_type=OrderType(_required_str(mapping, "order_type", "fixture strategy intent")),
            quantity=_decimal(
                mapping.get("quantity"),
                "quantity",
                "fixture strategy intent",
            ),
            limit_price=limit_price,
            time_in_force=TimeInForce(
                _required_str(mapping, "time_in_force", "fixture strategy intent")
            ),
        )
    except ValueError as error:
        raise ReplayMismatchError(f"invalid fixture strategy intent: {error}") from None


def fixture_strategy_from_manifest(manifest: ExperimentManifest) -> ScriptedFixtureStrategy:
    """Reconstruct the supported non-production fixture from manifest evidence."""

    if manifest.strategy_id != "fixture.scripted.v1":
        raise ReplayMismatchError("unsupported replay strategy identity")
    configuration = dict(manifest.strategy_config)
    if set(configuration) != {"script"}:
        raise ReplayMismatchError("fixture strategy configuration does not match schema")
    script_mapping = _json_object(configuration["script"].encode("utf-8"), "fixture strategy")
    if set(script_mapping) != {"entries"}:
        raise ReplayMismatchError("fixture strategy fields do not match schema")
    raw_entries = script_mapping.get("entries")
    if not isinstance(raw_entries, list):
        raise ReplayMismatchError("invalid fixture strategy entries")
    script: list[tuple[int, tuple[OrderIntent, ...]]] = []
    for raw_entry in cast(list[object], raw_entries):
        if not isinstance(raw_entry, dict):
            raise ReplayMismatchError("invalid fixture strategy entry")
        entry = cast(dict[object, object], raw_entry)
        if not all(isinstance(key, str) for key in entry):
            raise ReplayMismatchError("invalid fixture strategy entry")
        entry_mapping = cast(dict[str, object], entry)
        if set(entry_mapping) != {"candle_index", "intents"}:
            raise ReplayMismatchError("fixture strategy entry fields do not match schema")
        raw_intents = entry_mapping.get("intents")
        if not isinstance(raw_intents, list):
            raise ReplayMismatchError("invalid fixture strategy intents")
        intents: list[OrderIntent] = []
        for raw_intent in cast(list[object], raw_intents):
            if not isinstance(raw_intent, dict):
                raise ReplayMismatchError("invalid fixture strategy intent")
            intent_mapping = cast(dict[object, object], raw_intent)
            if not all(isinstance(key, str) for key in intent_mapping):
                raise ReplayMismatchError("invalid fixture strategy intent")
            intents.append(_intent_from_mapping(cast(dict[str, object], intent_mapping)))
        script.append(
            (
                _required_int(entry_mapping, "candle_index", "fixture strategy entry"),
                tuple(intents),
            )
        )
    try:
        strategy = ScriptedFixtureStrategy(script=tuple(script))
    except ValueError as error:
        raise ReplayMismatchError(f"invalid fixture strategy: {error}") from None
    if strategy.configuration() != manifest.strategy_config:
        raise ReplayMismatchError("fixture strategy canonical configuration mismatch")
    return strategy


def resolve_clean_git_commit(root: Path) -> str:
    """Return exact HEAD only when the repository working tree is clean."""

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise ReplayMismatchError("unable to resolve clean code commit") from None
    if status:
        raise ReplayMismatchError("code working tree is not clean")
    if _GIT_COMMIT_PATTERN.fullmatch(commit) is None:
        raise ReplayMismatchError("resolved code commit is invalid")
    return commit


def _default_current_commit() -> str:
    return resolve_clean_git_commit(Path.cwd())


@dataclass(frozen=True, slots=True)
class ReplayService:
    """Reconstruct and compare one stored deterministic experiment offline."""

    canonical_store: LocalImmutableStore
    research_store: LocalResearchStore
    current_commit_resolver: Callable[[], str] = _default_current_commit

    def replay(self, experiment_id_value: str) -> ResearchArtifacts:
        """Replay one experiment and fail unless every canonical artifact matches."""

        try:
            manifest_bytes = self.research_store.read_artifact(
                experiment_id_value,
                "experiment-manifest.json",
            )
            config_bytes = self.research_store.read_artifact(
                experiment_id_value,
                "simulation-config.json",
            )
        except (OSError, ValueError):
            raise ReplayMismatchError("required replay evidence is missing") from None
        manifest = parse_experiment_manifest(manifest_bytes)
        if experiment_id(manifest) != experiment_id_value:
            raise ReplayMismatchError("experiment identity does not match manifest")
        current_commit = self.current_commit_resolver()
        if current_commit != manifest.code_commit:
            raise ReplayMismatchError("code commit does not match experiment manifest")
        config = parse_simulation_config(config_bytes)
        if hashlib.sha256(config_bytes).hexdigest() != manifest.simulation_config_sha256:
            raise ReplayMismatchError("simulation configuration hash does not match manifest")
        strategy = fixture_strategy_from_manifest(manifest)
        try:
            dataset = load_verified_dataset(self.canonical_store, manifest.dataset_id)
        except Exception:
            raise ReplayMismatchError("canonical dataset verification failed") from None
        if dataset.manifest.canonical_sha256 != manifest.canonical_sha256:
            raise ReplayMismatchError("canonical dataset hash does not match experiment manifest")
        evidence = run_backtest(dataset, manifest, config, strategy)
        regenerated = build_artifacts(evidence, config)
        if regenerated.experiment_id != experiment_id_value:
            raise ReplayMismatchError("replayed experiment identity changed")
        for name, expected_bytes in regenerated.files:
            try:
                stored_bytes = self.research_store.read_artifact(experiment_id_value, name)
            except (OSError, ValueError):
                raise ReplayMismatchError(f"stored replay artifact is missing: {name}") from None
            if stored_bytes != expected_bytes:
                raise ReplayMismatchError(f"replayed artifact does not match: {name}")
        return regenerated


__all__ = [
    "ReplayService",
    "fixture_strategy_from_manifest",
    "parse_experiment_manifest",
    "parse_simulation_config",
    "resolve_clean_git_commit",
]
