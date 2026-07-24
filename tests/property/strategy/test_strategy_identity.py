"""Property tests for strategy-study trust-boundary identities."""

from dataclasses import replace

from hypothesis import given, strategies as st

from gemini_trading.strategy.identity import study_id
from tests.strategy_fixture_support import example_study_manifest


@given(
    st.sampled_from(
        (
            "dataset_id",
            "canonical_sha256",
            "code_commit",
            "policy_id",
            "simulation_config_id",
            "feature_registry_id",
            "label_policy_id",
            "split_plan_id",
            "random_seed_policy_id",
        )
    )
)
def test_study_identity_changes_at_every_trust_boundary(boundary: str) -> None:
    manifest = example_study_manifest()

    if boundary == "dataset_id":
        changed = replace(manifest, dataset_id="9" * 64)
    elif boundary == "canonical_sha256":
        changed = replace(manifest, canonical_sha256="9" * 64)
    elif boundary == "code_commit":
        changed = replace(manifest, code_commit="9" * 40)
    elif boundary == "policy_id":
        changed = replace(manifest, policy_id="9" * 64)
    elif boundary == "simulation_config_id":
        changed = replace(manifest, simulation_config_id="9" * 64)
    elif boundary == "feature_registry_id":
        changed = replace(manifest, feature_registry_id="9" * 64)
    elif boundary == "label_policy_id":
        changed = replace(manifest, label_policy_id="9" * 64)
    elif boundary == "split_plan_id":
        changed = replace(manifest, split_plan_id="9" * 64)
    else:
        changed = replace(manifest, random_seed_policy_id="9" * 64)

    assert study_id(changed) != study_id(manifest)
