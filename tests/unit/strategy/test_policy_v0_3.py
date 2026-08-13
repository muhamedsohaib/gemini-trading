"""Candidate v0.3 policy identity and backward-compatibility tests."""

import hashlib

import pytest

from gemini_trading.strategy.policy import (
    CandidatePolicy,
    approved_candidate_policy,
    serialize_candidate_policy,
)

_V0_1_POLICY_SHA256 = "f9ecffb4c1079b9d00cae34ba9f000086a9ebb6d6a6930e6b3f26232fef82303"
_V0_2_POLICY_SHA256 = "95a59e0a8b190190d692a9f6836c634facbf9fd51da4a68b5f8fa7b83d33c9aa"


def _policy_sha256(policy: CandidatePolicy) -> str:
    return hashlib.sha256(serialize_candidate_policy(policy)).hexdigest()


def test_previous_candidate_policy_bytes_remain_frozen() -> None:
    assert _policy_sha256(CandidatePolicy.locked_v0_1()) == _V0_1_POLICY_SHA256
    assert _policy_sha256(CandidatePolicy.locked_v0_2()) == _V0_2_POLICY_SHA256


def test_locked_v0_3_changes_only_candidate_identity_from_v0_2() -> None:
    old = CandidatePolicy.locked_v0_2()
    new = CandidatePolicy.locked_v0_3()

    assert new.strategy_id == "candidate.multi_model.v0_3"
    assert new.policy_version == "candidate-multi-model-v0.3"
    assert new.schema_version == "candidate-strategy-policy-v3"
    differing = {
        name for name in old.__dataclass_fields__ if getattr(old, name) != getattr(new, name)
    }
    assert differing == {"schema_version", "strategy_id", "policy_version"}


def test_approved_candidate_policy_accepts_only_exact_v0_3_identity_pair() -> None:
    policy = approved_candidate_policy(
        "candidate.multi_model.v0_3",
        "candidate-multi-model-v0.3",
    )
    assert policy == CandidatePolicy.locked_v0_3()

    with pytest.raises(ValueError, match="identity pair"):
        approved_candidate_policy(
            "candidate.multi_model.v0_3",
            "candidate-multi-model-v0.2",
        )
