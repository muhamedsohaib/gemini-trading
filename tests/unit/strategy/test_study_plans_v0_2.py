"""RED tests for Candidate v0.2 development qualification case planning."""

from decimal import Decimal
from types import SimpleNamespace
from typing import cast

from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.strategy.baselines import build_baseline_schedules
from gemini_trading.strategy.calibration import ExpectedReturnMap, PlattArtifact
from gemini_trading.strategy.contracts import RegimeState
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.models import MeanReversionSpecialistTrainer, TrendSpecialistTrainer
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.regimes import RegimeObservation
from gemini_trading.strategy.study import REQUIRED_FINAL_CASE_IDS, StudyPhase
from gemini_trading.strategy.study_execution import CasePlan
from gemini_trading.strategy.study_plans import prepare_phase
from gemini_trading.strategy.study_predictions import Prediction, PredictionBundle
from strategy_fixture_support import base_simulation, deterministic_model_fixture, rising_candles


def _bundle() -> tuple[PredictionBundle, FeatureMatrix, int]:
    matrix, labels, indices = deterministic_model_fixture()
    policy = CandidatePolicy.locked_v0_2()
    trend = TrendSpecialistTrainer(policy).fit(matrix, labels, indices)
    mean_reversion = MeanReversionSpecialistTrainer(policy).fit(matrix, labels, indices)
    platt = PlattArtifact(
        schema_version="candidate-platt-v1",
        slope_hex=(1.0).hex(),
        intercept_hex=(0.0).hex(),
        minimum_probability_hex=(0.1).hex(),
        maximum_probability_hex=(0.9).hex(),
        observation_count=200,
        positive_count=100,
        negative_count=100,
    )
    expected = ExpectedReturnMap(
        schema_version="candidate-expected-return-map-v1",
        intercept=Decimal("0"),
        slope=Decimal("0.01"),
        minimum_probability=Decimal("0.1"),
        maximum_probability=Decimal("0.9"),
        observation_count=200,
    )
    index = indices[-1]
    return (
        PredictionBundle(
            phase=StudyPhase.DEVELOPMENT,
            fold_number=1,
            trend_model=trend,
            mean_reversion_model=mean_reversion,
            trend_platt=platt,
            mean_reversion_platt=platt,
            trend_return_map=expected,
            mean_reversion_return_map=expected,
            predictions=(
                Prediction(
                    candle_index=index,
                    trend_raw=0.1,
                    mean_reversion_raw=0.2,
                    trend_probability=Decimal("0.55"),
                    mean_reversion_probability=Decimal("0.52"),
                    trend_expected_return=Decimal("0.01"),
                    mean_reversion_expected_return=Decimal("0.008"),
                    regime=RegimeObservation(
                        candle_index=index,
                        state=RegimeState.TRENDING,
                        trend_strength=Decimal("1.2"),
                        volatility_ratio=Decimal("1.1"),
                        true_range_ratio=Decimal("1.0"),
                        sign_streak=3,
                        reason_code="trending_strength_streak",
                    ),
                ),
            ),
        ),
        matrix,
        index,
    )


def test_v0_2_development_qualification_prepares_full_robustness_case_set() -> None:
    bundle, matrix, index = _bundle()
    candles = rising_candles(index + 3)
    dataset = cast(VerifiedDataset, SimpleNamespace(candles=candles))
    simulation = base_simulation()
    policy = CandidatePolicy.locked_v0_2()
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan] = {}

    prepare_phase(
        phase=StudyPhase.DEVELOPMENT,
        fold_number=1,
        indices=(index,),
        bundle=bundle,
        dataset=dataset,
        simulation=simulation,
        policy=policy,
        label_policy=LabelPolicy.locked_v0_1(simulation),
        matrix=matrix,
        baseline_schedules=build_baseline_schedules(candles),
        plans=plans,
        include_qualification_robustness=True,
    )

    assert (
        tuple(
            case_id
            for phase, fold_number, case_id in plans
            if phase is StudyPhase.DEVELOPMENT and fold_number == 1
        )
        == REQUIRED_FINAL_CASE_IDS
    )
    assert plans[(StudyPhase.DEVELOPMENT, 1, policy.strategy_id)].strategy.strategy_id == (
        "candidate.multi_model.v0_2"
    )
