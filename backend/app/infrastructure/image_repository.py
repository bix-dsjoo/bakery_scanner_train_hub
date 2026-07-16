from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.domain.images import ImageKind, ImageRecord, LabelingStatus
from backend.app.infrastructure.models import ImageModel


class DuplicateImage(Exception):
    """Persistence-level duplicate signal translated by the upload service."""


class DiskSpaceProbe:
    def __init__(self, path: Path) -> None:
        self._path = path

    def can_accept(self, byte_limit: int, reserve_bytes: int) -> bool:
        if byte_limit < 0 or reserve_bytes < 0:
            raise ValueError("disk policy values must not be negative")
        return shutil.disk_usage(self._path).free - byte_limit >= reserve_bytes


class ImageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_duplicate(self, brand_id: str, sha256: str) -> ImageRecord | None:
        model = self._session.scalar(
            select(ImageModel).where(
                ImageModel.brand_id == brand_id,
                ImageModel.sha256 == sha256,
            )
        )
        return self._record(model) if model is not None else None

    def get(self, brand_id: str, image_id: str) -> ImageRecord | None:
        model = self._session.scalar(
            select(ImageModel).where(
                ImageModel.id == image_id,
                ImageModel.brand_id == brand_id,
            )
        )
        return self._record(model) if model is not None else None

    def list_page(
        self,
        brand_id: str,
        *,
        kind: ImageKind | None,
        labeling_status: LabelingStatus | None,
        product_id: str | None,
        filename: str | None,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
        limit: int,
    ) -> list[ImageRecord]:
        statement: Select[tuple[ImageModel]] = select(ImageModel).where(
            ImageModel.brand_id == brand_id
        )
        if kind is not None:
            statement = statement.where(ImageModel.kind == kind.value)
        if labeling_status is not None:
            statement = statement.where(
                ImageModel.labeling_status == labeling_status.value
            )
        if product_id is not None:
            statement = statement.where(ImageModel.product_id == product_id)
        if filename is not None:
            statement = statement.where(
                func.lower(ImageModel.original_filename).contains(filename.lower())
            )
        if cursor_created_at is not None and cursor_id is not None:
            database_cursor = cursor_created_at.astimezone(timezone.utc).replace(
                tzinfo=None
            )
            statement = statement.where(
                or_(
                    ImageModel.created_at < database_cursor,
                    (
                        (ImageModel.created_at == database_cursor)
                        & (ImageModel.id < cursor_id)
                    ),
                )
            )
        statement = statement.order_by(
            ImageModel.created_at.desc(), ImageModel.id.desc()
        ).limit(limit)
        return [self._record(model) for model in self._session.scalars(statement)]

    def set_product(
        self, brand_id: str, image_id: str, product_id: str
    ) -> ImageRecord | None:
        model = self._session.scalar(
            select(ImageModel).where(
                ImageModel.id == image_id,
                ImageModel.brand_id == brand_id,
            )
        )
        if model is None:
            return None
        model.product_id = product_id
        self._session.flush()
        return self._record(model)

    def delete(self, brand_id: str, image_id: str) -> bool:
        model = self._session.scalar(
            select(ImageModel).where(
                ImageModel.id == image_id,
                ImageModel.brand_id == brand_id,
            )
        )
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True

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
    ) -> ImageRecord:
        model = ImageModel(
            brand_id=brand_id,
            kind=kind.value,
            product_id=product_id,
            storage_key=storage_key,
            thumbnail_storage_key=thumbnail_storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            width=width,
            height=height,
            byte_size=byte_size,
            sha256=sha256,
            labeling_status=labeling_status.value,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError as error:
            if self._is_duplicate(error):
                raise DuplicateImage from error
            raise
        return self._record(model)

    def commit(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as error:
            if self._is_duplicate(error):
                raise DuplicateImage from error
            raise

    def rollback(self) -> None:
        self._session.rollback()

    @staticmethod
    def _is_duplicate(error: IntegrityError) -> bool:
        detail = str(error.orig).lower()
        return (
            "unique constraint failed" in detail
            and "images.brand_id" in detail
            and "images.sha256" in detail
        )

    @staticmethod
    def _record(model: ImageModel) -> ImageRecord:
        return ImageRecord(
            id=model.id,
            brand_id=model.brand_id,
            kind=ImageKind(model.kind),
            product_id=model.product_id,
            storage_key=model.storage_key,
            thumbnail_storage_key=model.thumbnail_storage_key,
            original_filename=model.original_filename,
            mime_type=model.mime_type,
            width=model.width,
            height=model.height,
            byte_size=model.byte_size,
            sha256=model.sha256,
            labeling_status=LabelingStatus(model.labeling_status),
            revision=model.revision,
            created_at=ImageRepository._as_utc(model.created_at),
            updated_at=ImageRepository._as_utc(model.updated_at),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
