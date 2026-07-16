import hashlib
import io
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.infrastructure.file_storage import (
    FileTooLargeError,
    LocalFileStorage,
)


class TrackingStream(io.BytesIO):
    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class FailingStream(io.BytesIO):
    def read(self, size: int = -1) -> bytes:
        if self.tell() > 0:
            raise OSError("stream stopped")
        return super().read(size)


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(Settings(data_dir=tmp_path))


def test_stream_import_preserves_bytes_and_calculates_sha256(
    storage: LocalFileStorage,
) -> None:
    content = (b"bakery-image" * 20_000) + b"tail"
    stream = TrackingStream(content)

    imported = storage.stream_import(stream)

    assert imported.path.read_bytes() == content
    assert imported.byte_size == len(content)
    assert imported.sha256 == hashlib.sha256(content).hexdigest()
    assert stream.read_sizes and set(stream.read_sizes) == {64 * 1024}
    assert imported.path.parent == storage.settings.imports_dir


def test_stream_import_stops_at_limit_and_removes_partial_file(
    storage: LocalFileStorage,
) -> None:
    stream = TrackingStream(b"a" * (64 * 1024 + 1))

    with pytest.raises(FileTooLargeError):
        storage.stream_import(stream, max_bytes=64 * 1024)

    assert stream.tell() == 64 * 1024 + 1
    assert list(storage.settings.imports_dir.iterdir()) == []


def test_stream_import_removes_partial_file_when_stream_fails(
    storage: LocalFileStorage,
) -> None:
    with pytest.raises(OSError, match="stream stopped"):
        storage.stream_import(FailingStream(b"a" * (64 * 1024 + 1)))

    assert list(storage.settings.imports_dir.iterdir()) == []


def test_promote_uses_server_key_and_hash_prefix(storage: LocalFileStorage) -> None:
    imported = storage.stream_import(io.BytesIO(b"original bytes"))

    storage_key = storage.promote(
        imported.path,
        collection="originals",
        brand_id="brand-123",
        sha256="abcdef" + "0" * 58,
        extension="jpg",
    )

    assert storage_key.parts[:3] == ("brand-123", "ab", "cd")
    assert storage_key.suffix == ".jpg"
    assert storage.resolve("originals", storage_key).read_bytes() == b"original bytes"
    assert "customer-upload" not in storage_key.as_posix()


def test_trash_move_restore_and_delete_are_reversible(
    storage: LocalFileStorage,
) -> None:
    imported = storage.stream_import(io.BytesIO(b"original bytes"))
    storage_key = storage.promote(
        imported.path,
        collection="originals",
        brand_id="brand-123",
        sha256="abcdef" + "0" * 58,
        extension="jpg",
    )

    trash_entry = storage.move_to_trash("originals", storage_key)
    assert not storage.resolve("originals", storage_key).exists()
    assert trash_entry.path.read_bytes() == b"original bytes"

    storage.restore_from_trash(trash_entry)
    assert storage.resolve("originals", storage_key).read_bytes() == b"original bytes"

    trash_entry = storage.move_to_trash("originals", storage_key)
    storage.delete_trash(trash_entry)
    assert not trash_entry.path.exists()
