"""Tests for content-addressed candidate-strategy study identities."""

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest
from tests.strategy_fixture_support import example_study_manifest

from gemini_trading.strategy.identity import (
    StrategyStudyManifest,
    component_id,
    serialize_study_manifest,
    study_id,
)


def test_component_identity_is_canonical_and_schema_scoped() -> None:
    first = component_id("component-v1", {"b": 2, "a": 1})
    second = component_id("component-v1", {"a": 1, "b": 2})

    assert first == second
    assert first != component_id("component-v2", {"a": 1, "b": 2})


def test_study_id_hashes_canonical_manifest_bytes() -> None:
    manifest = example_study_manifest()

    assert study_id(manifest) == hashlib.sha256(serialize_study_manifest(manifest)).hexdigest()
    assert study_id(manifest) == study_id(example_study_manifest())
    assert study_id(replace(manifest, policy_id="9" * 64)) != study_id(manifest)


def test_manifest_rejects_invalid_hash_commit_or_cash() -> None:
    manifest = example_study_manifest()

    with pytest.raises(ValueError, match="dataset_id"):
        replace(manifest, dataset_id="not-a-hash")
    with pytest.raises(ValueError, match="code_commit"):
        replace(manifest, code_commit="abc")
    with pytest.raises(ValueError, match="initial_cash"):
        replace(manifest, initial_cash=Decimal("0"))


def test_manifest_schema_is_complete() -> None:
    manifest = StrategyStudyManifest(
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

    assert manifest == example_study_manifest()
