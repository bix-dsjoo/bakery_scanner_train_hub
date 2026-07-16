from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.app.domain.images import ImageKind, ImageRecord, LabelingStatus
from backend.app.infrastructure.catalog_repository import CatalogRepository
from backend.app.infrastructure.file_storage import (
    LocalFileStorage,
    StorageCollection,
    TrashEntry,
)
from backend.app.infrastructure.image_repository import ImageRepository


logger = logging.getLogger(__name__)


class ImageLibraryError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        action: str | None = None,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.action = action
        self.field_errors = field_errors


@dataclass(frozen=True)
class ImagePage:
    items: list[ImageRecord]
    next_cursor: str | None


class ImageLibraryService:
    def __init__(
        self,
        *,
        catalog_repository: CatalogRepository,
        image_repository: ImageRepository,
        file_storage: LocalFileStorage,
    ) -> None:
        self._catalog_repository = catalog_repository
        self._image_repository = image_repository
        self._file_storage = file_storage

    def require_brand(self, brand_id: str) -> None:
        if self._catalog_repository.get_brand(brand_id) is None:
            raise ImageLibraryError(
                404,
                "BRAND_NOT_FOUND",
                "브랜드를 찾을 수 없어요.",
                "브랜드 목록을 새로고침해 주세요.",
            )

    def get(self, brand_id: str, image_id: str) -> ImageRecord:
        record = self._image_repository.get(brand_id, image_id)
        if record is None:
            raise self._not_found()
        return record

    def list_images(
        self,
        brand_id: str,
        *,
        kind: ImageKind | None,
        labeling_status: LabelingStatus | None,
        product_id: str | None,
        filename: str | None,
        cursor: str | None,
        limit: int,
    ) -> ImagePage:
        self.require_brand(brand_id)
        cursor_created_at, cursor_id = self._decode_cursor(cursor)
        records = self._image_repository.list_page(
            brand_id,
            kind=kind,
            labeling_status=labeling_status,
            product_id=product_id,
            filename=filename,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            limit=limit + 1,
        )
        has_next = len(records) > limit
        items = records[:limit]
        next_cursor = self._encode_cursor(items[-1]) if has_next else None
        return ImagePage(items=items, next_cursor=next_cursor)

    def resolve_file(
        self, brand_id: str, image_id: str, collection: StorageCollection
    ) -> tuple[ImageRecord, Path]:
        record = self.get(brand_id, image_id)
        if collection == "originals":
            storage_key = record.storage_key
        elif collection == "thumbnails":
            storage_key = record.thumbnail_storage_key
        else:
            raise ValueError("unsupported image collection")
        path = self._file_storage.resolve(collection, storage_key)
        if not path.is_file():
            raise ImageLibraryError(
                404,
                "IMAGE_FILE_MISSING",
                "이미지 파일을 찾을 수 없어요.",
                "관리자에게 저장소 상태 확인을 요청해 주세요.",
            )
        return record, path

    def change_product(
        self, brand_id: str, image_id: str, product_id: str | None
    ) -> ImageRecord:
        record = self.get(brand_id, image_id)
        if record.kind == ImageKind.TRAY:
            raise ImageLibraryError(
                422,
                "TRAY_PRODUCT_CHANGE_FORBIDDEN",
                "트레이 사진의 상품은 사진에서 변경할 수 없어요.",
                "라벨링 화면에서 박스별 상품을 지정해 주세요.",
            )
        if not product_id:
            raise ImageLibraryError(
                422,
                "PRODUCT_REQUIRED",
                "상품 사진에는 상품이 필요해요.",
                "현재 브랜드의 활성 상품을 선택해 주세요.",
                {"product_id": "상품을 선택해 주세요."},
            )
        product = self._catalog_repository.get_product(brand_id, product_id)
        if product is None:
            raise ImageLibraryError(
                422,
                "PRODUCT_BRAND_MISMATCH",
                "현재 브랜드의 상품이 아니에요.",
                "현재 브랜드의 활성 상품을 선택해 주세요.",
                {"product_id": "현재 브랜드의 상품을 선택해 주세요."},
            )
        if product.status != "ACTIVE":
            raise ImageLibraryError(
                422,
                "PRODUCT_INACTIVE",
                "비활성 상품에는 사진을 연결할 수 없어요.",
                "활성 상품을 선택해 주세요.",
                {"product_id": "활성 상품을 선택해 주세요."},
            )
        changed = self._image_repository.set_product(brand_id, image_id, product_id)
        if changed is None:
            raise self._not_found()
        self._image_repository.commit()
        return changed

    def delete(self, brand_id: str, image_id: str) -> None:
        record = self.get(brand_id, image_id)
        moved: list[TrashEntry] = []
        try:
            moved.append(
                self._file_storage.move_to_trash("originals", record.storage_key)
            )
            moved.append(
                self._file_storage.move_to_trash(
                    "thumbnails", record.thumbnail_storage_key
                )
            )
            if not self._image_repository.delete(brand_id, image_id):
                raise self._not_found()
            self._image_repository.commit()
        except FileNotFoundError as error:
            self._image_repository.rollback()
            self._restore(moved, error)
            raise ImageLibraryError(
                404,
                "IMAGE_FILE_MISSING",
                "이미지 파일을 찾을 수 없어요.",
                "관리자에게 저장소 상태 확인을 요청해 주세요.",
            ) from error
        except BaseException as error:
            self._image_repository.rollback()
            self._restore(moved, error)
            raise

        for entry in moved:
            try:
                self._file_storage.delete_trash(entry)
            except BaseException as error:
                logger.error(
                    "Image trash cleanup failed after delete for image %s",
                    image_id,
                    exc_info=error,
                )

    def _restore(self, moved: list[TrashEntry], original_error: BaseException) -> None:
        for entry in reversed(moved):
            try:
                self._file_storage.restore_from_trash(entry)
            except BaseException as restore_error:
                original_error.add_note(
                    f"Image delete compensation failed: {type(restore_error).__name__}"
                )
                logger.error(
                    "Image delete compensation failed for %s",
                    entry.collection,
                    exc_info=restore_error,
                )

    @staticmethod
    def _not_found() -> ImageLibraryError:
        return ImageLibraryError(
            404,
            "IMAGE_NOT_FOUND",
            "이미지를 찾을 수 없어요.",
            "현재 브랜드의 이미지 목록을 새로고침해 주세요.",
        )

    @staticmethod
    def _encode_cursor(record: ImageRecord) -> str:
        payload = json.dumps(
            {
                "created_at": ImageLibraryService._as_utc(
                    record.created_at
                ).isoformat(),
                "id": record.id,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
        if cursor is None:
            return None, None
        try:
            padding = "=" * (-len(cursor) % 4)
            raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
            payload = json.loads(raw)
            if set(payload) != {"created_at", "id"} or not isinstance(
                payload["id"], str
            ) or not payload["id"]:
                raise ValueError("invalid cursor payload")
            created_at = datetime.fromisoformat(payload["created_at"])
            return ImageLibraryService._as_utc(created_at), payload["id"]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error) as error:
            raise ImageLibraryError(
                422,
                "IMAGE_CURSOR_INVALID",
                "목록 위치 정보를 읽을 수 없어요.",
                "목록을 처음부터 다시 불러와 주세요.",
                {"cursor": "유효하지 않은 목록 위치예요."},
            ) from error

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
