"""Research-only candidate strategy contracts and study workflows."""

from gemini_trading.strategy.contracts import (
    GateResult,
    IndexWindow,
    RegimeState,
    SpecialistKind,
    SpecialistPrediction,
    StrategyAction,
)
from gemini_trading.strategy.identity import (
    StrategyStudyManifest,
    component_id,
    serialize_study_manifest,
    study_id,
)
from gemini_trading.strategy.policy import CandidatePolicy, serialize_candidate_policy

__all__ = [
    "CandidatePolicy",
    "GateResult",
    "IndexWindow",
    "RegimeState",
    "SpecialistKind",
    "SpecialistPrediction",
    "StrategyAction",
    "StrategyStudyManifest",
    "component_id",
    "serialize_candidate_policy",
    "serialize_study_manifest",
    "study_id",
]
