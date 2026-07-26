"""Storage protocols for immutable market-data evidence and datasets."""

from pathlib import Path
from typing import Protocol

from gemini_trading.domain.dataset import RawPage, RetrievalManifest


class RawStore(Protocol):
    """Immutable persistence contract for provider evidence."""

    def write_page(self, page: RawPage) -> Path: ...

    def write_retrieval_manifest(self, manifest: RetrievalManifest) -> Path: ...

    def write_run_closure_manifest(self, run_id: str, raw: bytes) -> Path: ...

    def read_run_closure_manifest_bytes(self, run_id: str) -> bytes: ...

    def read_run(self, run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]: ...


class CanonicalStore(Protocol):
    """Immutable persistence contract for canonical datasets and provenance."""

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]: ...

    def write_dataset_supporting_manifests(
        self,
        dataset_id: str,
        closure_raw: bytes,
        segment_raw: bytes,
    ) -> tuple[Path, Path]: ...

    def read_dataset_supporting_manifests(self, dataset_id: str) -> tuple[bytes, bytes]: ...

    def write_dataset_exclusion_manifest(self, dataset_id: str, exclusion_raw: bytes) -> Path: ...

    def read_dataset_exclusion_manifest_bytes(self, dataset_id: str) -> bytes: ...

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path: ...
