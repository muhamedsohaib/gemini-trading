"""Independent verification of immutable Candidate strategy-study evidence."""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from gemini_trading.research.verification import ResearchVerificationService
from gemini_trading.strategy.errors import StudyVerificationError
from gemini_trading.strategy.evaluation import MANDATORY_GATE_IDS, PromotionClassification
from gemini_trading.strategy.replay import (
    SUPPORTED_REPLAY_STRATEGY_IDS,
    StrategyStudyReplayService,
    parse_study_case_evidence,
    validate_replay_strategy_id,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ResearchVerificationEvidence(Protocol):
    """Minimum safe research-verification evidence consumed by study verification."""

    @property
    def result_id(self) -> str:
        """Return the independently verified research result identity."""

        ...


ResearchVerifier = Callable[[str], ResearchVerificationEvidence]


def _json_object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StudyVerificationError(f"invalid {description} JSON") from None
    if not isinstance(loaded, dict):
        raise StudyVerificationError(f"invalid {description} JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise StudyVerificationError(f"invalid {description} JSON object")
    return cast(dict[str, object], mapping)


def _required_str(mapping: Mapping[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise StudyVerificationError(f"invalid {description} field: {key}")
    return value


def _verify_mandatory_gates(raw: bytes, classification: PromotionClassification) -> None:
    mapping = _json_object(raw, "promotion gates")
    if _required_str(mapping, "classification", "promotion gates") != classification.value:
        raise StudyVerificationError("promotion-gate classification does not match study result")
    raw_gates = mapping.get("gates")
    if not isinstance(raw_gates, list):
        raise StudyVerificationError("promotion-gate evidence is incomplete")
    gate_ids: list[str] = []
    for raw_gate in cast(list[object], raw_gates):
        if not isinstance(raw_gate, dict):
            raise StudyVerificationError("invalid promotion-gate evidence")
        gate_mapping = cast(dict[object, object], raw_gate)
        if not all(isinstance(key, str) for key in gate_mapping):
            raise StudyVerificationError("invalid promotion-gate evidence")
        gate_ids.append(
            _required_str(
                cast(dict[str, object], gate_mapping),
                "gate_id",
                "promotion gate",
            )
        )
    values = tuple(gate_ids)
    if set(values) != set(MANDATORY_GATE_IDS) or len(values) != len(MANDATORY_GATE_IDS):
        raise StudyVerificationError("mandatory promotion-gate evidence is incomplete")


@dataclass(frozen=True, slots=True)
class StrategyStudyVerificationResult:
    """Safe verification summary containing no raw arrays, paths, or provider bodies."""

    study_id: str
    study_result_id: str
    classification: PromotionClassification
    promotable: bool
    checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StrategyStudyVerificationService:
    """Verify study identities, artifacts, experiments, gates, and offline replay."""

    root: Path
    current_commit_resolver: Callable[[], str]
    research_verifier: ResearchVerifier | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _verify_research_experiment(self, experiment_id: str) -> ResearchVerificationEvidence:
        if self.research_verifier is not None:
            return self.research_verifier(experiment_id)
        return ResearchVerificationService(
            root=self.root,
            current_commit_resolver=self.current_commit_resolver,
        ).verify(experiment_id)

    def verify(self, study_id: str) -> StrategyStudyVerificationResult:
        """Fail closed unless every independently checked boundary agrees."""

        replayed = StrategyStudyReplayService(
            root=self.root,
            current_commit_resolver=self.current_commit_resolver,
        ).replay(study_id)
        records = parse_study_case_evidence(replayed.artifact_bytes("experiments.jsonl"))
        for record in records:
            verified = self._verify_research_experiment(record.experiment_id)
            if _SHA256_PATTERN.fullmatch(verified.result_id) is None:
                raise StudyVerificationError("referenced research result identity is invalid")
            if verified.result_id != record.evidence_sha256:
                raise StudyVerificationError("referenced research evidence identity does not match")

        active_ids = set(SUPPORTED_REPLAY_STRATEGY_IDS) - {"fixture.scripted.v1"}
        referenced_ids = {record.case_id for record in records}
        if not active_ids.issubset(referenced_ids):
            raise StudyVerificationError("closed reconstruction registry evidence is incomplete")
        for strategy_id in sorted(active_ids):
            validate_replay_strategy_id(strategy_id)

        _verify_mandatory_gates(
            replayed.artifact_bytes("promotion-gates.json"),
            replayed.classification,
        )

        checks = tuple(
            sorted(
                {
                    "artifact_hashes_verified",
                    "closed_reconstruction_registry_verified",
                    "code_commit_verified",
                    "final_test_receipt_verified",
                    "mandatory_gates_verified",
                    "referenced_experiments_verified",
                    "replay_equivalent",
                    "study_identity_verified",
                    "study_result_identity_verified",
                }
            )
        )
        return StrategyStudyVerificationResult(
            study_id=replayed.study_id,
            study_result_id=replayed.study_result_id,
            classification=replayed.classification,
            promotable=False,
            checks=checks,
        )


__all__ = [
    "ResearchVerificationEvidence",
    "ResearchVerifier",
    "StrategyStudyVerificationResult",
    "StrategyStudyVerificationService",
]
