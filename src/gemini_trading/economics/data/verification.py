"""Independent integrity verification for Economic Data Fabric v1."""

from hashlib import sha256
from pathlib import Path

from gemini_trading.economics.data.dataset import (
    EconomicDatasetError,
    EconomicDatasetManifest,
)
from gemini_trading.economics.data.replay import replay_economic_bundle


class EconomicVerificationError(EconomicDatasetError):
    """Raised when an economic bundle fails independent integrity verification."""


def _digest(path: Path) -> str:
    if not path.is_file():
        raise EconomicVerificationError(f"required economic bundle file is missing: {path}")
    return sha256(path.read_bytes()).hexdigest()


def verify_economic_bundle(root: Path) -> EconomicDatasetManifest:
    """Replay then independently verify component hashes and raw-file inventory."""

    dataset = replay_economic_bundle(root)
    manifest = dataset.manifest

    registry_path = root / "registry" / "series.jsonl"
    observations_path = root / "canonical" / "observations.jsonl"
    inventory_path = root / "inventory" / "raw-evidence.jsonl"

    if _digest(registry_path) != manifest.series_registry_sha256:
        raise EconomicVerificationError("series registry digest does not match manifest")
    if _digest(observations_path) != manifest.canonical_observations_sha256:
        raise EconomicVerificationError("canonical observations digest does not match manifest")
    if _digest(inventory_path) != manifest.raw_inventory_root_sha256:
        raise EconomicVerificationError("raw inventory root does not match manifest")

    declared_paths = {receipt.relative_path for receipt in dataset.raw_inventory.receipts}
    raw_root = root / "raw"
    actual_paths: set[str] = set()
    if raw_root.is_dir():
        actual_paths = {
            path.relative_to(root).as_posix() for path in raw_root.rglob("*") if path.is_file()
        }
    undeclared = actual_paths - declared_paths
    if undeclared:
        raise EconomicVerificationError(
            "undeclared raw evidence files: " + ", ".join(sorted(undeclared))
        )
    missing = declared_paths - actual_paths
    if missing:
        raise EconomicVerificationError(
            "declared raw evidence files are missing: " + ", ".join(sorted(missing))
        )

    for receipt in dataset.raw_inventory.receipts:
        raw_path = root / receipt.relative_path
        payload = raw_path.read_bytes()
        if len(payload) != receipt.byte_length:
            raise EconomicVerificationError(
                f"raw evidence byte length mismatch: {receipt.relative_path}"
            )
        if sha256(payload).hexdigest() != receipt.sha256:
            raise EconomicVerificationError(
                f"raw evidence digest mismatch: {receipt.relative_path}"
            )

    return manifest


__all__ = ["EconomicVerificationError", "verify_economic_bundle"]
