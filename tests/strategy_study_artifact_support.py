"""Shared deterministic fixtures for strategy-study artifact tests."""

import hashlib

from gemini_trading.strategy.contracts import IndexWindow
from gemini_trading.strategy.evaluation import PromotionClassification
from gemini_trading.strategy.study import (
    REQUIRED_DEVELOPMENT_CASE_IDS,
    REQUIRED_FINAL_CASE_IDS,
    FinalTestReceipt,
    StrategyStudyEvidence,
    StudyCaseEvidence,
    StudyPhase,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def complete_study_evidence() -> StrategyStudyEvidence:
    """Return one complete single-fold study evidence fixture."""

    fold_records = tuple(
        StudyCaseEvidence(
            case_id=case_id,
            phase=StudyPhase.DEVELOPMENT,
            fold_number=1,
            terminal_status="completed",
            experiment_id=_digest(f"development:{case_id}"),
            evidence_sha256=_digest(f"development-evidence:{case_id}"),
        )
        for case_id in REQUIRED_DEVELOPMENT_CASE_IDS
    )
    final_records = tuple(
        StudyCaseEvidence(
            case_id=case_id,
            phase=StudyPhase.FINAL,
            fold_number=None,
            terminal_status="completed",
            experiment_id=_digest(f"final:{case_id}"),
            evidence_sha256=_digest(f"final-evidence:{case_id}"),
        )
        for case_id in REQUIRED_FINAL_CASE_IDS
    )
    return StrategyStudyEvidence(
        study_id=_digest("study"),
        split_plan_sha256=_digest("split"),
        policy_sha256=_digest("policy"),
        configuration_sha256=_digest("configuration"),
        fold_records=fold_records,
        final_records=final_records,
        final_test_receipt=FinalTestReceipt(
            evaluation_count=1,
            final_test=IndexWindow(100, 200),
            split_plan_sha256=_digest("split"),
            policy_sha256=_digest("policy"),
            configuration_sha256=_digest("configuration"),
            receipt_id=_digest("receipt"),
        ),
    )


def complete_payloads() -> dict[str, object]:
    """Return every externally supplied canonical study payload."""

    return {
        "policy.json": {"policy_id": "candidate-v0.1"},
        "feature-registry.json": {"feature_count": 42},
        "feature-matrix.jsonl": [{"candle_index": 42, "values": ["0.1"]}],
        "labels.jsonl": [{"candle_index": 42, "label": 1}],
        "split-plan.json": {"split_plan_sha256": _digest("split")},
        "folds.jsonl": [{"fold_number": 1, "status": "completed"}],
        "models.jsonl": [{"model_id": _digest("model")}],
        "calibration.jsonl": [{"calibration_id": _digest("calibration")}],
        "predictions.jsonl": [{"candle_index": 100, "probability": "0.60"}],
        "regimes.jsonl": [{"candle_index": 100, "state": "trending"}],
        "arbitration-decisions.jsonl": [{"candle_index": 100, "action": "remain_in_cash"}],
        "baselines.json": {"case_count": 5},
        "ablations.json": {"case_count": 3},
        "negative-controls.json": {"shuffled_labels": "failed"},
        "cost-stress.json": {"multipliers": ["1.5", "2.0"]},
        "parameter-sensitivity.json": {"neighbor_count": 10},
        "bootstrap.json": {"seed": 1788, "replicate_count": 1000},
        "promotion-gates.json": {
            "classification": PromotionClassification.REJECTED.value,
            "mandatory_gate_count": 32,
        },
        "limitations.json": {"production_eligible": False},
    }
