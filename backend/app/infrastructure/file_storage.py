from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

from backend.app.config import Settings


CHUNK_SIZE = 64 * 1024
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
StorageCollection = Literal["originals", "thumbnails"]


class FileTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedFile:
    path: Path
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class TrashEntry:
    path: Path
    collection: StorageCollection
    storage_key: Path


class LocalFileStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def stream_import(
        self,
        stream: BinaryIO,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> ImportedFile:
        if max_bytes < 0:
            raise ValueError("max_bytes must not be negative")

        self.settings.imports_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.imports_dir / f"{uuid4().hex}.import"
        digest = hashlib.sha256()
        byte_size = 0

        try:
            with path.open("xb") as destination:
                while chunk := stream.read(CHUNK_SIZE):
                    byte_size += len(chunk)
                    if byte_size > max_bytes:
                        raise FileTooLargeError(
                            f"file exceeds the {max_bytes}-byte limit"
                        )
                    destination.write(chunk)
                    digest.update(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise

        return ImportedFile(path=path, byte_size=byte_size, sha256=digest.hexdigest())

    def promote(
        self,
        source: Path,
        *,
        collection: StorageCollection,
        brand_id: str,
        sha256: str,
        extension: str,
    ) -> Path:
        self._validate_component(brand_id, "brand_id")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise ValueError("sha256 must be a lowercase hexadecimal digest")
        extension = extension.removeprefix(".").lower()
        self._validate_component(extension, "extension")

        storage_key = Path(brand_id) / sha256[:2] / sha256[2:4] / (
            f"{uuid4().hex}.{extension}"
        )
        destination = self.resolve(collection, storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        return storage_key

    def resolve(self, collection: StorageCollection, storage_key: Path | str) -> Path:
        base = self._collection_dir(collection).resolve()
        path = (base / Path(storage_key)).resolve()
        if not path.is_relative_to(base):
            raise ValueError("storage key escapes its collection")
        return path

    def move_to_trash(
        self, collection: StorageCollection, storage_key: Path | str
    ) -> TrashEntry:
        source = self.resolve(collection, storage_key)
        self.settings.trash_dir.mkdir(parents=True, exist_ok=True)
        destination = self.settings.trash_dir / uuid4().hex
        os.replace(source, destination)
        return TrashEntry(
            path=destination,
            collection=collection,
            storage_key=Path(storage_key),
        )

    def restore_from_trash(self, entry: TrashEntry) -> None:
        destination = self.resolve(entry.collection, entry.storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(entry.path, destination)

    def delete_trash(self, entry: TrashEntry) -> None:
        entry.path.unlink(missing_ok=True)

    def _collection_dir(self, collection: StorageCollection) -> Path:
        if collection == "originals":
            return self.settings.originals_dir
        if collection == "thumbnails":
            return self.settings.thumbnails_dir
        raise ValueError(f"unsupported storage collection: {collection}")

    @staticmethod
    def _validate_component(value: str, name: str) -> None:
        if not value or value in {".", ".."} or Path(value).name != value:
            raise ValueError(f"{name} must be a single path component")

