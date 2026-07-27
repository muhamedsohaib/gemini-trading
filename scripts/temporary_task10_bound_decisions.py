"""Bound Task 10 decision windows while preserving the exact sealed evidence chain."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''from gemini_trading.data.segments import (
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
''',
    '''from gemini_trading.data.segments import (
    CandleSegmentManifest,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.domain.candle import Candle
''',
    1,
)
text = text.replace(
    "from gemini_trading.strategy.study import StudyPhase\n",
    '''from gemini_trading.strategy.splits import ChronologicalSplitPlan
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_plans import (
    build_split_plan as build_split_plan_unbounded,
)
''',
    1,
)
text = text.replace(
    "_MAX_CALIBRATION_ROWS = 500\n",
    "_MAX_CALIBRATION_ROWS = 500\n_MAX_DECISION_ROWS = 64\n",
    1,
)
anchor = '''def _bounded_prediction_bundle(
    *,
    phase: StudyPhase,
    fold_number: int | None,
    matrix: FeatureMatrix,
    labels: LabelVector,
    policy: CandidatePolicy,
    training_indices: tuple[int, ...],
    calibration_indices: tuple[int, ...],
    prediction_indices: tuple[int, ...],
) -> PredictionBundle:
    """Fit real deterministic specialists on bounded integration-only windows."""

    return fit_prediction_bundle_unbounded(
        phase=phase,
        fold_number=fold_number,
        matrix=matrix,
        labels=labels,
        policy=policy,
        training_indices=training_indices[:_MAX_TRAINING_ROWS],
        calibration_indices=calibration_indices[:_MAX_CALIBRATION_ROWS],
        prediction_indices=prediction_indices,
    )


'''
replacement = anchor + '''def _bounded_split_plan(
    candles: tuple[Candle, ...],
    eligible_indices: tuple[int, ...],
    policy: CandidatePolicy,
    segment_manifest: CandleSegmentManifest | None = None,
) -> tuple[ChronologicalSplitPlan, bool]:
    """Retain exact boundaries while bounding integration decision work."""

    plan, history_requirement_met = build_split_plan_unbounded(
        candles,
        eligible_indices,
        policy,
        segment_manifest,
    )
    folds = tuple(
        replace(
            fold,
            development_test_indices=fold.development_test_indices[:_MAX_DECISION_ROWS],
        )
        for fold in plan.folds[: policy.minimum_development_folds]
    )
    return (
        replace(
            plan,
            folds=folds,
            final_test_indices=plan.final_test_indices[:_MAX_DECISION_ROWS],
        ),
        history_requirement_met,
    )


'''
if text.count(anchor) != 1:
    raise SystemExit("unexpected bounded prediction fixture structure")
text = text.replace(anchor, replacement, 1)
old_fixture = '''@pytest.fixture(autouse=True)
def _bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )
'''
new_fixture = '''@pytest.fixture(autouse=True)
def bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )
    monkeypatch.setattr(
        sealed_evaluator,
        "build_split_plan",
        _bounded_split_plan,
    )
'''
if text.count(old_fixture) != 1:
    raise SystemExit("unexpected bounded training fixture structure")
path.write_text(text.replace(old_fixture, new_fixture, 1), encoding="utf-8")
