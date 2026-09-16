"""Independent integrity verification for Economic Data Fabric v2."""

from hashlib import sha256
from pathlib import Path

from gemini_trading.economics.data.dataset_v2 import (
    EconomicDatasetManifestV2,
    EconomicDatasetV2Error,
)
from gemini_trading.economics.data.replay_v2 import replay_economic_bundle_v2


class EconomicVerificationV2Error(EconomicDatasetV2Error):
    """Raised when a sealed economic v2 bundle fails integrity verification."""


def _digest(path: Path) -> str:
    if not path.is_file():
        raise EconomicVerificationV2Error(f"required economic v2 bundle file is missing: {path}")
    return sha256(path.read_bytes()).hexdigest()


def verify_economic_bundle_v2(root: Path) -> EconomicDatasetManifestV2:
    """Replay, then independently verify ledgers and immutable raw evidence."""

    dataset = replay_economic_bundle_v2(root)
    manifest = dataset.manifest
    paths = {
        "series registry": (root / "registry" / "series.jsonl", manifest.series_registry_sha256),
        "canonical observations": (
            root / "canonical" / "observations-v2.jsonl",
            manifest.canonical_observations_sha256,
        ),
        "publication events": (
            root / "events" / "publication-events.jsonl",
            manifest.publication_events_sha256,
        ),
        "availability evidence": (
            root / "availability" / "evidence.jsonl",
            manifest.availability_evidence_sha256,
        ),
        "raw inventory": (
            root / "inventory" / "raw-evidence.jsonl",
            manifest.raw_inventory_root_sha256,
        ),
    }
    for label, (path, expected) in paths.items():
        if _digest(path) != expected:
            raise EconomicVerificationV2Error(f"{label} digest does not match manifest")

    declared_paths = {receipt.relative_path for receipt in dataset.raw_inventory.receipts}
    raw_root = root / "raw"
    actual_paths = (
        {path.relative_to(root).as_posix() for path in raw_root.rglob("*") if path.is_file()}
        if raw_root.is_dir()
        else set()
    )
    undeclared = actual_paths - declared_paths
    if undeclared:
        raise EconomicVerificationV2Error(
            "undeclared raw evidence files: " + ", ".join(sorted(undeclared))
        )
    missing = declared_paths - actual_paths
    if missing:
        raise EconomicVerificationV2Error(
            "declared raw evidence files are missing: " + ", ".join(sorted(missing))
        )
    for receipt in dataset.raw_inventory.receipts:
        raw_path = root / receipt.relative_path
        payload = raw_path.read_bytes()
        if len(payload) != receipt.byte_length:
            raise EconomicVerificationV2Error(
                f"raw evidence byte length mismatch: {receipt.relative_path}"
            )
        if sha256(payload).hexdigest() != receipt.sha256:
            raise EconomicVerificationV2Error(
                f"raw evidence digest mismatch: {receipt.relative_path}"
            )
    return manifest


__all__ = ["EconomicVerificationV2Error", "verify_economic_bundle_v2"]
