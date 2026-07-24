"""Property tests for stable bounded calibrated probabilities."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.strategy.calibration import PlattArtifact, apply_platt


@given(score=st.floats(allow_nan=False, allow_infinity=False, width=64))
def test_platt_inference_is_bounded_for_every_finite_raw_score(score: float) -> None:
    artifact = PlattArtifact(
        schema_version="candidate-platt-v1",
        slope_hex=1.25.hex(),
        intercept_hex=(-0.4).hex(),
        minimum_probability_hex=0.1.hex(),
        maximum_probability_hex=0.9.hex(),
        observation_count=200,
        positive_count=100,
        negative_count=100,
    )

    probability = apply_platt(artifact, score)

    assert Decimal("0") <= probability <= Decimal("1")
