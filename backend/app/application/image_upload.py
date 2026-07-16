from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from backend.app.domain.catalog import Product
from backend.app.domain.images import ImageKind, ImageRecord, LabelingStatus
from backend.app.infrastructure.file_storage import (
    DEFAULT_MAX_BYTES,
    FileTooLargeError,
    ImportedFile,
    LocalFileStorage,
    StorageCollection,
)
from backend.app.infrastructure.image_processor import (
    ImageProcessor,
    InvalidImageError,
    UnsupportedImageError,
)
from backend.app.infrastructure.image_repository import DuplicateImage


DEFAULT_RESERVE_BYTES = 10 * 1024 * 1024 * 1024
logger = logging.getLogger(__name__)


class CatalogLookupProtocol(Protocol):
    def get_product(self, brand_id: str, product_id: str) -> Product | None: ...


class ImageRepositoryProtocol(Protocol):
    def find_duplicate(self, brand_id: str, sha256: str) -> ImageRecord | None: ...

    def create(
        self,
        *,
        brand_id: str,
        kind: ImageKind,
        product_id: str | None,
        storage_key: str,
        thumbnail_storage_key: str,
        original_filename: str,
        mime_type: str,
        width: int,
        height: int,
        byte_size: int,
        sha256: str,
        labeling_status: LabelingStatus,
    ) -> ImageRecord: ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class DiskSpaceProbeProtocol(Protocol):
    def can_accept(self, byte_limit: int, reserve_bytes: int) -> bool: ...


class ImageUploadError(Exception):
    def __init__(self, code: str, message: str, action: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action


class ImageUploadService:
    def __init__(
        self,
        *,
        catalog_repository: CatalogLookupProtocol,
        image_repository: ImageRepositoryProtocol,
        file_storage: LocalFileStorage,
        image_processor: ImageProcessor,
        disk_space_probe: DiskSpaceProbeProtocol,
    ) -> None:
        self._catalog_repository = catalog_repository
        self._image_repository = image_repository
        self._file_storage = file_storage
        self._image_processor = image_processor
        self._disk_space_probe = disk_space_probe

    def upload(
        self,
        brand_id: str,
        kind: ImageKind,
        product_id: str | None,
        filename: str,
        stream: BinaryIO,
    ) -> ImageRecord:
        if not self._disk_space_probe.can_accept(
            DEFAULT_MAX_BYTES, DEFAULT_RESERVE_BYTES
        ):
            raise self._error("DISK_SPACE_LOW")
        self._validate_product(brand_id, kind, product_id)

        imported: ImportedFile | None = None
        thumbnail_path: Path | None = None
        thumbnail_created = False
        original_key: Path | None = None
        thumbnail_key: Path | None = None
        try:
            imported = self._file_storage.stream_import(
                stream, max_bytes=DEFAULT_MAX_BYTES
            )
            inspected = self._image_processor.inspect(imported.path, filename)
            if self._image_repository.find_duplicate(brand_id, imported.sha256):
                raise self._error("IMAGE_DUPLICATE")

            thumbnail_path = imported.path.with_name(
                f"{uuid4().hex}.thumbnail.webp"
            )
            thumbnail_existed = thumbnail_path.exists()
            try:
                self._image_processor.create_thumbnail(imported.path, thumbnail_path)
            except BaseException:
                thumbnail_created = not thumbnail_existed and thumbnail_path.exists()
                raise
            else:
                thumbnail_created = not thumbnail_existed
            original_key = self._file_storage.promote(
                imported.path,
                collection="originals",
                brand_id=brand_id,
                sha256=imported.sha256,
                extension=inspected.extension,
            )
            thumbnail_key = self._file_storage.promote(
                thumbnail_path,
                collection="thumbnails",
                brand_id=brand_id,
                sha256=imported.sha256,
                extension="webp",
            )
            labeling_status = (
                LabelingStatus.COMPLETED
                if kind == ImageKind.PRODUCT
                else LabelingStatus.UNLABELED
            )
            record = self._image_repository.create(
                brand_id=brand_id,
                kind=kind,
                product_id=product_id,
                storage_key=original_key.as_posix(),
                thumbnail_storage_key=thumbnail_key.as_posix(),
                original_filename=filename,
                mime_type=inspected.mime_type,
                width=inspected.width,
                height=inspected.height,
                byte_size=imported.byte_size,
                sha256=imported.sha256,
                labeling_status=labeling_status,
            )
            self._image_repository.commit()
            return record
        except BaseException as error:
            self._best_effort_rollback(error)
            self._compensate(
                original_error=error,
                imported=imported,
                thumbnail_path=thumbnail_path if thumbnail_created else None,
                original_key=original_key,
                thumbnail_key=thumbnail_key,
            )
            translated = self._translate(error)
            if translated is error:
                raise
            for note in getattr(error, "__notes__", ()):
                translated.add_note(note)
            raise translated from error

    def _best_effort_rollback(self, original_error: BaseException) -> None:
        try:
            self._image_repository.rollback()
        except BaseException as cleanup_error:
            self._record_cleanup_failure(
                original_error, "database rollback", cleanup_error
            )

    def _validate_product(
        self, brand_id: str, kind: ImageKind, product_id: str | None
    ) -> None:
        if kind == ImageKind.TRAY:
            if product_id is not None:
                raise ValueError("TRAY images must not have product_id")
            return
        if kind != ImageKind.PRODUCT:
            raise ValueError("kind must be an ImageKind")
        if not product_id:
            raise self._error("PRODUCT_BRAND_MISMATCH")
        product = self._catalog_repository.get_product(brand_id, product_id)
        if product is None:
            raise self._error("PRODUCT_BRAND_MISMATCH")
        if product.status != "ACTIVE":
            raise self._error("PRODUCT_INACTIVE")

    def _compensate(
        self,
        *,
        original_error: BaseException,
        imported: ImportedFile | None,
        thumbnail_path: Path | None,
        original_key: Path | None,
        thumbnail_key: Path | None,
    ) -> None:
        if thumbnail_key is not None:
            self._delete_storage_file(
                original_error,
                collection="thumbnails",
                storage_key=thumbnail_key,
                label="thumbnail final file",
            )
        if original_key is not None:
            self._delete_storage_file(
                original_error,
                collection="originals",
                storage_key=original_key,
                label="original final file",
            )
        if thumbnail_path is not None:
            self._delete_path(
                original_error, thumbnail_path, "thumbnail temporary file"
            )
        if imported is not None:
            self._delete_path(
                original_error, imported.path, "original temporary file"
            )

    def _delete_storage_file(
        self,
        original_error: BaseException,
        *,
        collection: StorageCollection,
        storage_key: Path,
        label: str,
    ) -> None:
        try:
            path = self._file_storage.resolve(collection, storage_key)
            path.unlink(missing_ok=True)
        except BaseException as cleanup_error:
            self._record_cleanup_failure(
                original_error,
                f"{label} ({collection}/{storage_key.as_posix()})",
                cleanup_error,
            )

    def _delete_path(
        self, original_error: BaseException, path: Path, label: str
    ) -> None:
        try:
            path.unlink(missing_ok=True)
        except BaseException as cleanup_error:
            self._record_cleanup_failure(
                original_error, f"{label} ({path})", cleanup_error
            )

    @staticmethod
    def _record_cleanup_failure(
        original_error: BaseException, label: str, cleanup_error: BaseException
    ) -> None:
        note = (
            f"Upload compensation failed during {label}: "
            f"{type(cleanup_error).__name__}: {cleanup_error}"
        )
        original_error.add_note(note)
        logger.error(
            note,
            exc_info=(
                type(cleanup_error),
                cleanup_error,
                cleanup_error.__traceback__,
            ),
        )

    @staticmethod
    def _translate(error: BaseException) -> BaseException:
        if isinstance(error, ImageUploadError):
            return error
        if isinstance(error, FileTooLargeError):
            return ImageUploadService._error("IMAGE_TOO_LARGE")
        if isinstance(error, UnsupportedImageError):
            return ImageUploadService._error("IMAGE_UNSUPPORTED")
        if isinstance(error, InvalidImageError):
            return ImageUploadService._error("IMAGE_CORRUPT")
        if isinstance(error, DuplicateImage):
            return ImageUploadService._error("IMAGE_DUPLICATE")
        return error

    @staticmethod
    def _error(code: str) -> ImageUploadError:
        details = {
            "IMAGE_TOO_LARGE": (
                "이미지 파일이 너무 커요.",
                "25MB 이하의 파일을 선택해 주세요.",
            ),
            "IMAGE_UNSUPPORTED": (
                "지원하지 않는 이미지 형식이에요.",
                "JPEG, PNG 또는 WebP 파일을 선택해 주세요.",
            ),
            "IMAGE_CORRUPT": (
                "이미지 파일을 읽을 수 없어요.",
                "정상적으로 열리는 다른 파일을 선택해 주세요.",
            ),
            "IMAGE_DUPLICATE": (
                "같은 이미지가 이미 등록되어 있어요.",
                "기존 이미지를 확인해 주세요.",
            ),
            "DISK_SPACE_LOW": (
                "이미지를 저장할 디스크 공간이 부족해요.",
                "디스크 공간을 확보한 뒤 다시 시도해 주세요.",
            ),
            "PRODUCT_INACTIVE": (
                "비활성 상품에는 새 사진을 등록할 수 없어요.",
                "활성 상품을 선택해 주세요.",
            ),
            "PRODUCT_BRAND_MISMATCH": (
                "현재 브랜드의 상품이 아니에요.",
                "현재 브랜드의 활성 상품을 선택해 주세요.",
            ),
        }
        message, action = details[code]
        return ImageUploadError(code, message, action)
