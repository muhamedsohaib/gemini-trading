"""Deterministic non-executable specialist model training and inference."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import SpecialistKind
from gemini_trading.strategy.errors import ModelDeterminismError
from gemini_trading.strategy.features import FeatureMatrix, FeatureRegistry
from gemini_trading.strategy.labels import LabelVector
from gemini_trading.strategy.policy import CandidatePolicy

_FLOAT_TOLERANCE = 1e-12


def _validate_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _validate_hex(value: str, field_name: str) -> str:
    normalized = _validate_identifier(value, field_name)
    try:
        decoded = float.fromhex(normalized)
    except ValueError:
        raise ValueError(f"{field_name} must contain a hexadecimal float") from None
    if not math.isfinite(decoded):
        raise ValueError(f"{field_name} must contain a finite hexadecimal float")
    return normalized


@dataclass(frozen=True, slots=True)
class LinearModelArtifact:
    """Portable elastic-net logistic artifact without executable serialization."""

    schema_version: str
    specialist: SpecialistKind
    feature_names: tuple[str, ...]
    mean_hex: tuple[str, ...]
    scale_hex: tuple[str, ...]
    intercept_hex: str
    coefficient_hex: tuple[str, ...]
    iteration_count: int
    seed: int
    regularization_c_hex: str
    l1_ratio_hex: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _validate_identifier(self.schema_version, "schema_version"),
        )
        if self.specialist is not SpecialistKind.TREND:
            raise ValueError("linear artifact specialist must be trend")
        _validate_feature_vectors(self.feature_names, self.mean_hex, self.scale_hex)
        if len(self.coefficient_hex) != len(self.feature_names):
            raise ValueError("linear coefficients must match feature names")
        for index, value in enumerate(self.coefficient_hex):
            _validate_hex(value, f"coefficient_hex[{index}]")
        object.__setattr__(
            self,
            "intercept_hex",
            _validate_hex(self.intercept_hex, "intercept_hex"),
        )
        object.__setattr__(
            self,
            "regularization_c_hex",
            _validate_hex(self.regularization_c_hex, "regularization_c_hex"),
        )
        object.__setattr__(
            self,
            "l1_ratio_hex",
            _validate_hex(self.l1_ratio_hex, "l1_ratio_hex"),
        )
        if isinstance(self.iteration_count, bool) or self.iteration_count < 1:
            raise ValueError("iteration_count must be positive")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be non-negative")


@dataclass(frozen=True, slots=True)
class TreeNodeArtifact:
    """One portable gradient-boosting tree node."""

    left_child: int
    right_child: int
    feature_index: int
    threshold_hex: str
    value_hex: str

    def __post_init__(self) -> None:
        for field_name in ("left_child", "right_child", "feature_index"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < -2:
                raise ValueError(f"{field_name} must be an integer no smaller than -2")
        object.__setattr__(
            self,
            "threshold_hex",
            _validate_hex(self.threshold_hex, "threshold_hex"),
        )
        object.__setattr__(
            self,
            "value_hex",
            _validate_hex(self.value_hex, "value_hex"),
        )


@dataclass(frozen=True, slots=True)
class DecisionTreeArtifact:
    """One ordered portable regression tree."""

    nodes: tuple[TreeNodeArtifact, ...]

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("decision tree must contain at least one node")


@dataclass(frozen=True, slots=True)
class BoostedTreeArtifact:
    """Portable gradient-boosted mean-reversion artifact."""

    schema_version: str
    specialist: SpecialistKind
    feature_names: tuple[str, ...]
    mean_hex: tuple[str, ...]
    scale_hex: tuple[str, ...]
    initial_raw_score_hex: str
    trees: tuple[DecisionTreeArtifact, ...]
    learning_rate_hex: str
    estimator_count: int
    max_depth: int
    minimum_leaf: int
    seed: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _validate_identifier(self.schema_version, "schema_version"),
        )
        if self.specialist is not SpecialistKind.MEAN_REVERSION:
            raise ValueError("boosted artifact specialist must be mean_reversion")
        _validate_feature_vectors(self.feature_names, self.mean_hex, self.scale_hex)
        object.__setattr__(
            self,
            "initial_raw_score_hex",
            _validate_hex(self.initial_raw_score_hex, "initial_raw_score_hex"),
        )
        object.__setattr__(
            self,
            "learning_rate_hex",
            _validate_hex(self.learning_rate_hex, "learning_rate_hex"),
        )
        for field_name in ("estimator_count", "max_depth", "minimum_leaf"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be positive")
        if len(self.trees) != self.estimator_count:
            raise ValueError("tree count must match estimator_count")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be non-negative")


type ModelArtifact = LinearModelArtifact | BoostedTreeArtifact


@dataclass(frozen=True, slots=True)
class _PreparedMatrix:
    feature_names: tuple[str, ...]
    raw: NDArray[np.float64]
    standardized: NDArray[np.float64]
    labels: NDArray[np.int64]
    means: NDArray[np.float64]
    scales: NDArray[np.float64]


def _validate_feature_vectors(
    feature_names: tuple[str, ...],
    mean_hex: tuple[str, ...],
    scale_hex: tuple[str, ...],
) -> None:
    if not feature_names or len(feature_names) != len(set(feature_names)):
        raise ValueError("feature_names must be unique and non-empty")
    if any(not value.strip() for value in feature_names):
        raise ValueError("feature_names must not contain empty values")
    if not (len(feature_names) == len(mean_hex) == len(scale_hex)):
        raise ValueError("feature names, means, and scales must have equal length")
    for index, value in enumerate(mean_hex):
        _validate_hex(value, f"mean_hex[{index}]")
    for index, value in enumerate(scale_hex):
        normalized = _validate_hex(value, f"scale_hex[{index}]")
        if float.fromhex(normalized) <= 0:
            raise ValueError("scales must be positive")


def _prepare_matrix(
    matrix: FeatureMatrix,
    labels: LabelVector,
    training_indices: tuple[int, ...],
    feature_names: tuple[str, ...],
) -> _PreparedMatrix:
    if not training_indices or len(training_indices) != len(set(training_indices)):
        raise ValueError("training indices must be unique and non-empty")
    column_by_name = {name: index for index, name in enumerate(matrix.feature_names)}
    try:
        columns = tuple(column_by_name[name] for name in feature_names)
    except KeyError as exc:
        raise KeyError(f"model feature is unavailable: {exc.args[0]}") from None
    raw_rows: list[list[float]] = []
    targets: list[int] = []
    for candle_index in training_indices:
        try:
            row = matrix.row_for(candle_index)
            label = labels.for_index(candle_index)
        except KeyError:
            raise KeyError(f"training index {candle_index} is unavailable") from None
        raw_rows.append([float(row.values[column]) for column in columns])
        targets.append(1 if label.positive else 0)
    raw = np.asarray(raw_rows, dtype=np.float64)
    target_array = np.asarray(targets, dtype=np.int64)
    if len(np.unique(target_array)) != 2:
        raise ModelDeterminismError("specialist training requires both label classes")
    means = np.asarray(np.mean(raw, axis=0), dtype=np.float64)
    scales = np.asarray(np.std(raw, axis=0, ddof=0), dtype=np.float64)
    if (
        not np.all(np.isfinite(raw))
        or not np.all(np.isfinite(means))
        or not np.all(np.isfinite(scales))
    ):
        raise ModelDeterminismError("specialist matrix must contain only finite values")
    zero_variance = tuple(
        feature_names[index] for index, value in enumerate(scales) if value == 0.0
    )
    if zero_variance:
        raise ModelDeterminismError(f"zero-variance training features: {', '.join(zero_variance)}")
    standardized = np.asarray((raw - means) / scales, dtype=np.float64)
    return _PreparedMatrix(
        feature_names=feature_names,
        raw=raw,
        standardized=standardized,
        labels=target_array,
        means=means,
        scales=scales,
    )


def _class_weights(labels: NDArray[np.int64]) -> dict[int, float] | None:
    total = int(labels.size)
    positive = int(np.sum(labels))
    negative = total - positive
    fraction = positive / total
    if 0.30 <= fraction <= 0.70:
        return None
    return {0: total / (2 * negative), 1: total / (2 * positive)}


@dataclass(frozen=True, slots=True)
class TrendSpecialistTrainer:
    """Fit the locked elastic-net trend specialist."""

    policy: CandidatePolicy

    def fit(
        self,
        matrix: FeatureMatrix,
        labels: LabelVector,
        training_indices: tuple[int, ...],
    ) -> LinearModelArtifact:
        registry = FeatureRegistry.locked_v0_1()
        prepared = _prepare_matrix(
            matrix,
            labels,
            training_indices,
            registry.trend_feature_names,
        )
        estimator = cast(
            Any,
            LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                C=float(self.policy.trend_regularization_c),
                l1_ratio=float(self.policy.trend_l1_ratio),
                max_iter=self.policy.trend_max_iterations,
                tol=float(self.policy.trend_tolerance),
                fit_intercept=True,
                class_weight=_class_weights(prepared.labels),
                random_state=self.policy.trend_seed,
                n_jobs=1,
            ),
        )
        with threadpool_limits(limits=1):
            estimator.fit(prepared.standardized, prepared.labels)
        iteration_count = int(np.asarray(estimator.n_iter_, dtype=np.int64).reshape(-1)[0])
        if iteration_count >= self.policy.trend_max_iterations:
            raise ModelDeterminismError("trend specialist did not converge before max_iter")
        coefficients = np.asarray(estimator.coef_, dtype=np.float64).reshape(-1)
        intercept = float(np.asarray(estimator.intercept_, dtype=np.float64).reshape(-1)[0])
        artifact = LinearModelArtifact(
            schema_version="candidate-linear-model-v1",
            specialist=SpecialistKind.TREND,
            feature_names=prepared.feature_names,
            mean_hex=tuple(float(value).hex() for value in prepared.means),
            scale_hex=tuple(float(value).hex() for value in prepared.scales),
            intercept_hex=intercept.hex(),
            coefficient_hex=tuple(float(value).hex() for value in coefficients),
            iteration_count=iteration_count,
            seed=self.policy.trend_seed,
            regularization_c_hex=float(self.policy.trend_regularization_c).hex(),
            l1_ratio_hex=float(self.policy.trend_l1_ratio).hex(),
        )
        expected = np.asarray(
            estimator.decision_function(prepared.standardized),
            dtype=np.float64,
        )
        _verify_custom_inference(artifact, prepared, expected)
        return artifact


@dataclass(frozen=True, slots=True)
class MeanReversionSpecialistTrainer:
    """Fit the locked gradient-boosted mean-reversion specialist."""

    policy: CandidatePolicy

    def fit(
        self,
        matrix: FeatureMatrix,
        labels: LabelVector,
        training_indices: tuple[int, ...],
    ) -> BoostedTreeArtifact:
        selected = tuple(
            candle_index
            for candle_index in training_indices
            if matrix.value_for(candle_index, "close_zscore_24") <= Decimal("-0.75")
            or matrix.value_for(candle_index, "drawdown_from_high_24") >= Decimal("0.02")
        )
        registry = FeatureRegistry.locked_v0_1()
        prepared = _prepare_matrix(
            matrix,
            labels,
            selected,
            registry.mean_reversion_feature_names,
        )
        estimator = cast(
            Any,
            GradientBoostingClassifier(
                loss="log_loss",
                learning_rate=float(self.policy.mean_reversion_learning_rate),
                n_estimators=self.policy.mean_reversion_estimators,
                subsample=1.0,
                max_depth=self.policy.mean_reversion_max_depth,
                min_samples_leaf=self.policy.mean_reversion_minimum_leaf,
                max_features=None,
                random_state=self.policy.mean_reversion_seed,
            ),
        )
        with threadpool_limits(limits=1):
            estimator.fit(prepared.standardized, prepared.labels)
        estimators = estimator.estimators_
        trees = tuple(
            _extract_tree(estimators[index, 0])
            for index in range(self.policy.mean_reversion_estimators)
        )
        initial_raw_score = float(
            np.asarray(
                estimator._raw_predict_init(prepared.standardized[:1]),
                dtype=np.float64,
            )[0, 0]
        )
        artifact = BoostedTreeArtifact(
            schema_version="candidate-boosted-tree-model-v1",
            specialist=SpecialistKind.MEAN_REVERSION,
            feature_names=prepared.feature_names,
            mean_hex=tuple(float(value).hex() for value in prepared.means),
            scale_hex=tuple(float(value).hex() for value in prepared.scales),
            initial_raw_score_hex=initial_raw_score.hex(),
            trees=trees,
            learning_rate_hex=float(self.policy.mean_reversion_learning_rate).hex(),
            estimator_count=self.policy.mean_reversion_estimators,
            max_depth=self.policy.mean_reversion_max_depth,
            minimum_leaf=self.policy.mean_reversion_minimum_leaf,
            seed=self.policy.mean_reversion_seed,
        )
        expected = np.asarray(
            estimator.decision_function(prepared.standardized),
            dtype=np.float64,
        )
        _verify_custom_inference(artifact, prepared, expected)
        return artifact


def _extract_tree(estimator: Any) -> DecisionTreeArtifact:
    tree = estimator.tree_
    nodes = tuple(
        TreeNodeArtifact(
            left_child=int(tree.children_left[index]),
            right_child=int(tree.children_right[index]),
            feature_index=int(tree.feature[index]),
            threshold_hex=float(tree.threshold[index]).hex(),
            value_hex=float(tree.value[index][0][0]).hex(),
        )
        for index in range(int(tree.node_count))
    )
    return DecisionTreeArtifact(nodes=nodes)


def _verify_custom_inference(
    artifact: ModelArtifact,
    prepared: _PreparedMatrix,
    expected: NDArray[np.float64],
) -> None:
    for row_index, expected_score in enumerate(expected.reshape(-1)):
        values = {
            feature_name: float(prepared.raw[row_index, column_index])
            for column_index, feature_name in enumerate(prepared.feature_names)
        }
        observed = predict_raw(artifact, values)
        if abs(observed - float(expected_score)) > _FLOAT_TOLERANCE:
            raise ModelDeterminismError("custom model inference diverged from scikit-learn")


def predict_raw(
    artifact: ModelArtifact,
    values: Mapping[str, Decimal | float],
) -> float:
    """Return one raw specialist score using only portable artifact data."""

    standardized: list[float] = []
    for feature_name, mean_hex, scale_hex in zip(
        artifact.feature_names,
        artifact.mean_hex,
        artifact.scale_hex,
        strict=True,
    ):
        try:
            raw_value = float(values[feature_name])
        except KeyError:
            raise KeyError(f"inference feature is unavailable: {feature_name}") from None
        if not math.isfinite(raw_value):
            raise ValueError(f"inference feature must be finite: {feature_name}")
        standardized.append((raw_value - float.fromhex(mean_hex)) / float.fromhex(scale_hex))
    if isinstance(artifact, LinearModelArtifact):
        return float.fromhex(artifact.intercept_hex) + math.fsum(
            float.fromhex(coefficient) * value
            for coefficient, value in zip(
                artifact.coefficient_hex,
                standardized,
                strict=True,
            )
        )
    score = float.fromhex(artifact.initial_raw_score_hex)
    learning_rate = float.fromhex(artifact.learning_rate_hex)
    for tree in artifact.trees:
        score += learning_rate * _tree_value(tree, standardized)
    return score


def _tree_value(tree: DecisionTreeArtifact, values: list[float]) -> float:
    node_index = 0
    while True:
        node = tree.nodes[node_index]
        if node.feature_index < 0:
            return float.fromhex(node.value_hex)
        node_index = (
            node.left_child
            if values[node.feature_index] <= float.fromhex(node.threshold_hex)
            else node.right_child
        )


def serialize_model_artifact(artifact: ModelArtifact) -> bytes:
    """Return canonical non-executable model bytes."""

    if isinstance(artifact, LinearModelArtifact):
        payload: dict[str, object] = {
            "artifact_type": "linear",
            "schema_version": artifact.schema_version,
            "specialist": artifact.specialist.value,
            "feature_names": artifact.feature_names,
            "mean_hex": artifact.mean_hex,
            "scale_hex": artifact.scale_hex,
            "intercept_hex": artifact.intercept_hex,
            "coefficient_hex": artifact.coefficient_hex,
            "iteration_count": artifact.iteration_count,
            "seed": artifact.seed,
            "regularization_c_hex": artifact.regularization_c_hex,
            "l1_ratio_hex": artifact.l1_ratio_hex,
        }
    else:
        payload = {
            "artifact_type": "boosted_tree",
            "schema_version": artifact.schema_version,
            "specialist": artifact.specialist.value,
            "feature_names": artifact.feature_names,
            "mean_hex": artifact.mean_hex,
            "scale_hex": artifact.scale_hex,
            "initial_raw_score_hex": artifact.initial_raw_score_hex,
            "trees": tuple(
                {
                    "nodes": tuple(
                        {
                            "left_child": node.left_child,
                            "right_child": node.right_child,
                            "feature_index": node.feature_index,
                            "threshold_hex": node.threshold_hex,
                            "value_hex": node.value_hex,
                        }
                        for node in tree.nodes
                    )
                }
                for tree in artifact.trees
            ),
            "learning_rate_hex": artifact.learning_rate_hex,
            "estimator_count": artifact.estimator_count,
            "max_depth": artifact.max_depth,
            "minimum_leaf": artifact.minimum_leaf,
            "seed": artifact.seed,
        }
    return canonical_json_bytes(payload)


def parse_model_artifact(payload: bytes) -> ModelArtifact:
    """Parse canonical model bytes without loading executable objects."""

    decoded = cast(dict[str, Any], json.loads(payload.decode("utf-8")))
    artifact_type = decoded.get("artifact_type")
    if artifact_type == "linear":
        return LinearModelArtifact(
            schema_version=str(decoded["schema_version"]),
            specialist=SpecialistKind(str(decoded["specialist"])),
            feature_names=tuple(str(value) for value in decoded["feature_names"]),
            mean_hex=tuple(str(value) for value in decoded["mean_hex"]),
            scale_hex=tuple(str(value) for value in decoded["scale_hex"]),
            intercept_hex=str(decoded["intercept_hex"]),
            coefficient_hex=tuple(str(value) for value in decoded["coefficient_hex"]),
            iteration_count=int(decoded["iteration_count"]),
            seed=int(decoded["seed"]),
            regularization_c_hex=str(decoded["regularization_c_hex"]),
            l1_ratio_hex=str(decoded["l1_ratio_hex"]),
        )
    if artifact_type == "boosted_tree":
        trees = tuple(
            DecisionTreeArtifact(
                nodes=tuple(
                    TreeNodeArtifact(
                        left_child=int(node["left_child"]),
                        right_child=int(node["right_child"]),
                        feature_index=int(node["feature_index"]),
                        threshold_hex=str(node["threshold_hex"]),
                        value_hex=str(node["value_hex"]),
                    )
                    for node in cast(list[dict[str, Any]], tree["nodes"])
                )
            )
            for tree in cast(list[dict[str, Any]], decoded["trees"])
        )
        return BoostedTreeArtifact(
            schema_version=str(decoded["schema_version"]),
            specialist=SpecialistKind(str(decoded["specialist"])),
            feature_names=tuple(str(value) for value in decoded["feature_names"]),
            mean_hex=tuple(str(value) for value in decoded["mean_hex"]),
            scale_hex=tuple(str(value) for value in decoded["scale_hex"]),
            initial_raw_score_hex=str(decoded["initial_raw_score_hex"]),
            trees=trees,
            learning_rate_hex=str(decoded["learning_rate_hex"]),
            estimator_count=int(decoded["estimator_count"]),
            max_depth=int(decoded["max_depth"]),
            minimum_leaf=int(decoded["minimum_leaf"]),
            seed=int(decoded["seed"]),
        )
    raise ValueError("unknown model artifact type")
