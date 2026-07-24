"""Shared deterministic fixtures for strategy-study artifact tests."""

from gemini_trading.strategy.contracts import IndexWindow
from gemini_trading.strategy.study import (
    FinalTestReceipt,
    StrategyStudyEvidence,
    StudyCaseEvidence,
    StudyPhase,
)


def example_study_evidence(*, failed_case_id: str | None = None) -> StrategyStudyEvidence:
    """Return compact complete study evidence with an optional failed case."""

    fold_records = tuple(
        StudyCaseEvidence(
            case_id=case_id,
            phase=StudyPhase.DEVELOPMENT,
            fold_number=1,
            terminal_status="failed" if case_id == failed_case_id else "completed",
            experiment_id=digit * 64,
            evidence_sha256=digit[::-1] * 64,
        )
        for case_id, digit in (
            ("candidate.multi_model.v0_1", "1"),
            ("cash.v1", "2"),
        )
    )
    final_records = tuple(
        StudyCaseEvidence(
            case_id=case_id,
            phase=StudyPhase.FINAL,
            fold_number=None,
            terminal_status="failed" if case_id == failed_case_id else "completed",
            experiment_id=digit * 64,
            evidence_sha256=digit[::-1] * 64,
        )
        for case_id, digit in (
            ("candidate.multi_model.v0_1", "3"),
            ("bootstrap.seed_1788", "4"),
        )
    )
    final_window = IndexWindow(start_inclusive=100, end_exclusive=200)
    receipt = FinalTestReceipt(
        evaluation_count=1,
        final_test=final_window,
        split_plan_sha256="5" * 64,
        policy_sha256="6" * 64,
        configuration_sha256="7" * 64,
        receipt_id="8" * 64,
    )
    return StrategyStudyEvidence(
        study_id="9" * 64,
        split_plan_sha256=receipt.split_plan_sha256,
        policy_sha256=receipt.policy_sha256,
        configuration_sha256=receipt.configuration_sha256,
        fold_records=fold_records,
        final_records=final_records,
        final_test_receipt=receipt,
    )
