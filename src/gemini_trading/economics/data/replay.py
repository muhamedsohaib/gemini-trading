"""Provider-free deterministic replay for Economic Data Fabric v1."""

from pathlib import Path

from gemini_trading.economics.data.dataset import EconomicDataset, load_economic_bundle


def replay_economic_bundle(root: Path) -> EconomicDataset:
    """Reconstruct and validate one economic dataset using only sealed bundle bytes."""

    return load_economic_bundle(root)


__all__ = ["replay_economic_bundle"]
