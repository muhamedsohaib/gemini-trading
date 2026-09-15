"""Content-addressed dataset identity for Economic Data Fabric v1."""

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from gemini_trading.economics.data.dataset import (
    ECONOMIC_DATASET_SCHEMA_V1,
    EconomicDataset,
    EconomicDatasetError,
    build_economic_dataset,
    load_economic_bundle,
    write_economic_bundle,
)
from gemini_trading.economics.data.observation import EconomicObservation
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)
from gemini_trading.economics.data.storage import (
    RawEvidenceInventory,
    RawEvidenceReceipt,
)


def _receipt(*, source_id: str, receipt_id: str, payload: bytes) -> RawEvidenceReceipt:
    return RawEvidenceReceipt(
        schema_version="economic-raw-receipt-v1",
        source_id=source_id,
        receipt_id=receipt_id,
        relative_path=f"raw/{source_id}/{receipt_id}.bin",
        byte_length=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def _registry(*, macro_title: str = "US CPI All Items") -> EconomicSeriesRegistry:
    return EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="market.usd.dxy.index",
                title="US Dollar Index",
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
                series_id="macro.us.cpi.all_items.index",
                title=macro_title,
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


def _observations(
    *,
    macro_value: Decimal = Decimal("324.100"),
    macro_available_time: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    macro_vintage_time: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
) -> tuple[EconomicObservation, ...]:
    market_payload = b"market-release"
    macro_payload = b"macro-release"
    return (
        EconomicObservation(
            schema_version="economic-observation-v1",
            series_id="market.usd.dxy.index",
            observation_time=datetime(2026, 8, 12, 12, 29, tzinfo=UTC),
            available_time=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
            vintage_time=None,
            retrieved_time=datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
            source_id="fixture.market.v1",
            value=Decimal("99.1250"),
            unit="index",
            scale=Decimal("1"),
            frequency="daily",
            release_id=None,
            raw_sha256=sha256(market_payload).hexdigest(),
        ),
        EconomicObservation(
            schema_version="economic-observation-v1",
            series_id="macro.us.cpi.all_items.index",
            observation_time=datetime(2026, 7, 1, tzinfo=UTC),
            available_time=macro_available_time,
            vintage_time=macro_vintage_time,
            retrieved_time=datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
            source_id="fixture.macro.v1",
            value=macro_value,
            unit="index",
            scale=Decimal("1"),
            frequency="monthly",
            release_id="cpi-2026-08",
            raw_sha256=sha256(macro_payload).hexdigest(),
        ),
    )


def _inventory() -> RawEvidenceInventory:
    return RawEvidenceInventory(
        (
            _receipt(
                source_id="fixture.market.v1",
                receipt_id="market-release",
                payload=b"market-release",
            ),
            _receipt(
                source_id="fixture.macro.v1",
                receipt_id="macro-release",
                payload=b"macro-release",
            ),
        )
    )


def _dataset(
    *,
    registry: EconomicSeriesRegistry | None = None,
    observations: tuple[EconomicObservation, ...] | None = None,
    inventory: RawEvidenceInventory | None = None,
) -> EconomicDataset:
    return build_economic_dataset(
        registry=_registry() if registry is None else registry,
        observations=_observations() if observations is None else observations,
        raw_inventory=_inventory() if inventory is None else inventory,
    )


def test_dataset_schema_is_frozen() -> None:
    assert ECONOMIC_DATASET_SCHEMA_V1 == "economic-dataset-v1"


def test_semantically_identical_input_order_has_same_dataset_id() -> None:
    observations = _observations()
    first = _dataset(observations=observations)
    second = _dataset(observations=tuple(reversed(observations)))

    assert first.manifest == second.manifest
    assert first.manifest.dataset_id == second.manifest.dataset_id
    assert first.canonical_observation_bytes == second.canonical_observation_bytes


def test_changing_observation_value_changes_dataset_id() -> None:
    first = _dataset()
    second = _dataset(observations=_observations(macro_value=Decimal("324.200")))

    assert first.manifest.dataset_id != second.manifest.dataset_id


def test_changing_available_time_alone_changes_dataset_id() -> None:
    first = _dataset()
    second = _dataset(
        observations=_observations(macro_available_time=datetime(2026, 8, 12, 12, 31, tzinfo=UTC))
    )

    assert first.observations[0].vintage_time == second.observations[0].vintage_time
    assert first.manifest.dataset_id != second.manifest.dataset_id


def test_changing_registry_semantics_changes_dataset_id() -> None:
    first = _dataset()
    second = _dataset(registry=_registry(macro_title="US CPI All Urban Consumers"))

    assert first.manifest.dataset_id != second.manifest.dataset_id


def test_changing_raw_inventory_identity_changes_dataset_id() -> None:
    macro = _receipt(
        source_id="fixture.macro.v1",
        receipt_id="macro-release-alias",
        payload=b"macro-release",
    )
    market = _receipt(
        source_id="fixture.market.v1",
        receipt_id="market-release",
        payload=b"market-release",
    )

    first = _dataset()
    second = _dataset(inventory=RawEvidenceInventory((macro, market)))

    assert first.raw_inventory.raw_digests == second.raw_inventory.raw_digests
    assert first.manifest.dataset_id != second.manifest.dataset_id


def test_dataset_rejects_observation_without_raw_evidence() -> None:
    market_only = RawEvidenceInventory((_inventory().receipts[1],))

    with pytest.raises(EconomicDatasetError, match="raw evidence"):
        _dataset(inventory=market_only)


def test_dataset_rejects_observation_series_missing_from_registry() -> None:
    macro_only_registry = EconomicSeriesRegistry((_registry().definitions[0],))

    with pytest.raises(EconomicDatasetError, match="series registry"):
        _dataset(registry=macro_only_registry)


def test_manifest_binds_counts_ranges_and_component_hashes() -> None:
    dataset = _dataset()
    manifest = dataset.manifest

    assert manifest.schema_version == "economic-dataset-v1"
    assert manifest.observation_count == 2
    assert manifest.series_count == 2
    assert manifest.minimum_observation_time == datetime(2026, 7, 1, tzinfo=UTC)
    assert manifest.maximum_observation_time == datetime(2026, 8, 12, 12, 29, tzinfo=UTC)
    assert manifest.minimum_available_time == datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    assert manifest.maximum_available_time == datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    assert (
        manifest.canonical_observations_sha256
        == sha256(dataset.canonical_observation_bytes).hexdigest()
    )
    assert manifest.series_registry_sha256 == sha256(dataset.series_registry_bytes).hexdigest()
    assert manifest.raw_inventory_root_sha256 == dataset.raw_inventory.inventory_root_sha256
    assert len(manifest.dataset_id) == 64


def _write_raw_source(dataset: EconomicDataset, raw_source: Path) -> None:
    payloads = {
        "macro-release": b"macro-release",
        "market-release": b"market-release",
    }
    for receipt in dataset.raw_inventory.receipts:
        target = raw_source / receipt.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[receipt.receipt_id])


def test_write_and_load_bundle_round_trip_exact_identity(tmp_path: Path) -> None:
    dataset = _dataset()
    raw_source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    _write_raw_source(dataset, raw_source)

    written = write_economic_bundle(bundle, dataset, raw_source_root=raw_source)
    loaded = load_economic_bundle(bundle)

    assert written == dataset.manifest
    assert loaded.manifest == dataset.manifest
    assert loaded.manifest.dataset_id == dataset.manifest.dataset_id
    assert (bundle / "registry" / "series.jsonl").read_bytes() == dataset.series_registry_bytes
    assert (bundle / "canonical" / "observations.jsonl").read_bytes() == (
        dataset.canonical_observation_bytes
    )
    assert (bundle / "inventory" / "raw-evidence.jsonl").read_bytes() == (
        dataset.raw_inventory.canonical_bytes
    )
    assert (bundle / "manifest.json").is_file()


def test_write_bundle_refuses_conflicting_existing_canonical_bytes(tmp_path: Path) -> None:
    dataset = _dataset()
    raw_source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    _write_raw_source(dataset, raw_source)

    conflicting = bundle / "canonical" / "observations.jsonl"
    conflicting.parent.mkdir(parents=True, exist_ok=True)
    conflicting.write_bytes(b"conflict\n")

    with pytest.raises(EconomicDatasetError, match="conflicting existing bytes"):
        write_economic_bundle(bundle, dataset, raw_source_root=raw_source)

    assert not (bundle / "manifest.json").exists()
