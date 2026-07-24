"""Integration tests for complete Candidate ablation and control evidence."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from gemini_trading.strategy.errors import StrategyStudyError
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
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


@dataclass(slots=True)
class MissingAblationExecutor:
    def run_case(
        self,
        *,
        phase: StudyPhase,
        fold_number: int | None,
        case_id: str,
        decision_indices: tuple[int, ...],
    ) -> StudyCaseEvidence | None:
        if phase is StudyPhase.DEVELOPMENT and case_id == "ablation.no_volume.v1":
            return None
        digest = (f"{phase.value}:{fold_number}:{case_id}".encode().hex() + "0" * 64)[:64]
        return StudyCaseEvidence(
            case_id=case_id,
            phase=phase,
            fold_number=fold_number,
            terminal_status="completed",
            experiment_id=digest,
            evidence_sha256=digest[::-1],
        )


def test_missing_ablation_evidence_fails_closed() -> None:
    assert "ablation.no_volume.v1" in REQUIRED_DEVELOPMENT_CASE_IDS

    with pytest.raises(StrategyStudyError, match="missing study evidence"):
        StrategyStudyRunner(MissingAblationExecutor()).run(
            split_plan=_split_plan(),
            policy_sha256="a" * 64,
            configuration_sha256="b" * 64,
        )
