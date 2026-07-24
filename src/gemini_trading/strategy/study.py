"""Sealed deterministic orchestration for Candidate v0.1 strategy studies."""

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import IndexWindow
from gemini_trading.strategy.errors import FinalTestSealError, StrategyStudyError
from gemini_trading.strategy.splits import ChronologicalSplitPlan, WalkForwardFold

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_DEVELOPMENT_CASE_IDS = (
    "candidate.multi_model.v0_1",
    "cash.v1",
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
    "trend.specialist.v1",
    "mean_reversion.specialist.v1",
    "trend.ema_20_50.gated.v1",
    "ranging.mean_reversion_z24.gated.v1",
    "ablation.no_disagreement.v1",
    "ablation.no_volume.v1",
    "ablation.no_protection.v1",
    "control.delayed_features.v1",
    "control.shuffled_labels.v1",
)

REQUIRED_FINAL_CASE_IDS = (
    *REQUIRED_DEVELOPMENT_CASE_IDS,
    "cost.1_5x",
    "cost.2x",
    "sensitivity.entry_0_59",
    "sensitivity.entry_0_65",
    "sensitivity.exit_0_42",
    "sensitivity.exit_0_48",
    "sensitivity.max_hold_12",
    "sensitivity.max_hold_24",
    "sensitivity.initial_stop_2_0",
    "sensitivity.initial_stop_3_0",
    "sensitivity.cooldown_1",
    "sensitivity.cooldown_3",
    "control.shuffled_labels.seed_1799",
    "control.delayed_features.final",
    "bootstrap.seed_1788",
)


def _sha256(value: str, field_name: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _window_payload(window: IndexWindow) -> dict[str, object]:
    return {
        "start_inclusive": window.start_inclusive,
        "end_exclusive": window.end_exclusive,
    }


def _fold_payload(fold: WalkForwardFold) -> dict[str, object]:
    return {
        "fold_number": fold.fold_number,
        "training": _window_payload(fold.training),
        "calibration": _window_payload(fold.calibration),
        "development_test": _window_payload(fold.development_test),
        "training_indices": list(fold.training_indices),
        "calibration_indices": list(fold.calibration_indices),
        "development_test_indices": list(fold.development_test_indices),
        "purge_candles": fold.purge_candles,
        "embargo_candles": fold.embargo_candles,
    }


def split_plan_payload(plan: ChronologicalSplitPlan) -> dict[str, object]:
    """Return the complete canonical split-plan identity payload."""

    return {
        "schema_version": plan.schema_version,
        "dataset_start_time": plan.dataset_start_time,
        "dataset_end_exclusive": plan.dataset_end_exclusive,
        "final_test_start_time": plan.final_test_start_time,
        "final_test_boundary_index": plan.final_test_boundary_index,
        "final_test": _window_payload(plan.final_test),
        "final_test_indices": list(plan.final_test_indices),
        "folds": [_fold_payload(fold) for fold in plan.folds],
        "boundary_indices": list(plan.boundary_indices),
        "used_label_indices": list(plan.used_label_indices),
        "purge_candles": plan.purge_candles,
        "embargo_candles": plan.embargo_candles,
        "label_exit_offset": plan.label_exit_offset,
    }


def split_plan_sha256(plan: ChronologicalSplitPlan) -> str:
    """Return the content-derived identity of one chronological split plan."""

    return hashlib.sha256(canonical_json_bytes(split_plan_payload(plan))).hexdigest()


class StudyPhase(StrEnum):
    """Closed study execution phases."""

    DEVELOPMENT = "development"
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class StudyCaseEvidence:
    """One immutable experiment reference for one required study case."""

    case_id: str
    phase: StudyPhase
    fold_number: int | None
    terminal_status: str
    experiment_id: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if self.phase is StudyPhase.DEVELOPMENT:
            if self.fold_number is None or self.fold_number < 1:
                raise ValueError("development evidence requires a positive fold_number")
        elif self.fold_number is not None:
            raise ValueError("final evidence must not have a fold_number")
        if self.terminal_status not in {"completed", "failed"}:
            raise ValueError("terminal_status must be completed or failed")
        _sha256(self.experiment_id, "experiment_id")
        _sha256(self.evidence_sha256, "evidence_sha256")


class StudyExecutor(Protocol):
    """Execute one predeclared study case without changing structural identity."""

    def run_case(
        self,
        *,
        phase: StudyPhase,
        fold_number: int | None,
        case_id: str,
        decision_indices: tuple[int, ...],
    ) -> StudyCaseEvidence | None: ...


@dataclass(frozen=True, slots=True)
class FinalTestReceipt:
    """Single-use final-test access receipt bound to sealed identities."""

    evaluation_count: int
    final_test: IndexWindow
    split_plan_sha256: str
    policy_sha256: str
    configuration_sha256: str
    receipt_id: str


@dataclass(slots=True)
class FinalTestSeal:
    """Deny development access and permit one identity-matched final evaluation."""

    final_test: IndexWindow
    split_plan_sha256: str
    policy_sha256: str
    configuration_sha256: str
    _evaluation_count: int = 0

    @classmethod
    def create(
        cls,
        split_plan: ChronologicalSplitPlan,
        *,
        policy_sha256: str,
        configuration_sha256: str,
    ) -> "FinalTestSeal":
        return cls(
            final_test=split_plan.final_test,
            split_plan_sha256=split_plan_sha256(split_plan),
            policy_sha256=_sha256(policy_sha256, "policy_sha256"),
            configuration_sha256=_sha256(configuration_sha256, "configuration_sha256"),
        )

    def overlaps_final(self, window: IndexWindow) -> bool:
        """Return whether a window touches the sealed final-test interval."""

        return not (
            window.end_exclusive <= self.final_test.start_inclusive
            or window.start_inclusive >= self.final_test.end_exclusive
        )

    def authorize_final(
        self,
        *,
        policy_sha256: str,
        configuration_sha256: str,
    ) -> FinalTestReceipt:
        """Consume the final test exactly once when all structural identities match."""

        if policy_sha256 != self.policy_sha256 or configuration_sha256 != self.configuration_sha256:
            raise FinalTestSealError("final test structural identity changed after sealing")
        if self._evaluation_count != 0:
            raise FinalTestSealError("final test was already evaluated")
        self._evaluation_count = 1
        payload: dict[str, object] = {
            "evaluation_count": self._evaluation_count,
            "final_test": _window_payload(self.final_test),
            "split_plan_sha256": self.split_plan_sha256,
            "policy_sha256": self.policy_sha256,
            "configuration_sha256": self.configuration_sha256,
        }
        return FinalTestReceipt(
            evaluation_count=self._evaluation_count,
            final_test=self.final_test,
            split_plan_sha256=self.split_plan_sha256,
            policy_sha256=self.policy_sha256,
            configuration_sha256=self.configuration_sha256,
            receipt_id=hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class DevelopmentSelector:
    """Expose only development windows while the final test remains sealed."""

    seal: FinalTestSeal

    def read_predictions(self, window: IndexWindow) -> tuple[int, ...]:
        """Return allowed indexes or fail if the window touches the final test."""

        if self.seal.overlaps_final(window):
            raise FinalTestSealError("development selector cannot read the final test")
        return tuple(range(window.start_inclusive, window.end_exclusive))


@dataclass(frozen=True, slots=True)
class StrategyStudyEvidence:
    """Complete study orchestration evidence, including failures and final receipt."""

    study_id: str
    split_plan_sha256: str
    policy_sha256: str
    configuration_sha256: str
    fold_records: tuple[StudyCaseEvidence, ...]
    final_records: tuple[StudyCaseEvidence, ...]
    final_test_receipt: FinalTestReceipt

    def __post_init__(self) -> None:
        _sha256(self.study_id, "study_id")
        _sha256(self.split_plan_sha256, "split_plan_sha256")
        _sha256(self.policy_sha256, "policy_sha256")
        _sha256(self.configuration_sha256, "configuration_sha256")
        if self.final_test_receipt.evaluation_count != 1:
            raise FinalTestSealError("study evidence requires one final evaluation")


@dataclass(frozen=True, slots=True)
class StrategyStudyRunner:
    """Run every approved case in fold order and consume the final test once."""

    executor: StudyExecutor

    def _required_case(
        self,
        *,
        phase: StudyPhase,
        fold_number: int | None,
        case_id: str,
        decision_indices: tuple[int, ...],
    ) -> StudyCaseEvidence:
        evidence = self.executor.run_case(
            phase=phase,
            fold_number=fold_number,
            case_id=case_id,
            decision_indices=decision_indices,
        )
        if evidence is None:
            raise StrategyStudyError(f"missing study evidence: {case_id}")
        if (
            evidence.case_id != case_id
            or evidence.phase is not phase
            or evidence.fold_number != fold_number
        ):
            raise StrategyStudyError(f"mismatched study evidence: {case_id}")
        return evidence

    def run(
        self,
        *,
        split_plan: ChronologicalSplitPlan,
        policy_sha256: str,
        configuration_sha256: str,
    ) -> StrategyStudyEvidence:
        """Run all development cases, seal identities, then run final cases once."""

        policy_identity = _sha256(policy_sha256, "policy_sha256")
        configuration_identity = _sha256(configuration_sha256, "configuration_sha256")
        seal = FinalTestSeal.create(
            split_plan,
            policy_sha256=policy_identity,
            configuration_sha256=configuration_identity,
        )
        selector = DevelopmentSelector(seal)
        fold_records: list[StudyCaseEvidence] = []
        for fold in split_plan.folds:
            selector.read_predictions(fold.development_test)
            for case_id in REQUIRED_DEVELOPMENT_CASE_IDS:
                fold_records.append(
                    self._required_case(
                        phase=StudyPhase.DEVELOPMENT,
                        fold_number=fold.fold_number,
                        case_id=case_id,
                        decision_indices=fold.development_test_indices,
                    )
                )

        receipt = seal.authorize_final(
            policy_sha256=policy_identity,
            configuration_sha256=configuration_identity,
        )
        final_records = tuple(
            self._required_case(
                phase=StudyPhase.FINAL,
                fold_number=None,
                case_id=case_id,
                decision_indices=split_plan.final_test_indices,
            )
            for case_id in REQUIRED_FINAL_CASE_IDS
        )
        split_identity = seal.split_plan_sha256
        identity_payload: dict[str, object] = {
            "schema_version": "strategy-study-v1",
            "split_plan_sha256": split_identity,
            "policy_sha256": policy_identity,
            "configuration_sha256": configuration_identity,
            "development_cases": list(REQUIRED_DEVELOPMENT_CASE_IDS),
            "final_cases": list(REQUIRED_FINAL_CASE_IDS),
        }
        return StrategyStudyEvidence(
            study_id=hashlib.sha256(canonical_json_bytes(identity_payload)).hexdigest(),
            split_plan_sha256=split_identity,
            policy_sha256=policy_identity,
            configuration_sha256=configuration_identity,
            fold_records=tuple(fold_records),
            final_records=final_records,
            final_test_receipt=receipt,
        )


__all__ = [
    "REQUIRED_DEVELOPMENT_CASE_IDS",
    "REQUIRED_FINAL_CASE_IDS",
    "DevelopmentSelector",
    "FinalTestReceipt",
    "FinalTestSeal",
    "StrategyStudyEvidence",
    "StrategyStudyRunner",
    "StudyCaseEvidence",
    "StudyExecutor",
    "StudyPhase",
    "split_plan_payload",
    "split_plan_sha256",
]
