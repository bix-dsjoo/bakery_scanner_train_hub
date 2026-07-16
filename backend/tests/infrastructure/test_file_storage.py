import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.config import Settings
from backend.app.infrastructure.file_storage import (
    FileTooLargeError,
    LocalFileStorage,
    TrashEntry,
)
from backend.app.infrastructure import file_storage


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


def test_stream_import_does_not_delete_preexisting_file_on_name_collision(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.settings.imports_dir.mkdir(parents=True)
    existing = storage.settings.imports_dir / "fixed.import"
    existing.write_bytes(b"keep me")
    monkeypatch.setattr(
        file_storage, "uuid4", lambda: SimpleNamespace(hex="fixed")
    )

    with pytest.raises(FileExistsError):
        storage.stream_import(io.BytesIO(b"new bytes"))

    assert existing.read_bytes() == b"keep me"


def test_stream_import_rejects_symlink_imports_root(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.settings.imports_dir.mkdir(parents=True)
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == storage.settings.imports_dir
        or original_is_symlink(path),
    )

    with pytest.raises(ValueError, match="symlink"):
        storage.stream_import(io.BytesIO(b"new bytes"))

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


def test_promote_rejects_source_outside_imports(storage: LocalFileStorage) -> None:
    source = storage.settings.data_dir / "outside.jpg"
    source.write_bytes(b"do not move")

    with pytest.raises(ValueError, match="imports"):
        storage.promote(
            source,
            collection="originals",
            brand_id="brand-123",
            sha256="a" * 64,
            extension="jpg",
        )

    assert source.read_bytes() == b"do not move"


def test_promote_rejects_symlink_source(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.settings.imports_dir.mkdir(parents=True)
    source = storage.settings.imports_dir / "linked.import"
    source.write_bytes(b"do not move")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == source or original_is_symlink(path),
    )

    with pytest.raises(ValueError, match="symlink"):
        storage.promote(
            source,
            collection="originals",
            brand_id="brand-123",
            sha256="a" * 64,
            extension="jpg",
        )

    assert source.read_bytes() == b"do not move"


@pytest.mark.parametrize("extension", [".jpg", "gif", "exe"])
def test_promote_rejects_noncanonical_extension(
    storage: LocalFileStorage, extension: str
) -> None:
    imported = storage.stream_import(io.BytesIO(b"original bytes"))

    with pytest.raises(ValueError, match="extension"):
        storage.promote(
            imported.path,
            collection="originals",
            brand_id="brand-123",
            sha256="a" * 64,
            extension=extension,
        )

    assert imported.path.read_bytes() == b"original bytes"


def test_resolve_rejects_symlink_in_storage_key(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.settings.originals_dir.mkdir(parents=True)
    link = storage.settings.originals_dir / "linked"
    link.mkdir()
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original_is_symlink(path),
    )

    with pytest.raises(ValueError, match="symlink"):
        storage.resolve("originals", Path("linked") / "image.jpg")


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


def test_move_to_trash_does_not_overwrite_collision(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    imported = storage.stream_import(io.BytesIO(b"original bytes"))
    storage_key = storage.promote(
        imported.path,
        collection="originals",
        brand_id="brand-123",
        sha256="a" * 64,
        extension="jpg",
    )
    storage.settings.trash_dir.mkdir(parents=True)
    collision = storage.settings.trash_dir / "fixed"
    collision.write_bytes(b"existing trash")
    monkeypatch.setattr(
        file_storage, "uuid4", lambda: SimpleNamespace(hex="fixed")
    )

    with pytest.raises(FileExistsError):
        storage.move_to_trash("originals", storage_key)

    assert collision.read_bytes() == b"existing trash"
    assert storage.resolve("originals", storage_key).read_bytes() == b"original bytes"


def test_restore_from_trash_does_not_overwrite_existing_target(
    storage: LocalFileStorage,
) -> None:
    imported = storage.stream_import(io.BytesIO(b"original bytes"))
    storage_key = storage.promote(
        imported.path,
        collection="originals",
        brand_id="brand-123",
        sha256="a" * 64,
        extension="jpg",
    )
    entry = storage.move_to_trash("originals", storage_key)
    target = storage.resolve("originals", storage_key)
    target.write_bytes(b"new original")

    with pytest.raises(FileExistsError):
        storage.restore_from_trash(entry)

    assert target.read_bytes() == b"new original"
    assert entry.path.read_bytes() == b"original bytes"


@pytest.mark.parametrize("operation", ["restore", "delete"])
def test_trash_operations_reject_entry_path_outside_trash(
    storage: LocalFileStorage, operation: str
) -> None:
    outside = storage.settings.data_dir / "outside.jpg"
    outside.write_bytes(b"keep me")
    entry = TrashEntry(
        path=outside,
        collection="originals",
        storage_key=Path("brand") / "aa" / "bb" / "image.jpg",
    )

    with pytest.raises(ValueError, match="trash"):
        if operation == "restore":
            storage.restore_from_trash(entry)
        else:
            storage.delete_trash(entry)

    assert outside.read_bytes() == b"keep me"


def test_restore_from_trash_rejects_destination_traversal(
    storage: LocalFileStorage,
) -> None:
    storage.settings.trash_dir.mkdir(parents=True)
    trash_file = storage.settings.trash_dir / "request-file"
    trash_file.write_bytes(b"trash bytes")
    entry = TrashEntry(
        path=trash_file,
        collection="originals",
        storage_key=Path("..") / "outside.jpg",
    )

    with pytest.raises(ValueError, match="escapes"):
        storage.restore_from_trash(entry)

    assert trash_file.read_bytes() == b"trash bytes"


def test_delete_trash_rejects_symlink_entry(
    storage: LocalFileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.settings.trash_dir.mkdir(parents=True)
    linked = storage.settings.trash_dir / "linked"
    linked.write_bytes(b"keep me")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == linked or original_is_symlink(path),
    )
    entry = TrashEntry(
        path=linked,
        collection="originals",
        storage_key=Path("brand") / "aa" / "bb" / "image.jpg",
    )

    with pytest.raises(ValueError, match="symlink"):
        storage.delete_trash(entry)

    assert linked.read_bytes() == b"keep me"
