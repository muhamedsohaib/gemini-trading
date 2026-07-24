"""Property tests for non-executable specialist model artifacts."""

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.models import (
    LinearModelArtifact,
    parse_model_artifact,
    serialize_model_artifact,
)


@given(coefficient=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False))
def test_linear_artifact_round_trip_preserves_hexadecimal_coefficients(coefficient: float) -> None:
    artifact = LinearModelArtifact(
        schema_version="candidate-linear-model-v1",
        specialist=SpecialistKind.TREND,
        feature_names=("feature",),
        mean_hex=(1.0.hex(),),
        scale_hex=(2.0.hex(),),
        intercept_hex=(-0.5).hex(),
        coefficient_hex=(coefficient.hex(),),
        iteration_count=17,
        seed=1701,
        regularization_c_hex=1.0.hex(),
        l1_ratio_hex=0.5.hex(),
    )

    encoded = serialize_model_artifact(artifact)

    assert parse_model_artifact(encoded) == artifact
    assert coefficient.hex().encode() in encoded
