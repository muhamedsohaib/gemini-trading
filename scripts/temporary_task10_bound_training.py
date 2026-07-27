"""Bound only Task 10 integration-model fitting while retaining the full evidence chain."""

from pathlib import Path


path = Path("tests/integration/test_sealed_historical_validation.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from typing import cast\n\nfrom candidate_strategy_e2e_worker",
    "from typing import cast\n\nimport pytest\n\nfrom candidate_strategy_e2e_worker",
    1,
)
text = text.replace(
    "from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES\n",
    '''from gemini_trading.strategy import sealed_evaluator
from gemini_trading.strategy.artifacts import REQUIRED_STUDY_ARTIFACT_NAMES
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.policy import CandidatePolicy
''',
    1,
)
text = text.replace(
    "from gemini_trading.strategy.verification import StrategyStudyVerificationService\n",
    '''from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    fit_prediction_bundle as fit_prediction_bundle_unbounded,
)
from gemini_trading.strategy.verification import StrategyStudyVerificationService
''',
    1,
)
anchor = '''_CODE_COMMIT = "a" * 40
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


'''
insert = '''_CODE_COMMIT = "a" * 40
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAX_TRAINING_ROWS = 1_000
_MAX_CALIBRATION_ROWS = 500


def _bounded_prediction_bundle(
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


@pytest.fixture(autouse=True)
def _bound_integration_training(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sealed_evaluator,
        "fit_prediction_bundle",
        _bounded_prediction_bundle,
    )


'''
if text.count(anchor) != 1:
    raise SystemExit("unexpected Task 10 integration constant anchor")
path.write_text(text.replace(anchor, insert, 1), encoding="utf-8")
