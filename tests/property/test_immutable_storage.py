import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable

_SAFE_SEGMENTS = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", fullmatch=True).filter(
    lambda value: ".." not in value
)


@given(content=st.binary(max_size=2048))
def test_immutable_write_round_trips_arbitrary_bytes(content: bytes) -> None:
    with TemporaryDirectory() as directory:
        destination = Path(directory) / "artifact.bin"

        write_immutable(destination, content)
        write_immutable(destination, content)

        assert destination.read_bytes() == content


@given(first=st.binary(max_size=1024), second=st.binary(max_size=1024))
def test_conflicting_arbitrary_bytes_never_replace_existing_content(
    first: bytes,
    second: bytes,
) -> None:
    assume(first != second)
    with TemporaryDirectory() as directory:
        destination = Path(directory) / "artifact.bin"
        write_immutable(destination, first)

        with pytest.raises(RawStorageConflictError):
            write_immutable(destination, second)

        assert destination.read_bytes() == first


@given(segment=_SAFE_SEGMENTS, content=st.binary(max_size=1024))
def test_safe_dataset_identity_always_stays_under_canonical_root(
    segment: str,
    content: bytes,
) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        store = LocalImmutableStore(root)

        candle_path, manifest_path = store.write_dataset(segment, content, b"{}\n")

        canonical_root = (root / "data" / "canonical").resolve()
        assert candle_path.resolve().is_relative_to(canonical_root)
        assert manifest_path.resolve().is_relative_to(canonical_root)
        assert hashlib.sha256(candle_path.read_bytes()).digest() == hashlib.sha256(content).digest()
