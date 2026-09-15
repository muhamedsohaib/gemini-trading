"""End-to-end synthetic proof for Economic Data Fabric v1."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from gemini_trading.economics.data.asof import latest_visible_vintages
from gemini_trading.economics.data.dataset import (
    build_economic_dataset,
    write_economic_bundle,
)
from gemini_trading.economics.data.observation import EconomicObservation
from gemini_trading.economics.data.replay import replay_economic_bundle
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)
from gemini_trading.economics.data.storage import (
    LocalEconomicEvidenceStore,
    RawEvidenceInventory,
)
from gemini_trading.economics.data.verification import verify_economic_bundle

_MARKET_SERIES = "market.synthetic.risk_asset.index"
_MACRO_SERIES = "macro.synthetic.activity.index"


def _registry() -> EconomicSeriesRegistry:
    return EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id=_MARKET_SERIES,
                title="Synthetic Risk Asset",
                domain=EconomicDomain.MARKET,
                unit="index",
                scale=Decimal("1"),
                frequency="daily",
                observation_semantics="market observation timestamp",
                availability_semantics="public market availability timestamp",
                revision_policy=RevisionPolicy.NONE,
            ),
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id=_MACRO_SERIES,
                title="Synthetic Monthly Activity Index",
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="reference-month start",
                availability_semantics="public release timestamp",
                revision_policy=RevisionPolicy.REVISIONED,
            ),
        )
    )


def _observation(
    *,
    series_id: str,
    observation_time: datetime,
    available_time: datetime,
    retrieved_time: datetime,
    source_id: str,
    value: Decimal,
    frequency: str,
    raw_sha256: str,
    vintage_time: datetime | None = None,
    release_id: str | None = None,
) -> EconomicObservation:
    return EconomicObservation(
        schema_version="economic-observation-v1",
        series_id=series_id,
        observation_time=observation_time,
        available_time=available_time,
        vintage_time=vintage_time,
        retrieved_time=retrieved_time,
        source_id=source_id,
        value=value,
        unit="index",
        scale=Decimal("1"),
        frequency=frequency,
        release_id=release_id,
        raw_sha256=raw_sha256,
    )


def test_revisioned_bundle_build_replay_verify_and_asof_visibility(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    bundle_root = tmp_path / "bundle"
    store = LocalEconomicEvidenceStore(source_root)

    market_day_1 = store.put(
        source_id="fixture.market.v1",
        receipt_id="market-2026-02-10",
        payload=b'{"date":"2026-02-10","value":"200.0"}',
    )
    market_day_2 = store.put(
        source_id="fixture.market.v1",
        receipt_id="market-2026-02-11",
        payload=b'{"date":"2026-02-11","value":"202.0"}',
    )
    macro_initial = store.put(
        source_id="fixture.macro.v1",
        receipt_id="activity-2026-01-initial",
        payload=b'{"period":"2026-01","value":"100.0","vintage":"initial"}',
    )
    macro_revision = store.put(
        source_id="fixture.macro.v1",
        receipt_id="activity-2026-01-revision-1",
        payload=b'{"period":"2026-01","value":"101.0","vintage":"revision-1"}',
    )

    macro_reference_time = datetime(2026, 1, 1, tzinfo=UTC)
    initial_available = datetime(2026, 2, 5, 12, 0, tzinfo=UTC)
    revised_available = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)

    observations = (
        _observation(
            series_id=_MARKET_SERIES,
            observation_time=datetime(2026, 2, 10, 16, 0, tzinfo=UTC),
            available_time=datetime(2026, 2, 10, 16, 0, 1, tzinfo=UTC),
            retrieved_time=datetime(2026, 2, 10, 16, 1, tzinfo=UTC),
            source_id="fixture.market.v1",
            value=Decimal("200.0"),
            frequency="daily",
            raw_sha256=market_day_1.sha256,
        ),
        _observation(
            series_id=_MARKET_SERIES,
            observation_time=datetime(2026, 2, 11, 16, 0, tzinfo=UTC),
            available_time=datetime(2026, 2, 11, 16, 0, 1, tzinfo=UTC),
            retrieved_time=datetime(2026, 2, 11, 16, 1, tzinfo=UTC),
            source_id="fixture.market.v1",
            value=Decimal("202.0"),
            frequency="daily",
            raw_sha256=market_day_2.sha256,
        ),
        _observation(
            series_id=_MACRO_SERIES,
            observation_time=macro_reference_time,
            available_time=initial_available,
            vintage_time=initial_available,
            retrieved_time=datetime(2026, 2, 5, 12, 1, tzinfo=UTC),
            source_id="fixture.macro.v1",
            value=Decimal("100.0"),
            frequency="monthly",
            release_id="activity-2026-01-initial",
            raw_sha256=macro_initial.sha256,
        ),
        _observation(
            series_id=_MACRO_SERIES,
            observation_time=macro_reference_time,
            available_time=revised_available,
            vintage_time=revised_available,
            retrieved_time=datetime(2026, 3, 5, 12, 1, tzinfo=UTC),
            source_id="fixture.macro.v1",
            value=Decimal("101.0"),
            frequency="monthly",
            release_id="activity-2026-01-revision-1",
            raw_sha256=macro_revision.sha256,
        ),
    )
    inventory = RawEvidenceInventory((market_day_1, market_day_2, macro_initial, macro_revision))

    built = build_economic_dataset(
        registry=_registry(),
        observations=observations,
        raw_inventory=inventory,
    )
    written = write_economic_bundle(
        bundle_root,
        built,
        raw_source_root=source_root,
    )
    replayed = replay_economic_bundle(bundle_root)
    verified = verify_economic_bundle(bundle_root)

    assert written.dataset_id == built.manifest.dataset_id
    assert replayed.manifest.dataset_id == built.manifest.dataset_id
    assert verified.dataset_id == built.manifest.dataset_id
    assert replayed.canonical_observation_bytes == built.canonical_observation_bytes
    assert replayed.raw_inventory.inventory_root_sha256 == inventory.inventory_root_sha256

    pre_revision = latest_visible_vintages(
        replayed,
        datetime(2026, 2, 20, tzinfo=UTC),
        series_id=_MACRO_SERIES,
    )
    post_revision = latest_visible_vintages(
        replayed,
        datetime(2026, 3, 10, tzinfo=UTC),
        series_id=_MACRO_SERIES,
    )
    market_before_second_release = latest_visible_vintages(
        replayed,
        datetime(2026, 2, 11, 16, 0, tzinfo=UTC),
        series_id=_MARKET_SERIES,
    )
    market_after_second_release = latest_visible_vintages(
        replayed,
        datetime(2026, 2, 11, 16, 0, 1, tzinfo=UTC),
        series_id=_MARKET_SERIES,
    )

    assert tuple(row.value for row in pre_revision) == (Decimal("100.0"),)
    assert tuple(row.value for row in post_revision) == (Decimal("101.0"),)
    assert tuple(row.value for row in market_before_second_release) == (Decimal("200.0"),)
    assert tuple(row.value for row in market_after_second_release) == (
        Decimal("200.0"),
        Decimal("202.0"),
    )
