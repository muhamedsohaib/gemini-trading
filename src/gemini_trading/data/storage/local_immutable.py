"""Immutable local storage for raw evidence and canonical datasets."""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_PROVIDER = "binance_spot"
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def write_immutable(path: Path, content: bytes) -> Path:
    """Publish bytes once without exposing a partial final destination."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise RawStorageConflictError(f"immutable path conflicts: {path}") from None
    finally:
        temp.unlink(missing_ok=True)
    return path


def _validate_identity(value: str) -> str:
    if (
        not value
        or ".." in value
        or "/" in value
        or "\\" in value
        or _IDENTITY_PATTERN.fullmatch(value) is None
    ):
        raise ValueError("invalid storage identity segment")
    return value


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json_bytes(payload: dict[str, object]) -> bytes:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def _instrument_payload(instrument: Instrument) -> dict[str, object]:
    return {
        "symbol": instrument.symbol,
        "base_asset": instrument.base_asset,
        "quote_asset": instrument.quote_asset,
    }


def _manifest_payload(manifest: RetrievalManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "provider": manifest.provider,
        "instrument": _instrument_payload(manifest.instrument),
        "timeframe": manifest.timeframe.value,
        "start_time": _format_datetime(manifest.start_time),
        "end_time": _format_datetime(manifest.end_time),
        "server_time_snapshot": (
            None
            if manifest.server_time_snapshot is None
            else _format_datetime(manifest.server_time_snapshot)
        ),
        "page_hashes": list(manifest.page_hashes),
        "retry_count": manifest.retry_count,
        "status": manifest.status.value,
        "failure_type": manifest.failure_type,
        "failure_message": manifest.failure_message,
    }


def _page_metadata_payload(page: RawPage) -> dict[str, object]:
    return {
        "run_id": page.run_id,
        "sequence": page.sequence,
        "request_parameters": [list(item) for item in page.request_parameters],
        "retrieved_at": _format_datetime(page.retrieved_at),
        "server_time_snapshot": _format_datetime(page.server_time_snapshot),
        "http_status": page.http_status,
    }


def _object_mapping(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {description} JSON") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"invalid {description} JSON object")
    raw_mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise ValueError(f"invalid {description} JSON object")
    return cast(dict[str, object], raw_mapping)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"invalid storage metadata field: {key}")
    return value


def _optional_str(mapping: dict[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid storage metadata field: {key}")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"invalid storage metadata field: {key}")
    return value


def _required_mapping(mapping: dict[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"invalid storage metadata field: {key}")
    raw_mapping = cast(dict[object, object], value)
    if not all(isinstance(item, str) for item in raw_mapping):
        raise ValueError(f"invalid storage metadata field: {key}")
    return cast(dict[str, object], raw_mapping)


def _required_strings(mapping: dict[str, object], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ValueError(f"invalid storage metadata field: {key}")
    raw_values = cast(list[object], value)
    if not all(isinstance(item, str) for item in raw_values):
        raise ValueError(f"invalid storage metadata field: {key}")
    return tuple(cast(list[str], raw_values))


def _request_parameters(mapping: dict[str, object]) -> tuple[tuple[str, str], ...]:
    raw_parameters = mapping.get("request_parameters")
    if not isinstance(raw_parameters, list):
        raise ValueError("invalid storage metadata field: request_parameters")
    raw_parameter_values = cast(list[object], raw_parameters)
    parameters: list[tuple[str, str]] = []
    for raw_parameter in raw_parameter_values:
        if not isinstance(raw_parameter, list):
            raise ValueError("invalid storage metadata field: request_parameters")
        pair = cast(list[object], raw_parameter)
        if len(pair) != 2:
            raise ValueError("invalid storage metadata field: request_parameters")
        key, value = pair
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("invalid storage metadata field: request_parameters")
        parameters.append((key, value))
    return tuple(parameters)


def _deserialize_manifest(raw: bytes) -> RetrievalManifest:
    mapping = _object_mapping(raw, "retrieval manifest")
    instrument_mapping = _required_mapping(mapping, "instrument")
    server_time_value = mapping.get("server_time_snapshot")
    if server_time_value is not None and not isinstance(server_time_value, str):
        raise ValueError("invalid storage metadata field: server_time_snapshot")
    return RetrievalManifest(
        schema_version=_required_str(mapping, "schema_version"),
        run_id=_required_str(mapping, "run_id"),
        provider=_required_str(mapping, "provider"),
        instrument=Instrument(
            _required_str(instrument_mapping, "symbol"),
            _required_str(instrument_mapping, "base_asset"),
            _required_str(instrument_mapping, "quote_asset"),
        ),
        timeframe=Timeframe(_required_str(mapping, "timeframe")),
        start_time=_parse_datetime(_required_str(mapping, "start_time")),
        end_time=_parse_datetime(_required_str(mapping, "end_time")),
        server_time_snapshot=(
            None if server_time_value is None else _parse_datetime(server_time_value)
        ),
        page_hashes=_required_strings(mapping, "page_hashes"),
        retry_count=_required_int(mapping, "retry_count"),
        status=RetrievalStatus(_required_str(mapping, "status")),
        failure_type=_optional_str(mapping, "failure_type"),
        failure_message=_optional_str(mapping, "failure_message"),
    )


@dataclass(frozen=True, slots=True)
class LocalImmutableStore:
    """Filesystem implementation rooted beneath one explicit project directory."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    def _raw_run_directory(self, run_id: str) -> Path:
        return self.root / "data" / "raw" / _PROVIDER / _validate_identity(run_id)

    def _dataset_directory(self, dataset_id: str) -> Path:
        return self.root / "data" / "canonical" / _validate_identity(dataset_id)

    @staticmethod
    def _page_name(sequence: int) -> str:
        if sequence > 999_999:
            raise ValueError("page sequence must fit six digits")
        return f"page-{sequence:06d}"

    def write_page(self, page: RawPage) -> Path:
        run_directory = self._raw_run_directory(page.run_id)
        page_name = self._page_name(page.sequence)
        response_path = run_directory / f"{page_name}.json"
        metadata_path = run_directory / f"{page_name}.metadata.json"
        write_immutable(response_path, page.response_bytes)
        write_immutable(metadata_path, _json_bytes(_page_metadata_payload(page)))
        return response_path

    def write_retrieval_manifest(self, manifest: RetrievalManifest) -> Path:
        if manifest.provider != _PROVIDER:
            raise ValueError("unsupported local raw provider")
        path = self._raw_run_directory(manifest.run_id) / "retrieval-manifest.json"
        return write_immutable(path, _json_bytes(_manifest_payload(manifest)))

    def read_run(self, run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]:
        run_directory = self._raw_run_directory(run_id)
        manifest_path = run_directory / "retrieval-manifest.json"
        manifest = _deserialize_manifest(manifest_path.read_bytes())
        if manifest.run_id != run_id:
            raise ValueError("retrieval manifest run identity mismatch")
        pages: list[RawPage] = []
        for sequence, response_sha256 in enumerate(manifest.page_hashes, start=1):
            page_name = self._page_name(sequence)
            response_path = run_directory / f"{page_name}.json"
            metadata_path = run_directory / f"{page_name}.metadata.json"
            response_bytes = response_path.read_bytes()
            metadata = _object_mapping(metadata_path.read_bytes(), "raw page metadata")
            metadata_run_id = _required_str(metadata, "run_id")
            metadata_sequence = _required_int(metadata, "sequence")
            if metadata_run_id != run_id or metadata_sequence != sequence:
                raise ValueError("raw page metadata identity mismatch")
            pages.append(
                RawPage(
                    run_id=metadata_run_id,
                    sequence=metadata_sequence,
                    request_parameters=_request_parameters(metadata),
                    retrieved_at=_parse_datetime(_required_str(metadata, "retrieved_at")),
                    server_time_snapshot=_parse_datetime(
                        _required_str(metadata, "server_time_snapshot")
                    ),
                    http_status=_required_int(metadata, "http_status"),
                    response_bytes=response_bytes,
                    response_sha256=response_sha256,
                )
            )
        return manifest, tuple(pages)

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]:
        dataset_directory = self._dataset_directory(dataset_id)
        candle_path = write_immutable(dataset_directory / "candles.jsonl", jsonl_bytes)
        manifest_path = write_immutable(
            dataset_directory / "dataset-manifest.json",
            manifest_bytes,
        )
        return candle_path, manifest_path

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path:
        path = (
            self._dataset_directory(dataset_id)
            / "provenance"
            / f"{_validate_identity(run_id)}.json"
        )
        return write_immutable(path, receipt_bytes)

    def read_dataset(self, dataset_id: str) -> tuple[bytes, bytes]:
        dataset_directory = self._dataset_directory(dataset_id)
        return (
            (dataset_directory / "candles.jsonl").read_bytes(),
            (dataset_directory / "dataset-manifest.json").read_bytes(),
        )

    def read_provenance(self, dataset_id: str, run_id: str) -> bytes:
        path = (
            self._dataset_directory(dataset_id)
            / "provenance"
            / f"{_validate_identity(run_id)}.json"
        )
        return path.read_bytes()
