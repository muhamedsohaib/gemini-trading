"""Integration tests for sealed Candidate walk-forward orchestration."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    StrategyStudyRunner,
    StudyCaseEvidence,
    StudyPhase,
)
from strategy_fixture_support import calendar_candles


def _split_plan() -> ChronologicalSplitPlan:
    candles = calendar_candles(
        start=datetime(2018, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return ChronologicalSplitPlan.build(
        candles,
        tuple(range(42, len(candles) - 4)),
        CandidatePolicy.locked_v0_1(),
    )


def _empty_calls() -> list[tuple[StudyPhase, int | None, str]]:
    return []


@dataclass(slots=True)
class RecordingExecutor:
    calls: list[tuple[StudyPhase, int | None, str]] = field(default_factory=_empty_calls)

    def run_case(
        self,
        *,
        phase: StudyPhase,
        fold_number: int | None,
        case_id: str,
        decision_indices: tuple[int, ...],
    ) -> StudyCaseEvidence:
        self.calls.append((phase, fold_number, case_id))
        identity_seed = f"{phase.value}:{fold_number}:{case_id}:{len(decision_indices)}"
        digest = (identity_seed.encode().hex() + "0" * 64)[:64]
        return StudyCaseEvidence(
            case_id=case_id,
            phase=phase,
            fold_number=fold_number,
            terminal_status="completed",
            experiment_id=digest,
            evidence_sha256=digest[::-1],
        )


def test_runner_records_every_fold_case_and_one_final_evaluation() -> None:
    plan = _split_plan()
    executor = RecordingExecutor()

    evidence = StrategyStudyRunner(executor).run(
        split_plan=plan,
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )

    assert len(evidence.fold_records) == len(plan.folds) * len(REQUIRED_DEVELOPMENT_CASE_IDS)
    assert tuple(item.case_id for item in evidence.final_records) == REQUIRED_FINAL_CASE_IDS
    assert evidence.final_test_receipt.evaluation_count == 1
    assert evidence.final_test_receipt.final_test == plan.final_test
    assert all(item.terminal_status == "completed" for item in evidence.fold_records)
    assert all(item.terminal_status == "completed" for item in evidence.final_records)
    assert len(evidence.study_id) == 64


def test_study_identity_changes_when_locked_configuration_changes() -> None:
    plan = _split_plan()
    first = StrategyStudyRunner(RecordingExecutor()).run(
        split_plan=plan,
        policy_sha256="a" * 64,
        configuration_sha256="b" * 64,
    )
    second = StrategyStudyRunner(RecordingExecutor()).run(
        split_plan=plan,
        policy_sha256="a" * 64,
        configuration_sha256="c" * 64,
    )

    assert first.study_id != second.study_id
