"""Provider-free exact replay for Economic Data Fabric v1."""

import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.economics.data.dataset import (
    EconomicDataset,
    EconomicDatasetError,
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


def _write_bundle(root: Path) -> EconomicDataset:
    source = root / "source"
    bundle = root / "bundle"
    store = LocalEconomicEvidenceStore(source)
    receipt = store.put(
        source_id="fixture.market.v1",
        receipt_id="dxy-2026-08-12",
        payload=b'{"dxy":"99.1250"}',
    )
    registry = EconomicSeriesRegistry(
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
        )
    )
    observation = EconomicObservation(
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
        raw_sha256=receipt.sha256,
    )
    dataset = build_economic_dataset(
        registry=registry,
        observations=(observation,),
        raw_inventory=RawEvidenceInventory((receipt,)),
    )
    write_economic_bundle(bundle, dataset, raw_source_root=source)
    return dataset


def _bundle(root: Path) -> Path:
    return root / "bundle"


def _rewrite_json_line(path: Path, field: str, value: object) -> None:
    row = json.loads(path.read_text(encoding="utf-8"))
    row[field] = value
    encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"{encoded}\n", encoding="utf-8")


def test_replay_reconstructs_exact_dataset_without_provider_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _write_bundle(tmp_path)
    monkeypatch.setitem(sys.modules, "gemini_trading.data.providers", None)

    replayed = replay_economic_bundle(_bundle(tmp_path))

    assert replayed.manifest == original.manifest
    assert replayed.manifest.dataset_id == original.manifest.dataset_id
    assert replayed.canonical_observation_bytes == original.canonical_observation_bytes


def test_replay_rejects_tampered_raw_byte(tmp_path: Path) -> None:
    dataset = _write_bundle(tmp_path)
    raw = _bundle(tmp_path) / dataset.raw_inventory.receipts[0].relative_path
    raw.write_bytes(b"tampered")

    with pytest.raises(EconomicDatasetError, match="raw evidence digest mismatch"):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_tampered_canonical_value(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    canonical = _bundle(tmp_path) / "canonical" / "observations.jsonl"
    _rewrite_json_line(canonical, "value", "100.0000")

    with pytest.raises(EconomicDatasetError):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_tampered_available_time(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    canonical = _bundle(tmp_path) / "canonical" / "observations.jsonl"
    _rewrite_json_line(canonical, "available_time", "2026-08-12T12:30:01.000Z")

    with pytest.raises(EconomicDatasetError):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_tampered_registry_semantics(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    registry = _bundle(tmp_path) / "registry" / "series.jsonl"
    _rewrite_json_line(registry, "title", "Tampered Dollar Index")

    with pytest.raises(EconomicDatasetError):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_tampered_raw_inventory_sha(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    inventory = _bundle(tmp_path) / "inventory" / "raw-evidence.jsonl"
    _rewrite_json_line(inventory, "sha256", "0" * 64)

    with pytest.raises(EconomicDatasetError):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_tampered_manifest_dataset_id(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    manifest = _bundle(tmp_path) / "manifest.json"
    _rewrite_json_line(manifest, "dataset_id", "0" * 64)

    with pytest.raises(EconomicDatasetError, match="manifest"):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_missing_raw_file(tmp_path: Path) -> None:
    dataset = _write_bundle(tmp_path)
    raw = _bundle(tmp_path) / dataset.raw_inventory.receipts[0].relative_path
    raw.unlink()

    with pytest.raises(EconomicDatasetError, match="raw evidence is missing"):
        replay_economic_bundle(_bundle(tmp_path))


def test_replay_rejects_unknown_observation_raw_digest(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    canonical = _bundle(tmp_path) / "canonical" / "observations.jsonl"
    _rewrite_json_line(canonical, "raw_sha256", "f" * 64)

    with pytest.raises(EconomicDatasetError, match="raw evidence"):
        replay_economic_bundle(_bundle(tmp_path))
