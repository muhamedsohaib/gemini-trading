# Deterministic Research and Backtesting Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repository-native, deterministic, single-instrument Binance Spot backtesting engine that produces conservative, reproducible, independently verifiable research evidence without any exchange execution capability.

**Architecture:** Verified canonical candles are replayed as a strict chronological event stream into a strategy protocol. Deterministic order, fill, accounting, artifact, replay, and verification components remain isolated behind immutable domain contracts. Official evidence uses next-candle execution, conservative limit fills, explicit costs, Decimal arithmetic, and fail-closed invariants.

**Tech Stack:** Python 3.12, standard-library dataclasses/enums/protocols, `Decimal`, JSON/JSONL, SHA-256, argparse, pytest, Hypothesis, Ruff, Pyright, Hatch/uv.

## Global Constraints

- Runtime promotion level remains `RESEARCH_ONLY`; no private endpoint, credential, paper broker, demo adapter, or exchange submission is introduced.
- First slice is Binance Spot canonical candles, one instrument, long-only, quote-currency cash accounting.
- Supported actions are buy, hold, and sell-to-close; shorting, leverage, margin, futures, options, funding, and liquidation modelling are excluded.
- Official timing is next-candle execution; same-close behavior is diagnostic and non-promotable.
- Official limit fills require strict price crossing; optimistic touch fills are diagnostic and non-promotable.
- Market and limit orders, deterministic partial fills, bounded `IOC`/`BAR`/`GTC`, and maximum candle-volume participation are required.
- Monetary, price, fee, and quantity calculations use finite `Decimal` values only.
- Identical trusted inputs must produce byte-equivalent core artifacts and the same experiment and result identities.
- Integrity, chronology, accounting, artifact, or replay contradictions invalidate the experiment and fail closed.
- The assistant remains an independent advisory reviewer for promotion, evidence classification, risk increases, credentials, stage changes, material capital allocation, and accepted limitations; it is not autonomous order authority.
- Every implementation task follows red-green-refactor TDD, records focused evidence, and ends in a dedicated commit.
- Final acceptance requires exact pull-request-head verification and exact merged-`main` verification before Issue #12 closes.

---

## File Structure

The milestone creates these focused units:

```text
src/gemini_trading/
├── domain/
│   ├── experiment.py      # experiment enums and immutable manifest contracts
│   ├── order.py           # order intents and simulated order lifecycle
│   ├── fill.py            # immutable fill records
│   └── account.py         # immutable account snapshots and ledger entries
├── research/
│   ├── errors.py          # safe research/backtest failure taxonomy
│   ├── serialization.py   # canonical JSON/JSONL and Decimal/UTC encoding
│   ├── dataset_reader.py  # verified canonical dataset loading
│   ├── config.py          # validated simulation configuration
│   ├── identity.py        # experiment/result content identities
│   ├── contracts.py       # strategy protocol and read-only context
│   ├── fixture_strategy.py# scripted non-production acceptance fixture
│   ├── engine.py          # chronological orchestration
│   ├── metrics.py         # deterministic metrics
│   ├── artifacts.py       # immutable local research evidence
│   ├── replay.py          # provider-free deterministic replay
│   └── verification.py    # independent evidence verification
├── execution/simulator/
│   ├── precision.py       # conservative tick/step rounding
│   ├── costs.py           # fees, spread, and slippage
│   ├── liquidity.py       # deterministic volume participation
│   └── fills.py           # market/limit eligibility and fill proposals
└── cli/
    └── research.py        # safe backtest/replay/verify handlers
```

Tests mirror those boundaries under `tests/unit`, `tests/property`, `tests/integration`, `tests/regression`, and `tests/acceptance`.

---

### Task 1: Research failure taxonomy and canonical serialization

**Files:**
- Create: `src/gemini_trading/research/__init__.py`
- Create: `src/gemini_trading/research/errors.py`
- Create: `src/gemini_trading/research/serialization.py`
- Create: `tests/unit/research/test_errors.py`
- Create: `tests/unit/research/test_serialization.py`
- Create: `reports/verification/deterministic-backtesting-progress.md`

**Interfaces:**
- Produces: `ResearchError` subclasses used by every later task.
- Produces: `canonical_json_bytes(payload: Mapping[str, object]) -> bytes`.
- Produces: `canonical_jsonl_bytes(rows: Iterable[Mapping[str, object]]) -> bytes`.
- Produces: `format_decimal(value: Decimal) -> str` and `format_utc(value: datetime) -> str`.

- [ ] **Step 1: Write failing taxonomy and serialization tests**

```python
# tests/unit/research/test_serialization.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.research.serialization import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    format_decimal,
    format_utc,
)


def test_canonical_json_is_sorted_compact_utf8_and_newline_terminated() -> None:
    payload = {"z": Decimal("1.2300"), "a": "é"}
    assert canonical_json_bytes(payload) == '{"a":"é","z":"1.2300"}\n'.encode("utf-8")


def test_canonical_jsonl_preserves_row_order() -> None:
    assert canonical_jsonl_bytes(({"n": 2}, {"n": 1})) == b'{"n":2}\n{"n":1}\n'


def test_decimal_and_utc_formatting_are_exact() -> None:
    assert format_decimal(Decimal("10.5000")) == "10.5000"
    assert format_utc(datetime(2025, 1, 1, 0, 0, tzinfo=UTC)) == "2025-01-01T00:00:00.000Z"


def test_serialization_rejects_non_finite_decimal_and_non_utc_time() -> None:
    with pytest.raises(ValueError, match="finite"):
        format_decimal(Decimal("NaN"))
    with pytest.raises(ValueError, match="UTC-aware"):
        format_utc(datetime(2025, 1, 1))
```

```python
# tests/unit/research/test_errors.py
from gemini_trading.research.errors import (
    AccountingInvariantError,
    DatasetVerificationError,
    ResearchError,
)


def test_research_errors_share_one_safe_base() -> None:
    assert issubclass(AccountingInvariantError, ResearchError)
    assert issubclass(DatasetVerificationError, ResearchError)
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run:

```bash
uv run pytest tests/unit/research/test_errors.py tests/unit/research/test_serialization.py -q
```

Expected: collection fails because `gemini_trading.research` does not exist.

- [ ] **Step 3: Add the minimal safe implementation**

```python
# src/gemini_trading/research/errors.py
"""Safe deterministic-research failure taxonomy."""


class ResearchError(Exception):
    """Base class for safe research and backtesting failures."""


class InvalidExperimentConfigError(ResearchError):
    """Experiment configuration is incomplete or contradictory."""


class DatasetVerificationError(ResearchError):
    """Canonical dataset evidence cannot be trusted."""


class ChronologyViolationError(ResearchError):
    """Candle chronology or completion rules were violated."""


class StrategyContractError(ResearchError):
    """A strategy returned an invalid or non-deterministic decision."""


class InvalidOrderTransitionError(ResearchError):
    """An order lifecycle transition is not permitted."""


class AccountingInvariantError(ResearchError):
    """Cash, position, equity, or ledger invariants failed."""


class ArtifactConflictError(ResearchError):
    """Immutable research evidence conflicts with stored bytes."""


class ReplayMismatchError(ResearchError):
    """Replay did not reproduce the recorded artifacts."""


class NonDeterministicResultError(ResearchError):
    """Equivalent trusted inputs produced different core evidence."""
```

```python
# src/gemini_trading/research/serialization.py
"""Canonical research JSON and JSONL encoding."""

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast


def format_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Decimal value must be finite")
    return format(value, "f")


def format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("datetime must be UTC-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _default(value: object) -> object:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, datetime):
        return format_utc(value)
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_default,
    )
    return f"{encoded}\n".encode("utf-8")


def canonical_jsonl_bytes(rows: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_json_bytes(cast(Mapping[str, object], row)) for row in rows)
```

Create empty package file `src/gemini_trading/research/__init__.py`.

Initialize `reports/verification/deterministic-backtesting-progress.md` with the task goal, exact commands, observed red/green outcomes, tested commit, and remaining limitations.

- [ ] **Step 4: Run focused quality checks**

```bash
uv run pytest tests/unit/research/test_errors.py tests/unit/research/test_serialization.py -q
uv run ruff format --check src/gemini_trading/research tests/unit/research
uv run ruff check src/gemini_trading/research tests/unit/research
uv run pyright src/gemini_trading/research tests/unit/research
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research tests/unit/research reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add deterministic research foundations"
```

---

### Task 2: Immutable experiment, order, fill, and account contracts

**Files:**
- Create: `src/gemini_trading/domain/experiment.py`
- Create: `src/gemini_trading/domain/order.py`
- Create: `src/gemini_trading/domain/fill.py`
- Create: `src/gemini_trading/domain/account.py`
- Create: `tests/unit/domain/test_experiment.py`
- Create: `tests/unit/domain/test_order.py`
- Create: `tests/unit/domain/test_fill.py`
- Create: `tests/unit/domain/test_account.py`

**Interfaces:**
- Produces enums: `TimingPolicy`, `LimitFillPolicy`, `TimeInForce`, `OrderSide`, `OrderType`, `OrderStatus`.
- Produces immutable dataclasses: `ExperimentManifest`, `OrderIntent`, `SimulatedOrder`, `Fill`, `AccountSnapshot`, `LedgerEntry`.
- All Decimal fields must be finite; quantities and prices must be positive where required.

- [ ] **Step 1: Write failing contract tests**

```python
# tests/unit/domain/test_order.py
from decimal import Decimal

import pytest

from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce


def test_limit_order_requires_price_and_market_order_forbids_it() -> None:
    with pytest.raises(ValueError, match="limit_price"):
        OrderIntent(OrderSide.BUY, OrderType.LIMIT, Decimal("1"), None, TimeInForce.GTC)
    with pytest.raises(ValueError, match="limit_price"):
        OrderIntent(
            OrderSide.BUY,
            OrderType.MARKET,
            Decimal("1"),
            Decimal("100"),
            TimeInForce.IOC,
        )


def test_sell_to_close_is_explicit_not_short_side() -> None:
    assert OrderSide.SELL_TO_CLOSE.value == "sell_to_close"
```

```python
# tests/unit/domain/test_account.py
from decimal import Decimal

import pytest

from gemini_trading.domain.account import AccountSnapshot


def test_account_rejects_negative_cash_or_position() -> None:
    with pytest.raises(ValueError, match="cash"):
        AccountSnapshot.initial(Decimal("-1"))
    with pytest.raises(ValueError, match="position"):
        AccountSnapshot(
            cash=Decimal("10"),
            reserved_cash=Decimal("0"),
            position_quantity=Decimal("-1"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
            cumulative_fees=Decimal("0"),
            cumulative_execution_costs=Decimal("0"),
            marked_equity=Decimal("10"),
            peak_equity=Decimal("10"),
            drawdown=Decimal("0"),
        )
```

Add equivalent immutability, finite-value, status, and manifest SHA validation tests in the other three files.

- [ ] **Step 2: Run tests and confirm missing-contract failures**

```bash
uv run pytest tests/unit/domain/test_experiment.py tests/unit/domain/test_order.py tests/unit/domain/test_fill.py tests/unit/domain/test_account.py -q
```

Expected: collection fails on missing modules.

- [ ] **Step 3: Implement complete immutable contracts**

Use `@dataclass(frozen=True, slots=True)` for every record and `StrEnum` for every enum.

Required signatures:

```python
class TimingPolicy(StrEnum):
    NEXT_CANDLE = "next_candle"
    SAME_CLOSE_DIAGNOSTIC = "same_close_diagnostic"


class LimitFillPolicy(StrEnum):
    CONSERVATIVE = "conservative"
    OPTIMISTIC_TOUCH_DIAGNOSTIC = "optimistic_touch_diagnostic"


class TimeInForce(StrEnum):
    IOC = "ioc"
    BAR = "bar"
    GTC = "gtc"


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    schema_version: str
    dataset_id: str
    canonical_sha256: str
    code_commit: str
    engine_version: str
    strategy_id: str
    strategy_config: tuple[tuple[str, str], ...]
    initial_cash: Decimal
    timing_policy: TimingPolicy
    limit_fill_policy: LimitFillPolicy
    default_time_in_force: TimeInForce
    max_active_candles: int
    random_seed: int
    simulation_config_sha256: str
```

```python
class OrderSide(StrEnum):
    BUY = "buy"
    SELL_TO_CLOSE = "sell_to_close"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    time_in_force: TimeInForce


@dataclass(frozen=True, slots=True)
class SimulatedOrder:
    order_id: str
    decision_sequence: int
    intent_sequence: int
    created_candle_index: int
    eligible_candle_index: int
    expires_after_candle_index: int
    side: OrderSide
    order_type: OrderType
    requested_quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal | None
    time_in_force: TimeInForce
    status: OrderStatus

    @property
    def remaining_quantity(self) -> Decimal:
        return self.requested_quantity - self.filled_quantity
```

```python
@dataclass(frozen=True, slots=True)
class Fill:
    fill_id: str
    order_id: str
    candle_index: int
    candle_open_time: datetime
    quantity: Decimal
    reference_price: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    spread_cost: Decimal
    slippage_cost: Decimal
    price_was_rounded: bool
    quantity_was_rounded: bool
```

```python
@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    cash: Decimal
    reserved_cash: Decimal
    position_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    cumulative_fees: Decimal
    cumulative_execution_costs: Decimal
    marked_equity: Decimal
    peak_equity: Decimal
    drawdown: Decimal

    @classmethod
    def initial(cls, cash: Decimal) -> "AccountSnapshot":
        return cls(cash, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
                   Decimal("0"), Decimal("0"), cash, cash, Decimal("0"))


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    sequence: int
    event_type: str
    order_id: str | None
    fill_id: str | None
    cash_delta: Decimal
    position_delta: Decimal
    fee_delta: Decimal
    resulting_cash: Decimal
    resulting_position: Decimal
```

Validation must enforce lowercase 64-character SHA-256 digests, a 40-character lowercase Git commit, non-empty identifiers, finite values, positive requested/fill quantities, non-negative balances, and `0 <= filled_quantity <= requested_quantity`.

- [ ] **Step 4: Run focused tests and static checks**

```bash
uv run pytest tests/unit/domain/test_experiment.py tests/unit/domain/test_order.py tests/unit/domain/test_fill.py tests/unit/domain/test_account.py -q
uv run ruff format --check src/gemini_trading/domain tests/unit/domain
uv run ruff check src/gemini_trading/domain tests/unit/domain
uv run pyright src/gemini_trading/domain tests/unit/domain
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/domain tests/unit/domain reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add backtesting domain contracts"
```

---

### Task 3: Verified canonical dataset reader

**Files:**
- Create: `src/gemini_trading/research/dataset_reader.py`
- Create: `tests/unit/research/test_dataset_reader.py`
- Create: `tests/integration/test_research_dataset_reader.py`

**Interfaces:**
- Consumes: `LocalImmutableStore.read_dataset(dataset_id)`.
- Produces: `VerifiedDataset(manifest: DatasetManifest, candles: tuple[Candle, ...], canonical_bytes: bytes)`.
- Produces: `load_verified_dataset(store: LocalImmutableStore, dataset_id: str) -> VerifiedDataset`.

- [ ] **Step 1: Write failing parser and tamper tests**

```python
def test_reader_loads_completed_candles_and_verifies_identity(tmp_path: Path) -> None:
    dataset_id = write_known_canonical_fixture(tmp_path)
    result = load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id)
    assert result.manifest.dataset_id == dataset_id
    assert len(result.candles) == 3
    assert all(candle.completed for candle in result.candles)


def test_reader_rejects_tampered_canonical_bytes(tmp_path: Path) -> None:
    dataset_id = write_known_canonical_fixture(tmp_path)
    candle_path = tmp_path / "data" / "canonical" / dataset_id / "candles.jsonl"
    candle_path.write_bytes(candle_path.read_bytes() + b"{}\n")
    with pytest.raises(DatasetVerificationError, match="canonical"):
        load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id)
```

The fixture helper must use the production `serialize_candles`, `build_dataset_manifest`, and `serialize_dataset_manifest` functions rather than handwritten identities.

- [ ] **Step 2: Run focused tests and confirm failure**

```bash
uv run pytest tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py -q
```

Expected: missing `dataset_reader` module.

- [ ] **Step 3: Implement strict dataset loading**

`dataset_reader.py` must:

1. call `store.read_dataset(dataset_id)`;
2. parse the deterministic dataset manifest JSON;
3. reconstruct `DatasetManifest`, `Instrument`, and `Timeframe`;
4. verify `manifest.dataset_id == dataset_id`;
5. verify `sha256(canonical_bytes) == manifest.canonical_sha256`;
6. verify `dataset_id(manifest.schema_version, canonical_bytes) == dataset_id`;
7. parse each non-empty JSONL row into `Candle`;
8. reject unknown/missing fields, invalid Decimals, invalid UTC timestamps, incomplete candles, wrong identity/timeframe/provider, duplicates, reversals, and continuity gaps;
9. call the existing canonical candle validator;
10. return immutable tuples only.

Required public contract:

```python
@dataclass(frozen=True, slots=True)
class VerifiedDataset:
    manifest: DatasetManifest
    candles: tuple[Candle, ...]
    canonical_bytes: bytes


def load_verified_dataset(
    store: LocalImmutableStore,
    dataset_id_value: str,
) -> VerifiedDataset:
    ...
```

Convert expected parsing/storage exceptions into `DatasetVerificationError` with safe messages; do not include absolute paths or raw payloads.

- [ ] **Step 4: Run focused and market-data regression checks**

```bash
uv run pytest tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py -q
uv run pytest tests/unit/data tests/integration/test_replay_without_network.py -q
uv run ruff format --check src/gemini_trading/research/dataset_reader.py tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py
uv run ruff check src/gemini_trading/research/dataset_reader.py tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py
uv run pyright src/gemini_trading/research/dataset_reader.py tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/dataset_reader.py tests/unit/research/test_dataset_reader.py tests/integration/test_research_dataset_reader.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add verified research dataset reader"
```

---

### Task 4: Simulation configuration and deterministic experiment identity

**Files:**
- Create: `src/gemini_trading/research/config.py`
- Create: `src/gemini_trading/research/identity.py`
- Create: `tests/unit/research/test_config.py`
- Create: `tests/property/test_experiment_identity.py`

**Interfaces:**
- Produces: `SimulationConfig`.
- Produces: `build_experiment_manifest(...) -> ExperimentManifest`.
- Produces: `serialize_experiment_manifest(manifest) -> bytes`.
- Produces: `experiment_id(manifest) -> str`.

- [ ] **Step 1: Write failing validation and identity properties**

```python
def test_official_config_rejects_zero_costs() -> None:
    with pytest.raises(InvalidExperimentConfigError, match="official"):
        SimulationConfig.official(
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            half_spread_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            latency_bars=0,
            price_tick=Decimal("0.01"),
            quantity_step=Decimal("0.0001"),
            min_quantity=Decimal("0.0001"),
            min_notional=Decimal("5"),
            max_volume_participation=Decimal("0.01"),
        )


@given(st.permutations([("b", "2"), ("a", "1")]))
def test_strategy_config_order_does_not_change_experiment_identity(items: list[tuple[str, str]]) -> None:
    manifest = make_manifest(strategy_config=tuple(items))
    assert experiment_id(manifest) == experiment_id(
        replace(manifest, strategy_config=(("a", "1"), ("b", "2")))
    )
```

- [ ] **Step 2: Run and confirm missing modules**

```bash
uv run pytest tests/unit/research/test_config.py tests/property/test_experiment_identity.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement exact configuration and identity rules**

`SimulationConfig` must contain:

```python
@dataclass(frozen=True, slots=True)
class SimulationConfig:
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    half_spread_bps: Decimal
    slippage_bps: Decimal
    latency_bars: int
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_volume_participation: Decimal
    max_active_candles: int
    timing_policy: TimingPolicy
    limit_fill_policy: LimitFillPolicy
    default_time_in_force: TimeInForce
    promotable: bool
```

Provide an `official(...)` classmethod that supplies `max_active_candles=3`, `timing_policy=NEXT_CANDLE`, `limit_fill_policy=CONSERVATIVE`, `default_time_in_force=BAR`, and `promotable=True` unless explicitly overridden.

Validation rules:

- rates and basis points are finite and non-negative;
- ticks, steps, minima are finite and positive;
- `0 < max_volume_participation <= 1`;
- latency is non-negative;
- max active candles is positive;
- `promotable=True` requires `NEXT_CANDLE`, `CONSERVATIVE`, and at least one non-zero fee/spread/slippage component;
- diagnostic policies force `promotable=False`.

Identity serialization must use canonical JSON and normalize `strategy_config` by unique key sort. The experiment ID is:

```python
hashlib.sha256(serialize_experiment_manifest(manifest)).hexdigest()
```

`build_experiment_manifest` must record the verified dataset ID/hash, clean 40-character code commit, fixed engine version `research-engine-v1`, strategy ID/config, initial cash, random seed, policy values, and SHA-256 of canonical simulation-config bytes.

- [ ] **Step 4: Run tests and deterministic property checks**

```bash
uv run pytest tests/unit/research/test_config.py tests/property/test_experiment_identity.py -q
uv run ruff format --check src/gemini_trading/research tests/unit/research/test_config.py tests/property/test_experiment_identity.py
uv run ruff check src/gemini_trading/research tests/unit/research/test_config.py tests/property/test_experiment_identity.py
uv run pyright src/gemini_trading/research tests/unit/research/test_config.py tests/property/test_experiment_identity.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/config.py src/gemini_trading/research/identity.py tests/unit/research/test_config.py tests/property/test_experiment_identity.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add deterministic experiment identity"
```

---

### Task 5: Conservative precision, cost, and liquidity primitives

**Files:**
- Create: `src/gemini_trading/execution/__init__.py`
- Create: `src/gemini_trading/execution/simulator/__init__.py`
- Create: `src/gemini_trading/execution/simulator/precision.py`
- Create: `src/gemini_trading/execution/simulator/costs.py`
- Create: `src/gemini_trading/execution/simulator/liquidity.py`
- Create: `tests/unit/execution/simulator/test_precision.py`
- Create: `tests/unit/execution/simulator/test_costs.py`
- Create: `tests/property/test_liquidity.py`

**Interfaces:**
- Produces: `round_quantity_down`, `round_fill_price`, `market_fill_costs`, `available_quantity`.
- No function may use binary floating point.

- [ ] **Step 1: Write failing primitive tests**

```python
def test_quantity_rounds_down_to_step() -> None:
    assert round_quantity_down(Decimal("1.23456"), Decimal("0.001")) == Decimal("1.234")


def test_buy_price_rounds_up_and_sell_price_rounds_down() -> None:
    assert round_fill_price(Decimal("100.001"), Decimal("0.01"), OrderSide.BUY) == Decimal("100.01")
    assert (
        round_fill_price(Decimal("100.009"), Decimal("0.01"), OrderSide.SELL_TO_CLOSE)
        == Decimal("100.00")
    )


def test_market_buy_costs_are_adverse_and_exact() -> None:
    result = market_fill_costs(
        reference_price=Decimal("100"),
        quantity=Decimal("2"),
        side=OrderSide.BUY,
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        fee_rate=Decimal("0.001"),
    )
    assert result.fill_price == Decimal("100.1500")
    assert result.notional == Decimal("200.3000")
    assert result.fee == Decimal("0.2003000")
```

Hypothesis property: `available_quantity(volume, participation, already_consumed)` is never negative, never exceeds remaining candle volume allocation, and is deterministic.

- [ ] **Step 2: Run and confirm missing implementation**

```bash
uv run pytest tests/unit/execution/simulator tests/property/test_liquidity.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement pure Decimal primitives**

Required signatures:

```python
def round_quantity_down(quantity: Decimal, step: Decimal) -> Decimal:
    units = (quantity / step).to_integral_value(rounding=ROUND_FLOOR)
    return units * step


def round_fill_price(price: Decimal, tick: Decimal, side: OrderSide) -> Decimal:
    rounding = ROUND_CEILING if side is OrderSide.BUY else ROUND_FLOOR
    units = (price / tick).to_integral_value(rounding=rounding)
    return units * tick
```

```python
@dataclass(frozen=True, slots=True)
class FillCosts:
    reference_price: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    spread_cost: Decimal
    slippage_cost: Decimal


def market_fill_costs(
    *,
    reference_price: Decimal,
    quantity: Decimal,
    side: OrderSide,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
    fee_rate: Decimal,
) -> FillCosts:
    direction = Decimal("1") if side is OrderSide.BUY else Decimal("-1")
    spread = reference_price * half_spread_bps / Decimal("10000")
    slippage = reference_price * slippage_bps / Decimal("10000")
    fill_price = reference_price + direction * (spread + slippage)
    notional = fill_price * quantity
    return FillCosts(
        reference_price,
        fill_price,
        notional,
        notional * fee_rate,
        spread * quantity,
        slippage * quantity,
    )
```

```python
def available_quantity(
    *,
    candle_volume: Decimal,
    participation: Decimal,
    already_consumed: Decimal,
) -> Decimal:
    cap = candle_volume * participation
    return max(Decimal("0"), cap - already_consumed)
```

Every function validates finite positive inputs and raises `ValueError` before arithmetic when invalid.

- [ ] **Step 4: Run focused tests and static checks**

```bash
uv run pytest tests/unit/execution/simulator tests/property/test_liquidity.py -q
uv run ruff format --check src/gemini_trading/execution tests/unit/execution tests/property/test_liquidity.py
uv run ruff check src/gemini_trading/execution tests/unit/execution tests/property/test_liquidity.py
uv run pyright src/gemini_trading/execution tests/unit/execution tests/property/test_liquidity.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/execution tests/unit/execution tests/property/test_liquidity.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add conservative execution primitives"
```

---

### Task 6: Deterministic market and limit fill simulator

**Files:**
- Create: `src/gemini_trading/execution/simulator/fills.py`
- Create: `tests/unit/execution/simulator/test_fills.py`
- Create: `tests/property/test_fill_determinism.py`

**Interfaces:**
- Consumes: `SimulatedOrder`, `Candle`, `AccountSnapshot`, `SimulationConfig`.
- Produces: `FillEvaluation(order: SimulatedOrder, fill: Fill | None, reason: str, consumed_volume: Decimal)`.
- Produces: `evaluate_order(order, candle, account, config, candle_index, consumed_volume, market_reference_price=None) -> FillEvaluation`.

- [ ] **Step 1: Write failing official and diagnostic fill tests**

```python
def test_conservative_buy_limit_requires_strict_cross() -> None:
    order = buy_limit(limit_price=Decimal("100"))
    candle = candle_with(low=Decimal("100"), high=Decimal("110"))
    result = evaluate_order(order, candle, account(), official_config(), 0, Decimal("0"))
    assert result.fill is None
    assert result.reason == "limit_not_strictly_crossed"


def test_optimistic_touch_policy_fills_touch_but_is_non_promotable() -> None:
    config = replace(
        official_config(),
        limit_fill_policy=LimitFillPolicy.OPTIMISTIC_TOUCH_DIAGNOSTIC,
        promotable=False,
    )
    result = evaluate_order(
        buy_limit(limit_price=Decimal("100")),
        candle_with(low=Decimal("100")),
        account(),
        config,
        0,
        Decimal("0"),
    )
    assert result.fill is not None


def test_partial_fill_is_capped_by_volume_participation_and_cash() -> None:
    result = evaluate_order(
        market_buy(quantity=Decimal("10")),
        candle_with(open=Decimal("100"), volume=Decimal("20")),
        account(cash=Decimal("350")),
        official_config(max_volume_participation=Decimal("0.25")),
        0,
        Decimal("0"),
    )
    assert result.fill is not None
    assert Decimal("0") < result.fill.quantity <= Decimal("3.5")
```

- [ ] **Step 2: Run and confirm missing simulator failure**

```bash
uv run pytest tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py -q
```

Expected: missing `fills` module.

- [ ] **Step 3: Implement deterministic evaluation**

Rules in `evaluate_order`:

1. return `not_yet_eligible` before `eligible_candle_index`;
2. return `expired` after `expires_after_candle_index`;
3. market reference is `market_reference_price` when explicitly supplied by the diagnostic engine path, otherwise the eligible candle open;
4. conservative buy limit requires `candle.low < limit_price`;
5. conservative sell limit requires `candle.high > limit_price`;
6. optimistic diagnostic mode permits equality;
7. limit fill price is exactly the limit price; spread/slippage cost fields are zero and maker fee applies;
8. market fill applies adverse spread/slippage and taker fee;
9. candidate quantity is the minimum of order remainder and available volume participation;
10. buy quantity is also capped by available cash including fee;
11. sell quantity is capped by owned position;
12. buy affordability is `cash / (fill_price * (1 + fee_rate))`, then rounds down to the quantity step;
13. quantity rounds down to step and must satisfy minimum quantity/notional;
14. fill price uses adverse tick rounding and the fill records both price/quantity rounding booleans;
15. a limit price that is not tick-aligned is rejected; it is never silently improved, and any rounded execution may not violate the limit;
16. fill ID is `sha256(f"{order_id}:{candle_index}:{filled_quantity}:{fill_price}".encode()).hexdigest()`;
17. no random source, system clock, host state, or network is read.

Return domain reasons such as `filled`, `partial_fill`, `insufficient_cash`, `insufficient_position`, `below_min_quantity`, `below_min_notional`, `no_liquidity`, and `limit_not_strictly_crossed`.

- [ ] **Step 4: Run focused and property tests**

```bash
uv run pytest tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py -q
uv run ruff format --check src/gemini_trading/execution/simulator/fills.py tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py
uv run ruff check src/gemini_trading/execution/simulator/fills.py tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py
uv run pyright src/gemini_trading/execution/simulator/fills.py tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py
```

Expected: all pass and repeated evaluations compare equal.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/execution/simulator/fills.py tests/unit/execution/simulator/test_fills.py tests/property/test_fill_determinism.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add deterministic fill simulation"
```

---

### Task 7: Account transitions, ledger reconciliation, and invariants

**Files:**
- Create: `src/gemini_trading/research/accounting.py`
- Create: `tests/unit/research/test_accounting.py`
- Create: `tests/property/test_accounting_invariants.py`

**Interfaces:**
- Produces: `apply_fill(account, order, fill, sequence) -> tuple[AccountSnapshot, LedgerEntry]`.
- Produces: `mark_to_market(account, close_price) -> AccountSnapshot`.
- Produces: `verify_reconciliation(initial_cash, account, ledger) -> None`.

- [ ] **Step 1: Write failing buy/sell and conservation tests**

```python
def test_round_trip_reconciles_cash_position_fees_and_realized_pnl() -> None:
    initial = AccountSnapshot.initial(Decimal("1000"))
    after_buy, buy_entry = apply_fill(initial, buy_order(), buy_fill(), 1)
    after_sell, sell_entry = apply_fill(after_buy, sell_order(), sell_fill(), 2)
    verify_reconciliation(Decimal("1000"), after_sell, (buy_entry, sell_entry))
    assert after_sell.position_quantity == Decimal("0")
    assert after_sell.cash == Decimal("1017.80")
    assert after_sell.realized_pnl == Decimal("17.80")


def test_sell_above_owned_position_fails_closed() -> None:
    with pytest.raises(AccountingInvariantError, match="owned position"):
        apply_fill(account(position_quantity=Decimal("1")), sell_order(), fill(quantity=Decimal("2")), 1)
```

Hypothesis properties must prove non-negative cash/position, ledger delta conservation, and deterministic replay for generated valid buy/sell sequences.

- [ ] **Step 2: Run and confirm missing accounting module**

```bash
uv run pytest tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement exact accounting transitions**

For a buy:

```text
cash_delta = -(fill.notional + fill.fee)
position_delta = +fill.quantity
new_average_entry = (
    old_quantity * old_average_entry + fill.notional + fill.fee
) / new_quantity
```

For sell-to-close:

```text
cash_delta = fill.notional - fill.fee
position_delta = -fill.quantity
cost_basis_released = old_average_entry * fill.quantity
realized_pnl_delta = fill.notional - fill.fee - cost_basis_released
```

`average_entry_price` becomes zero when the position reaches zero. `reserved_cash` remains zero in this first slice because the engine rejects conflicting concurrent intents and rechecks affordability at every fill; future portfolio work may introduce explicit reservation. `cumulative_execution_costs` increases by `spread_cost + slippage_cost`; `cumulative_fees` increases once per fill.

`mark_to_market` computes:

```text
marked_equity = cash + position_quantity * close_price
peak_equity = max(previous_peak_equity, marked_equity)
drawdown = 0 when peak_equity is zero else (peak_equity - marked_equity) / peak_equity
```

`verify_reconciliation` sums every ledger delta, confirms final balances, confirms unique fill IDs, and raises `AccountingInvariantError` on any contradiction.

- [ ] **Step 4: Run focused and property tests**

```bash
uv run pytest tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py -q
uv run ruff format --check src/gemini_trading/research/accounting.py tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py
uv run ruff check src/gemini_trading/research/accounting.py tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py
uv run pyright src/gemini_trading/research/accounting.py tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/accounting.py tests/unit/research/test_accounting.py tests/property/test_accounting_invariants.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add deterministic portfolio accounting"
```

---

### Task 8: Read-only strategy contract and scripted fixture

**Files:**
- Create: `src/gemini_trading/research/contracts.py`
- Create: `src/gemini_trading/research/fixture_strategy.py`
- Create: `tests/unit/research/test_strategy_contract.py`
- Create: `tests/regression/test_strategy_cannot_access_future_data.py`

**Interfaces:**
- Produces: `StrategyContext`, `StrategyDecision`, `Strategy` protocol.
- Produces: `ScriptedFixtureStrategy`.
- Strategy input contains one completed candle and immutable current state only.

- [ ] **Step 1: Write failing isolation tests**

```python
def test_context_contains_no_future_iterator_or_provider() -> None:
    context = make_context()
    assert not hasattr(context, "future_candles")
    assert not hasattr(context, "provider")
    assert context.candle.completed is True


def test_scripted_fixture_is_deterministic_and_non_production() -> None:
    strategy = ScriptedFixtureStrategy(
        script=((0, (market_buy(Decimal("1")),)), (2, (market_sell(Decimal("1")),)))
    )
    first = strategy.on_candle(make_context(candle_index=0))
    second = strategy.on_candle(make_context(candle_index=0))
    assert first == second
    assert strategy.strategy_id == "fixture.scripted.v1"
    assert strategy.production_eligible is False
```

- [ ] **Step 2: Run and confirm missing contract failure**

```bash
uv run pytest tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement the strategy boundary**

```python
@dataclass(frozen=True, slots=True)
class StrategyContext:
    candle_index: int
    candle: Candle
    account: AccountSnapshot
    active_orders: tuple[SimulatedOrder, ...]


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    decision_sequence: int
    candle_index: int
    candle_open_time: datetime
    intents: tuple[OrderIntent, ...]


class Strategy(Protocol):
    strategy_id: str
    production_eligible: bool

    def configuration(self) -> tuple[tuple[str, str], ...]: ...
    def on_candle(self, context: StrategyContext) -> tuple[OrderIntent, ...]: ...
```

`ScriptedFixtureStrategy` accepts an immutable tuple mapping candle indexes to intents, rejects duplicate indexes, exposes deterministic sorted configuration JSON, and returns only the exact tuple for the current index. It must contain no price prediction, parameter optimization, or production eligibility.

- [ ] **Step 4: Run focused and regression tests**

```bash
uv run pytest tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py -q
uv run ruff format --check src/gemini_trading/research/contracts.py src/gemini_trading/research/fixture_strategy.py tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py
uv run ruff check src/gemini_trading/research/contracts.py src/gemini_trading/research/fixture_strategy.py tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py
uv run pyright src/gemini_trading/research/contracts.py src/gemini_trading/research/fixture_strategy.py tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/contracts.py src/gemini_trading/research/fixture_strategy.py tests/unit/research/test_strategy_contract.py tests/regression/test_strategy_cannot_access_future_data.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add isolated strategy contract"
```

---

### Task 9: Chronological engine, order lifecycle, and idempotency

**Files:**
- Create: `src/gemini_trading/research/engine.py`
- Create: `tests/unit/research/test_engine.py`
- Create: `tests/integration/test_backtest_event_order.py`
- Create: `tests/regression/test_duplicate_cycle_idempotency.py`

**Interfaces:**
- Consumes: `VerifiedDataset`, `ExperimentManifest`, `SimulationConfig`, `Strategy`.
- Produces: `BacktestEvidence`.
- Produces: `run_backtest(...) -> BacktestEvidence`.

- [ ] **Step 1: Write failing event-order and duplicate-cycle tests**

```python
def test_official_decision_on_candle_zero_cannot_fill_before_candle_one() -> None:
    evidence = run_fixture_backtest(scripted_market_buy_at(0))
    assert evidence.decisions[0].candle_index == 0
    assert evidence.orders[0].eligible_candle_index == 1
    assert evidence.fills[0].candle_index == 1


def test_duplicate_event_identity_does_not_create_duplicate_orders() -> None:
    engine = build_engine()
    engine.process_candle(0, candle_zero())
    with pytest.raises(ChronologyViolationError, match="duplicate"):
        engine.process_candle(0, candle_zero())
    assert len(engine.evidence.orders) == 1
```

Add tests for IOC/BAR cancellation, GTC expiry, conflicting intents, partial fills across candles, sell-to-close validation, and experiment-end cancellation.

- [ ] **Step 2: Run and confirm missing engine failure**

```bash
uv run pytest tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement the event-driven kernel**

Required evidence contract:

```python
@dataclass(frozen=True, slots=True)
class BacktestEvidence:
    experiment_manifest: ExperimentManifest
    decisions: tuple[StrategyDecision, ...]
    orders: tuple[SimulatedOrder, ...]
    fills: tuple[Fill, ...]
    ledger: tuple[LedgerEntry, ...]
    account_series: tuple[AccountSnapshot, ...]
    rejection_records: tuple[dict[str, object], ...]
    terminal_account: AccountSnapshot
```

Per candle `T`, official ordering is:

1. verify completed, identity-matching, strictly increasing candle;
2. evaluate active orders eligible on `T` in deterministic `order_id` order using one shared consumed-volume counter;
3. apply fills and order status transitions;
4. expire IOC/BAR/GTC remainders according to exact policy;
5. mark account to candle close;
6. construct immutable `StrategyContext`;
7. call strategy once;
8. validate intents, rejecting more than one active buy or more than one active sell-to-close and rejecting mutually conflicting simultaneous intents;
9. derive deterministic order IDs from experiment ID, decision sequence, and intent sequence;
10. set official `eligible_candle_index = T + 1 + latency_bars`;
11. set bounded expiry index;
12. append one decision record.

For `SAME_CLOSE_DIAGNOSTIC`, after intent validation perform a separate clearly labelled post-decision fill pass using candle close as market reference. Set `promotable=False` and record the diagnostic policy in every artifact.

At dataset end, cancel remaining active orders, mark terminal equity with the last close, call reconciliation, and return immutable evidence. Any integrity exception produces no trusted completed evidence.

- [ ] **Step 4: Run engine, integration, and regression checks**

```bash
uv run pytest tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py -q
uv run pytest tests/regression/test_strategy_cannot_access_future_data.py tests/property/test_accounting_invariants.py tests/property/test_fill_determinism.py -q
uv run ruff format --check src/gemini_trading/research/engine.py tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py
uv run ruff check src/gemini_trading/research/engine.py tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py
uv run pyright src/gemini_trading/research/engine.py tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/engine.py tests/unit/research/test_engine.py tests/integration/test_backtest_event_order.py tests/regression/test_duplicate_cycle_idempotency.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add chronological backtesting engine"
```

---

### Task 10: Deterministic metrics, artifacts, and result identity

**Files:**
- Create: `src/gemini_trading/research/metrics.py`
- Create: `src/gemini_trading/research/artifacts.py`
- Create: `tests/unit/research/test_metrics.py`
- Create: `tests/unit/research/test_artifacts.py`
- Create: `tests/property/test_result_identity.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `BacktestMetrics`.
- Produces: `build_artifacts(evidence) -> ResearchArtifacts`.
- Produces: `LocalResearchStore.write(artifacts) -> tuple[tuple[str, Path], ...]`.
- Produces result identity from canonical core artifact hashes.

- [ ] **Step 1: Write failing metrics and byte-equivalence tests**

```python
def test_metrics_report_gross_net_costs_drawdown_and_counts() -> None:
    metrics = calculate_metrics(known_evidence())
    assert metrics.starting_equity == Decimal("1000")
    assert metrics.ending_equity == Decimal("1017.80")
    assert metrics.net_return == Decimal("0.0178")
    assert metrics.total_fees == Decimal("2.20")
    assert metrics.order_count == 2
    assert metrics.trade_count == 1


def test_identical_evidence_produces_byte_identical_artifacts() -> None:
    first = build_artifacts(known_evidence())
    second = build_artifacts(known_evidence())
    assert first == second
    assert first.result_id == second.result_id
```

- [ ] **Step 2: Run and confirm missing modules**

```bash
uv run pytest tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement deterministic evidence generation**

`BacktestMetrics` fields:

```python
@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    starting_equity: Decimal
    ending_equity: Decimal
    gross_return: Decimal
    net_return: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    total_execution_costs: Decimal
    maximum_drawdown: Decimal
    exposure_fraction: Decimal
    order_count: int
    rejection_count: int
    fill_count: int
    partial_fill_count: int
    trade_count: int
    win_rate: Decimal | None
```

Artifacts must include canonical bytes for:

- `experiment-manifest.json`;
- `decisions.jsonl`;
- `orders.jsonl`;
- `rejections.jsonl`;
- `fills.jsonl`;
- `cash-ledger.jsonl`;
- `account-series.jsonl`;
- `trades.jsonl`;
- `metrics.json`;
- `result-manifest.json`;
- `verification.json`.

The result manifest contains schema version, experiment ID, sorted `(artifact_name, sha256)` pairs, terminal status, promotable flag, and `result_id`. Compute `result_id` from canonical result-manifest content excluding its own `result_id`, then serialize the final manifest.

Use the existing `write_immutable` function and store beneath:

```text
data/research/<experiment_id>/
```

Conflicting bytes raise `ArtifactConflictError`. Identical reruns are accepted without mutation. Add `data/research/` to `.gitignore`.

- [ ] **Step 4: Run focused and deterministic property tests**

```bash
uv run pytest tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py -q
uv run ruff format --check src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py
uv run ruff check src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py
uv run pyright src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .gitignore src/gemini_trading/research/metrics.py src/gemini_trading/research/artifacts.py tests/unit/research/test_metrics.py tests/unit/research/test_artifacts.py tests/property/test_result_identity.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add immutable backtest evidence"
```

---

### Task 11: Provider-free replay and independent verification

**Files:**
- Create: `src/gemini_trading/research/replay.py`
- Create: `src/gemini_trading/research/verification.py`
- Create: `tests/integration/test_backtest_replay_without_network.py`
- Create: `tests/unit/research/test_verification.py`
- Create: `tests/regression/test_tampered_backtest_artifacts.py`

**Interfaces:**
- Produces: `ReplayService.replay(experiment_id) -> ResearchArtifacts`.
- Produces: `ResearchVerificationService.verify(experiment_id) -> ResearchVerificationResult`.

- [ ] **Step 1: Write failing offline and tamper tests**

```python
def test_replay_uses_no_network_and_reproduces_all_core_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment_id = write_completed_fixture_experiment(tmp_path)
    monkeypatch.setattr(socket, "create_connection", fail_if_called)
    replayed = ReplayService(LocalImmutableStore(tmp_path), LocalResearchStore(tmp_path)).replay(
        experiment_id
    )
    assert replayed.experiment_id == experiment_id


def test_verification_rejects_modified_fill_ledger(tmp_path: Path) -> None:
    experiment_id = write_completed_fixture_experiment(tmp_path)
    path = tmp_path / "data" / "research" / experiment_id / "fills.jsonl"
    path.write_bytes(path.read_bytes() + b"{}\n")
    with pytest.raises(ReplayMismatchError, match="fills"):
        ResearchVerificationService(tmp_path).verify(experiment_id)
```

- [ ] **Step 2: Run and confirm missing replay/verification modules**

```bash
uv run pytest tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py -q
```

Expected: collection failure.

- [ ] **Step 3: Implement replay and independent verification**

Replay must:

1. read the stored experiment manifest;
2. reconstruct `SimulationConfig`;
3. load and verify the canonical dataset without network;
4. rebuild only the registered `fixture.scripted.v1` strategy in this milestone;
5. rerun the engine;
6. regenerate canonical artifacts in memory;
7. compare every core artifact byte-for-byte;
8. reject code-commit mismatch unless the current clean Git HEAD equals the recorded commit;
9. return regenerated artifacts without overwriting conflicting evidence.

Verification must independently recompute:

- canonical dataset linkage and hashes;
- experiment-manifest bytes and experiment ID;
- each artifact SHA-256;
- fill/order/decision referential integrity;
- ledger reconciliation and accounting invariants;
- metrics from ledger and account series;
- result ID;
- replay equivalence;
- terminal status and promotable policy.

`ResearchVerificationResult` contains experiment ID, result ID, terminal status, promotable flag, and a sorted tuple of passed check names.

- [ ] **Step 4: Run replay, tamper, and regression tests**

```bash
uv run pytest tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py -q
uv run pytest tests/property/test_result_identity.py tests/property/test_accounting_invariants.py -q
uv run ruff format --check src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py
uv run ruff check src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py
uv run pyright src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py
```

Expected: all pass and network sentinel remains unused.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/research/replay.py src/gemini_trading/research/verification.py tests/integration/test_backtest_replay_without_network.py tests/unit/research/test_verification.py tests/regression/test_tampered_backtest_artifacts.py reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add backtest replay and verification"
```

---

### Task 12: Safe research CLI and complete acceptance workflow

**Files:**
- Create: `src/gemini_trading/cli/research.py`
- Modify: `src/gemini_trading/cli/main.py`
- Create: `tests/unit/cli/test_research.py`
- Create: `tests/acceptance/test_research_backtest_cli.py`
- Create: `tests/fixtures/research/official-fixture-config.json`
- Create: `tests/fixtures/research/diagnostic-fixture-config.json`

**Interfaces:**
- Adds commands:
  - `gemini-trading research backtest`
  - `gemini-trading research replay`
  - `gemini-trading research verify`
- CLI emits one compact safe JSON object and exit code `0` on success, `2` on classified failure.

- [ ] **Step 1: Write failing parser and end-to-end CLI tests**

```python
def test_research_backtest_cli_emits_safe_completed_payload(tmp_path: Path) -> None:
    dataset_id = write_cli_dataset(tmp_path)
    result = run_cli(
        "research",
        "backtest",
        "--dataset-id",
        dataset_id,
        "--config",
        "tests/fixtures/research/official-fixture-config.json",
        "--project-root",
        str(PROJECT_ROOT),
        "--output-root",
        str(tmp_path),
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "completed"
    assert payload["promotable"] is True
    assert "experiment_id" in payload
    assert "result_id" in payload
    assert str(tmp_path.resolve()) not in result.stdout


def test_research_cli_rejects_live_mode_before_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_TRADING_MODE", "live")
    result = run_cli("research", "verify", "--experiment-id", "a" * 64, "--output-root", ".")
    assert result.returncode == 2
    assert "UnsafeExecutionModeError" in result.stderr
```

- [ ] **Step 2: Run and confirm unsupported-command failure**

```bash
uv run pytest tests/unit/cli/test_research.py tests/acceptance/test_research_backtest_cli.py -q
```

Expected: CLI reports unsupported `research` command.

- [ ] **Step 3: Implement safe command handlers**

Parser arguments:

```text
research backtest --dataset-id ID --config FILE --project-root DIR --output-root DIR
research replay --experiment-id ID --project-root DIR --output-root DIR
research verify --experiment-id ID --project-root DIR --output-root DIR
```

`research.py` must:

- validate identities and paths;
- load runtime policy before reading dataset/config or constructing services;
- require a clean Git worktree and resolve exact lowercase 40-character HEAD;
- parse only the documented JSON config schema;
- build `ScriptedFixtureStrategy`;
- run backtest, write artifacts, and return safe relative paths;
- replay and verify without network;
- never emit strategy internals beyond fixture identity, raw artifact contents, environment dumps, absolute paths, or traceback text.

Modify `main.py` to dispatch `research` and catch `ResearchError`. Acceptance tests call `main(argv)` in process and monkeypatch only the clean-Git-head resolver to a fixed 40-character test SHA; production code always runs the real clean-worktree check.

The broad exception handler emits `{"status":"failed","error":{"type":"InternalError","message":"research command failed"}}` for research commands and preserves the existing market-data message for market-data commands.

- [ ] **Step 4: Run CLI acceptance and safety regression tests**

```bash
uv run pytest tests/unit/cli/test_research.py tests/acceptance/test_research_backtest_cli.py -q
uv run pytest tests/acceptance/test_market_data_cli.py tests/unit/cli/test_market_data.py -q
uv run ruff format --check src/gemini_trading/cli tests/unit/cli tests/acceptance/test_research_backtest_cli.py
uv run ruff check src/gemini_trading/cli tests/unit/cli tests/acceptance/test_research_backtest_cli.py
uv run pyright src/gemini_trading/cli tests/unit/cli tests/acceptance/test_research_backtest_cli.py
```

Expected: all pass; existing market-data CLI remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/gemini_trading/cli tests/unit/cli/test_research.py tests/acceptance/test_research_backtest_cli.py tests/fixtures/research reports/verification/deterministic-backtesting-progress.md
git commit -m "feat: add safe research backtest CLI"
```

---

### Task 13: Hostile regression and milestone acceptance suite

**Files:**
- Create: `tests/regression/test_backtesting_prototype_defects.py`
- Create: `tests/acceptance/test_deterministic_backtesting_milestone.py`
- Create: `tests/property/test_order_lifecycle.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Produces one milestone acceptance suite proving the approved design rather than profitability.

- [ ] **Step 1: Add failing hostile acceptance tests**

The regression file must prove:

```python
def test_incomplete_candle_never_reaches_strategy() -> None: ...
def test_trailing_future_outcome_is_never_invented() -> None: ...
def test_duplicate_decision_cycle_cannot_duplicate_order() -> None: ...
def test_sell_to_close_requires_owned_position() -> None: ...
def test_diagnostic_fill_policy_cannot_be_promotable() -> None: ...
def test_random_allocation_or_random_fill_is_absent() -> None: ...
def test_invalid_stop_entry_target_fields_are_not_part_of_engine_contract() -> None: ...
```

The acceptance test must run a fixed canonical dataset twice and assert:

```python
assert first.experiment_id == second.experiment_id
assert first.result_id == second.result_id
assert first.core_artifacts == second.core_artifacts
assert verified.promotable is True
assert verified.checks == tuple(sorted(verified.checks))
```

Property tests generate valid order lifecycle sequences and prove only allowed status transitions occur.

- [ ] **Step 2: Run and confirm the new suite exposes any remaining gaps**

```bash
uv run pytest tests/regression/test_backtesting_prototype_defects.py tests/property/test_order_lifecycle.py tests/acceptance/test_deterministic_backtesting_milestone.py -q
```

Expected before final fixes: at least one focused failure identifying the remaining acceptance gap; record the exact observed failure in the progress report.

- [ ] **Step 3: Make only the minimal acceptance fixes**

Modify only the component responsible for each observed failure. Do not add production strategy logic, portfolio optimization, risk governor, paper broker, credentials, or network behavior.

Add pytest markers to `pyproject.toml` only when needed:

```toml
markers = [
  "live_api: bounded public Binance Spot smoke test disabled by default",
  "research_acceptance: deterministic backtesting milestone acceptance",
]
```

Update `README.md` with:

```text
gemini-trading research backtest
gemini-trading research replay
gemini-trading research verify
```

State explicitly that the synthetic strategy is non-production, profitability is not established, official evidence is conservative, and live exchange submission remains disabled.

- [ ] **Step 4: Run the complete deterministic checkpoint**

```bash
uv run pytest -m "not live_api" -q
uv run pre-commit run --all-files
uv run pyright
uv run ruff format --check .
uv run ruff check .
uv build
uv run pip-audit
uv run detect-secrets scan --baseline .secrets.baseline
git diff --check
git status --short
```

Expected:

- deterministic suite passes;
- all hooks pass without changing files;
- Pyright, Ruff, build, audit, and secret scan pass;
- `git diff --check` emits no errors;
- `git status --short` shows only intentional milestone files before commit.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md tests/regression/test_backtesting_prototype_defects.py tests/property/test_order_lifecycle.py tests/acceptance/test_deterministic_backtesting_milestone.py reports/verification/deterministic-backtesting-progress.md
git commit -m "test: add deterministic backtesting acceptance gate"
```

---

### Task 14: Operations documentation, ADR, and exact-head evidence

**Files:**
- Create: `docs/architecture/adr/0003-deterministic-research-engine.md`
- Create: `docs/operations/deterministic-backtesting.md`
- Create: `docs/operations/deterministic-backtesting-step-verification.md`
- Create: `reports/verification/deterministic-backtesting-final.md`
- Modify: `reports/verification/deterministic-backtesting-progress.md`

**Interfaces:**
- Produces operator-facing commands, trust boundaries, limitations, and exact verification evidence.
- Does not claim strategy edge or readiness for real capital.

- [ ] **Step 1: Write documentation acceptance tests**

Create `tests/acceptance/test_deterministic_backtesting_documentation.py` asserting that the documents contain:

- exact command names;
- `RESEARCH_ONLY`;
- next-candle official timing;
- conservative limit fills;
- costs and partial fills;
- no credentials or exchange submission;
- provider-free replay;
- exact-head and merged-main verification;
- assistant advisory governance and human real-capital authorization;
- OHLCV queue/intrabar limitations;
- profitability not established.

Run:

```bash
uv run pytest tests/acceptance/test_deterministic_backtesting_documentation.py -q
```

Expected: fail because documents do not exist.

- [ ] **Step 2: Write the ADR and operator guide**

ADR decision:

- repository-native event-driven kernel;
- verified canonical dataset boundary;
- official conservative execution;
- deterministic content identities;
- independent replay and verification;
- fail-closed accounting;
- no live-capable behavior;
- known OHLCV, queue, intrabar, and market-impact limitations.

Operator guide includes exact PowerShell and POSIX examples for backtest, replay, and verify, the fixture config schema, output layout, safe failure behavior, and interpretation of `promotable`.

Step-verification protocol requires red/green focused evidence, checkpoint evidence, PR exact-head verification, merge, and exact merged-main verification before Issue #12 closure.

- [ ] **Step 3: Run documentation and complete project checks**

```bash
uv run pytest tests/acceptance/test_deterministic_backtesting_documentation.py -q
uv run pytest -m "not live_api" -q
uv run pre-commit run --all-files
uv run pyright
uv run ruff format --check .
uv run ruff check .
uv build
uv run pip-audit
uv run detect-secrets scan --baseline .secrets.baseline
git diff --check
```

Expected: all pass.

- [ ] **Step 4: Record exact pull-request-head evidence**

Record in `reports/verification/deterministic-backtesting-final.md`:

- exact branch and commit SHA;
- exact commands;
- observed counts and pass/fail outcomes;
- official and diagnostic policy separation;
- proof of provider-free replay;
- artifact/result byte equivalence;
- accounting reconciliation evidence;
- quality, gitleaks, dependency, build, and repository-policy results;
- untested live API smoke status;
- remaining limitations;
- statement that profitability and real-capital readiness are not established.

Commit:

```bash
git add docs/architecture/adr/0003-deterministic-research-engine.md docs/operations/deterministic-backtesting.md docs/operations/deterministic-backtesting-step-verification.md tests/acceptance/test_deterministic_backtesting_documentation.py reports/verification/deterministic-backtesting-progress.md reports/verification/deterministic-backtesting-final.md
git commit -m "docs: record deterministic backtesting evidence"
```

- [ ] **Step 5: Complete protected-main verification**

1. Open a pull request from `feature/deterministic-backtesting-engine` to `main`.
2. Require `quality` and `gitleaks`.
3. Verify the exact PR head using the complete command set from Step 3.
4. Review the cumulative diff for scope expansion, secrets, generated data, or live-capable behavior.
5. Merge only when all gates pass.
6. Verify the exact merged `main` SHA with the same deterministic, build, audit, secret, policy, replay, and clean-tree checks.
7. Add exact merged-main evidence to Issue #12.
8. Close Issue #12 only after the evidence is recorded and verified.
9. Open the next design-gate issue for Candidate Multi-Model Strategy v0.1; do not implement it inside this milestone.

Expected terminal state: protected `main` contains the verified deterministic research engine, Issue #12 is closed as completed, and no strategy profitability or live-trading claim has been made.

---

## Plan Self-Review

- **Spec coverage:** Every approved requirement maps to Tasks 1–14: chronology, look-ahead prevention, order/fill timing, Decimal accounting, fees/spread/slippage/latency, precision and minimums, partial fills, deterministic identity, immutable evidence, replay, verification, safe CLI, hostile tests, governance, and exact-head completion.
- **Scope:** The plan delivers one coherent working subsystem. Production strategy logic, portfolio construction, independent risk governance, paper brokerage, credentials, and live execution remain excluded.
- **Type consistency:** `SimulationConfig`, `ExperimentManifest`, `VerifiedDataset`, `Strategy`, `BacktestEvidence`, `ResearchArtifacts`, and verification result names remain consistent across all consuming tasks.
- **Ambiguity resolution:** Official evidence is always next-candle, strict-cross conservative, cost-bearing, and promotable only under those rules. Diagnostic policies are implemented only as explicitly non-promotable comparisons.
