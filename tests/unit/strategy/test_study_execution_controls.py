"""Tests for evidence-derived Candidate component and negative-control gates."""

from decimal import Decimal

from gemini_trading.strategy.study_execution import (
    component_value_supported,
    shuffled_labels_passes_any_economic_gate,
)


def test_component_value_rejects_material_improvement_without_higher_drawdown() -> None:
    assert (
        component_value_supported(
            primary_return_to_drawdown=Decimal("0.50"),
            primary_maximum_drawdown=Decimal("0.20"),
            ablation_return_to_drawdown=Decimal("0.55"),
            ablation_maximum_drawdown=Decimal("0.20"),
            require_drawdown_reduction=False,
        )
        is False
    )


def test_component_value_accepts_when_ablation_improvement_is_below_ten_percent() -> None:
    assert (
        component_value_supported(
            primary_return_to_drawdown=Decimal("0.50"),
            primary_maximum_drawdown=Decimal("0.20"),
            ablation_return_to_drawdown=Decimal("0.549"),
            ablation_maximum_drawdown=Decimal("0.19"),
            require_drawdown_reduction=False,
        )
        is True
    )


def test_protection_component_requires_actual_drawdown_reduction_to_invalidate() -> None:
    assert (
        component_value_supported(
            primary_return_to_drawdown=Decimal("0.50"),
            primary_maximum_drawdown=Decimal("0.20"),
            ablation_return_to_drawdown=Decimal("0.55"),
            ablation_maximum_drawdown=Decimal("0.20"),
            require_drawdown_reduction=True,
        )
        is True
    )
    assert (
        component_value_supported(
            primary_return_to_drawdown=Decimal("0.50"),
            primary_maximum_drawdown=Decimal("0.20"),
            ablation_return_to_drawdown=Decimal("0.55"),
            ablation_maximum_drawdown=Decimal("0.19"),
            require_drawdown_reduction=True,
        )
        is False
    )


def test_component_value_fails_closed_when_return_to_drawdown_is_missing() -> None:
    assert (
        component_value_supported(
            primary_return_to_drawdown=None,
            primary_maximum_drawdown=Decimal("0.20"),
            ablation_return_to_drawdown=Decimal("0.60"),
            ablation_maximum_drawdown=Decimal("0.10"),
            require_drawdown_reduction=False,
        )
        is False
    )


def test_shuffled_labels_detects_any_positive_economic_gate() -> None:
    assert (
        shuffled_labels_passes_any_economic_gate(
            net_return=Decimal("0.01"),
            return_to_drawdown=None,
            strongest_simple_return_to_drawdown=None,
            strongest_specialist_return_to_drawdown=None,
        )
        is True
    )
    assert (
        shuffled_labels_passes_any_economic_gate(
            net_return=Decimal("0"),
            return_to_drawdown=Decimal("0.50"),
            strongest_simple_return_to_drawdown=Decimal("0.60"),
            strongest_specialist_return_to_drawdown=Decimal("0.60"),
        )
        is True
    )
    assert (
        shuffled_labels_passes_any_economic_gate(
            net_return=Decimal("0"),
            return_to_drawdown=None,
            strongest_simple_return_to_drawdown=None,
            strongest_specialist_return_to_drawdown=None,
        )
        is False
    )
