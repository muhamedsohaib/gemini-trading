"""Locked structural policy for Candidate Multi-Model Strategy v0.1."""

from dataclasses import asdict, dataclass
from decimal import Decimal

from gemini_trading.research.serialization import canonical_json_bytes


def _positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")


def _non_negative_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


@dataclass(frozen=True, slots=True)
class CandidatePolicy:
    """Every predeclared structural value for the first strategy candidate."""

    schema_version: str
    strategy_id: str
    policy_version: str
    instrument_symbol: str
    base_asset: str
    quote_asset: str
    timeframe: str
    minimum_history_years: int
    final_test_months: int
    label_horizon_candles: int
    maximum_feature_lookback_candles: int
    cost_hurdle_extra_bps: Decimal
    entry_probability: Decimal
    hold_probability: Decimal
    exit_probability: Decimal
    companion_probability_floor: Decimal
    disagreement_limit: Decimal
    expected_edge_extra_bps: Decimal
    minimum_hold_candles: int
    maximum_hold_candles: int
    cooldown_candles: int
    indeterminate_tolerance_candles: int
    initial_stop_atr: Decimal
    trailing_stop_atr: Decimal
    initial_training_months: int
    calibration_months: int
    development_test_months: int
    walk_forward_step_months: int
    purge_candles: int
    embargo_candles: int
    minimum_development_folds: int
    calibration_minimum_observations: int
    calibration_minimum_positive: int
    calibration_minimum_negative: int
    trend_regularization_c: Decimal
    trend_l1_ratio: Decimal
    trend_max_iterations: int
    trend_tolerance: Decimal
    trend_seed: int
    mean_reversion_estimators: int
    mean_reversion_max_depth: int
    mean_reversion_learning_rate: Decimal
    mean_reversion_minimum_leaf: int
    mean_reversion_seed: int
    bootstrap_replicates: int
    bootstrap_block_candles: int
    bootstrap_seed: int
    shuffled_label_seed: int
    unstable_volatility_ratio: Decimal
    unstable_true_range_ratio: Decimal
    trending_strength_floor: Decimal
    trending_volatility_ceiling: Decimal
    trending_sign_streak: int
    ranging_strength_ceiling: Decimal
    ranging_volatility_ceiling: Decimal
    baseline_ids: tuple[str, ...]
    entry_sensitivity: tuple[Decimal, ...]
    exit_sensitivity: tuple[Decimal, ...]
    maximum_hold_sensitivity: tuple[int, ...]
    initial_stop_sensitivity: tuple[Decimal, ...]
    cooldown_sensitivity: tuple[int, ...]
    development_positive_fold_fraction: Decimal
    development_baseline_win_fraction: Decimal
    development_minimum_trades: int
    final_minimum_trades: int
    final_maximum_drawdown: Decimal
    final_buy_hold_drawdown_fraction: Decimal
    final_minimum_return_to_drawdown: Decimal
    final_baseline_ratio_improvement: Decimal
    final_standalone_ratio_improvement: Decimal
    final_baseline_net_return_tolerance: Decimal
    final_single_trade_profit_fraction: Decimal

    def __post_init__(self) -> None:
        for field_name in (
            "schema_version",
            "strategy_id",
            "policy_version",
            "instrument_symbol",
            "base_asset",
            "quote_asset",
            "timeframe",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        for field_name in (
            "minimum_history_years",
            "final_test_months",
            "label_horizon_candles",
            "maximum_feature_lookback_candles",
            "minimum_hold_candles",
            "maximum_hold_candles",
            "initial_training_months",
            "calibration_months",
            "development_test_months",
            "walk_forward_step_months",
            "minimum_development_folds",
            "calibration_minimum_observations",
            "calibration_minimum_positive",
            "calibration_minimum_negative",
            "trend_max_iterations",
            "mean_reversion_estimators",
            "mean_reversion_max_depth",
            "mean_reversion_minimum_leaf",
            "bootstrap_replicates",
            "bootstrap_block_candles",
            "trending_sign_streak",
            "development_minimum_trades",
            "final_minimum_trades",
        ):
            _positive_integer(getattr(self, field_name), field_name)
        for field_name in (
            "cooldown_candles",
            "indeterminate_tolerance_candles",
            "purge_candles",
            "embargo_candles",
            "trend_seed",
            "mean_reversion_seed",
            "bootstrap_seed",
            "shuffled_label_seed",
        ):
            _non_negative_integer(getattr(self, field_name), field_name)
        decimal_fields = (
            "cost_hurdle_extra_bps",
            "entry_probability",
            "hold_probability",
            "exit_probability",
            "companion_probability_floor",
            "disagreement_limit",
            "expected_edge_extra_bps",
            "initial_stop_atr",
            "trailing_stop_atr",
            "trend_regularization_c",
            "trend_l1_ratio",
            "trend_tolerance",
            "mean_reversion_learning_rate",
            "unstable_volatility_ratio",
            "unstable_true_range_ratio",
            "trending_strength_floor",
            "trending_volatility_ceiling",
            "ranging_strength_ceiling",
            "ranging_volatility_ceiling",
            "development_positive_fold_fraction",
            "development_baseline_win_fraction",
            "final_maximum_drawdown",
            "final_buy_hold_drawdown_fraction",
            "final_minimum_return_to_drawdown",
            "final_baseline_ratio_improvement",
            "final_standalone_ratio_improvement",
            "final_baseline_net_return_tolerance",
            "final_single_trade_profit_fraction",
        )
        for field_name in decimal_fields:
            _finite(getattr(self, field_name), field_name)
        for field_name in (
            "entry_probability",
            "hold_probability",
            "exit_probability",
            "companion_probability_floor",
            "disagreement_limit",
            "trend_l1_ratio",
            "development_positive_fold_fraction",
            "development_baseline_win_fraction",
            "final_maximum_drawdown",
            "final_buy_hold_drawdown_fraction",
            "final_baseline_ratio_improvement",
            "final_standalone_ratio_improvement",
            "final_single_trade_profit_fraction",
        ):
            value = getattr(self, field_name)
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be within [0, 1]")
        if not self.exit_probability < self.hold_probability < self.entry_probability:
            raise ValueError("probability thresholds must satisfy exit < hold < entry")
        if self.maximum_hold_candles < self.minimum_hold_candles:
            raise ValueError("maximum_hold_candles must not be below minimum_hold_candles")
        if len(self.baseline_ids) != len(set(self.baseline_ids)):
            raise ValueError("baseline_ids must be unique")
        if any(not value.strip() for value in self.baseline_ids):
            raise ValueError("baseline_ids must not contain empty values")

    @classmethod
    def locked_v0_1(cls) -> "CandidatePolicy":
        """Return the only structural policy approved for Candidate v0.1."""

        return cls(
            schema_version="candidate-strategy-policy-v1",
            strategy_id="candidate.multi_model.v0_1",
            policy_version="candidate-multi-model-v0.1",
            instrument_symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            timeframe="4h",
            minimum_history_years=7,
            final_test_months=18,
            label_horizon_candles=3,
            maximum_feature_lookback_candles=42,
            cost_hurdle_extra_bps=Decimal("10"),
            entry_probability=Decimal("0.62"),
            hold_probability=Decimal("0.50"),
            exit_probability=Decimal("0.45"),
            companion_probability_floor=Decimal("0.45"),
            disagreement_limit=Decimal("0.25"),
            expected_edge_extra_bps=Decimal("10"),
            minimum_hold_candles=2,
            maximum_hold_candles=18,
            cooldown_candles=2,
            indeterminate_tolerance_candles=1,
            initial_stop_atr=Decimal("2.5"),
            trailing_stop_atr=Decimal("3.0"),
            initial_training_months=24,
            calibration_months=6,
            development_test_months=6,
            walk_forward_step_months=6,
            purge_candles=3,
            embargo_candles=3,
            minimum_development_folds=5,
            calibration_minimum_observations=200,
            calibration_minimum_positive=40,
            calibration_minimum_negative=40,
            trend_regularization_c=Decimal("1.0"),
            trend_l1_ratio=Decimal("0.5"),
            trend_max_iterations=5000,
            trend_tolerance=Decimal("0.00000001"),
            trend_seed=1701,
            mean_reversion_estimators=150,
            mean_reversion_max_depth=2,
            mean_reversion_learning_rate=Decimal("0.03"),
            mean_reversion_minimum_leaf=100,
            mean_reversion_seed=1702,
            bootstrap_replicates=1000,
            bootstrap_block_candles=42,
            bootstrap_seed=1788,
            shuffled_label_seed=1799,
            unstable_volatility_ratio=Decimal("1.75"),
            unstable_true_range_ratio=Decimal("2.5"),
            trending_strength_floor=Decimal("1.0"),
            trending_volatility_ceiling=Decimal("1.5"),
            trending_sign_streak=3,
            ranging_strength_ceiling=Decimal("0.5"),
            ranging_volatility_ceiling=Decimal("1.25"),
            baseline_ids=(
                "cash.v1",
                "buy_hold.v1",
                "ema_20_50.v1",
                "donchian_20_10.v1",
                "mean_reversion_z24.v1",
            ),
            entry_sensitivity=(Decimal("0.59"), Decimal("0.65")),
            exit_sensitivity=(Decimal("0.42"), Decimal("0.48")),
            maximum_hold_sensitivity=(12, 24),
            initial_stop_sensitivity=(Decimal("2.0"), Decimal("3.0")),
            cooldown_sensitivity=(1, 3),
            development_positive_fold_fraction=Decimal("0.60"),
            development_baseline_win_fraction=Decimal("0.60"),
            development_minimum_trades=60,
            final_minimum_trades=30,
            final_maximum_drawdown=Decimal("0.25"),
            final_buy_hold_drawdown_fraction=Decimal("0.80"),
            final_minimum_return_to_drawdown=Decimal("0.50"),
            final_baseline_ratio_improvement=Decimal("0.10"),
            final_standalone_ratio_improvement=Decimal("0.05"),
            final_baseline_net_return_tolerance=Decimal("0.02"),
            final_single_trade_profit_fraction=Decimal("0.25"),
        )


def serialize_candidate_policy(policy: CandidatePolicy) -> bytes:
    """Return canonical bytes for the complete locked policy."""

    return canonical_json_bytes(asdict(policy))
