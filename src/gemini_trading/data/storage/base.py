"""Storage protocols for immutable market-data evidence and datasets."""

from pathlib import Path
from typing import Protocol

from gemini_trading.domain.dataset import RawPage, RetrievalManifest


class RawStore(Protocol):
    """Immutable persistence contract for provider evidence."""

    def write_page(self, page: RawPage) -> Path: ...

    def write_retrieval_manifest(self, manifest: RetrievalManifest) -> Path: ...

    def read_run(self, run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]: ...

    def read_retrieval_manifest_bytes(self, run_id: str) -> bytes: ...


class CanonicalStore(Protocol):
    """Immutable persistence contract for canonical datasets and provenance."""

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]: ...

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path: ...

    def read_dataset(self, dataset_id: str) -> tuple[bytes, bytes]: ...

    def read_provenance(self, dataset_id: str, run_id: str) -> bytes: ...
