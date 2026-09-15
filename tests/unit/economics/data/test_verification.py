"""Independent integrity verification for Economic Data Fabric v1."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.economics.data.dataset import (
    EconomicDatasetError,
    build_economic_dataset,
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
    LocalEconomicEvidenceStore,
    RawEvidenceInventory,
)
from gemini_trading.economics.data.verification import (
    EconomicVerificationError,
    verify_economic_bundle,
)


def _bundle(root: Path) -> tuple[Path, str]:
    source = root / "source"
    bundle = root / "bundle"
    store = LocalEconomicEvidenceStore(source)
    receipt = store.put(
        source_id="fixture.market.v1",
        receipt_id="asset",
        payload=b"asset-bytes",
    )
    registry = EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="market.synthetic.asset.index",
                title="Synthetic Asset",
                domain=EconomicDomain.MARKET,
                unit="index",
                scale=Decimal("1"),
                frequency="daily",
                observation_semantics="market observation timestamp",
                availability_semantics="public market availability timestamp",
                revision_policy=RevisionPolicy.NONE,
            ),
        )
    )
    observation = EconomicObservation(
        schema_version="economic-observation-v1",
        series_id="market.synthetic.asset.index",
        observation_time=datetime(2026, 8, 1, tzinfo=UTC),
        available_time=datetime(2026, 8, 1, 0, 1, tzinfo=UTC),
        vintage_time=None,
        retrieved_time=datetime(2026, 8, 1, 0, 2, tzinfo=UTC),
        source_id="fixture.market.v1",
        value=Decimal("100.0"),
        unit="index",
        scale=Decimal("1"),
        frequency="daily",
        release_id=None,
        raw_sha256=receipt.sha256,
    )
    dataset = build_economic_dataset(
        registry=registry,
        observations=(observation,),
        raw_inventory=RawEvidenceInventory((receipt,)),
    )
    write_economic_bundle(bundle, dataset, raw_source_root=source)
    return bundle, dataset.manifest.dataset_id


def test_verification_returns_exact_verified_manifest(tmp_path: Path) -> None:
    bundle, dataset_id = _bundle(tmp_path)

    manifest = verify_economic_bundle(bundle)

    assert manifest.dataset_id == dataset_id


def test_verification_independently_rejects_extra_raw_file(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    extra = bundle / "raw" / "fixture.market.v1" / "undeclared.bin"
    extra.write_bytes(b"undeclared")

    with pytest.raises(EconomicVerificationError, match="undeclared raw evidence"):
        verify_economic_bundle(bundle)


def test_verification_independently_rejects_component_hash_mismatch(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    registry = bundle / "registry" / "series.jsonl"
    registry.write_bytes(registry.read_bytes() + b"\n")

    with pytest.raises((EconomicDatasetError, EconomicVerificationError)):
        verify_economic_bundle(bundle)
