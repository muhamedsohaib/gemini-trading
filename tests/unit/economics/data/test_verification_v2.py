from pathlib import Path

import pytest

from gemini_trading.economics.data.dataset_v2 import write_economic_bundle_v2
from gemini_trading.economics.data.verification_v2 import (
    EconomicVerificationV2Error,
    verify_economic_bundle_v2,
)
from tests.unit.economics.data import test_dataset_v2 as fixtures
from tests.unit.economics.data.test_replay_v2 import _materialize_raw


def _bundle(tmp_path: Path) -> Path:
    dataset = fixtures._build_revision()
    raw_source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    _materialize_raw(raw_source, dataset)
    write_economic_bundle_v2(bundle, dataset, raw_source_root=raw_source)
    return bundle


def test_independent_verifier_accepts_intact_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    manifest = verify_economic_bundle_v2(bundle)
    assert manifest.schema_version == "economic-dataset-v2"


@pytest.mark.parametrize(
    "relative_path",
    [
        "canonical/observations-v2.jsonl",
        "events/publication-events.jsonl",
        "availability/evidence.jsonl",
        "registry/series.jsonl",
        "inventory/raw-evidence.jsonl",
        "manifest.json",
    ],
)
def test_canonical_ledger_tamper_is_rejected(tmp_path: Path, relative_path: str) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / relative_path
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises((EconomicVerificationV2Error, ValueError)):
        verify_economic_bundle_v2(bundle)


def test_raw_tamper_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    raw = next((bundle / "raw").rglob("*.bin"))
    raw.write_bytes(raw.read_bytes() + b"tamper")
    with pytest.raises((EconomicVerificationV2Error, ValueError), match="raw evidence"):
        verify_economic_bundle_v2(bundle)


def test_undeclared_raw_file_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    rogue = bundle / "raw" / "fixture.v2" / "rogue.bin"
    rogue.write_bytes(b"rogue")
    with pytest.raises(EconomicVerificationV2Error, match="undeclared"):
        verify_economic_bundle_v2(bundle)


def test_missing_declared_raw_file_is_rejected(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    raw = next((bundle / "raw").rglob("*.bin"))
    raw.unlink()
    with pytest.raises((EconomicVerificationV2Error, ValueError), match=r"raw evidence|missing"):
        verify_economic_bundle_v2(bundle)
