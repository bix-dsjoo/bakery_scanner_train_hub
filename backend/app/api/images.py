from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.app.api.dependencies import (
    ImageLibraryServiceDependency,
    ImageUploadServiceDependency,
)
from backend.app.application.image_library import ImageLibraryError
from backend.app.domain.images import ImageKind, ImageRecord, LabelingStatus


router = APIRouter(prefix="/api/v1", tags=["images"])


class ImageResponse(BaseModel):
    id: str
    brand_id: str
    kind: ImageKind
    product_id: str | None
    original_filename: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    labeling_status: LabelingStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    box_count: int = 0

    @classmethod
    def from_record(cls, record: ImageRecord) -> "ImageResponse":
        return cls(
            id=record.id,
            brand_id=record.brand_id,
            kind=record.kind,
            product_id=record.product_id,
            original_filename=record.original_filename,
            mime_type=record.mime_type,
            width=record.width,
            height=record.height,
            byte_size=record.byte_size,
            labeling_status=record.labeling_status,
            revision=record.revision,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ImageListResponse(BaseModel):
    items: list[ImageResponse]
    next_cursor: str | None


class ProductChange(BaseModel):
    product_id: str | None


@router.post(
    "/brands/{brand_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_image(
    brand_id: str,
    library: ImageLibraryServiceDependency,
    upload_service: ImageUploadServiceDependency,
    kind: Annotated[Literal["PRODUCT", "TRAY"], Form()],
    file: Annotated[UploadFile, File()],
    product_id: Annotated[str | None, Form()] = None,
) -> ImageResponse:
    library.require_brand(brand_id)
    image_kind = ImageKind(kind)
    if image_kind == ImageKind.PRODUCT and not product_id:
        raise ImageLibraryError(
            422,
            "PRODUCT_REQUIRED",
            "상품 사진에는 상품이 필요해요.",
            "현재 브랜드의 활성 상품을 선택해 주세요.",
            {"product_id": "상품을 선택해 주세요."},
        )
    if image_kind == ImageKind.TRAY and product_id is not None:
        raise ImageLibraryError(
            422,
            "TRAY_PRODUCT_FORBIDDEN",
            "트레이 사진에는 상품을 직접 연결할 수 없어요.",
            "상품은 라벨링 화면에서 박스별로 지정해 주세요.",
            {"product_id": "트레이 사진에서는 비워 주세요."},
        )
    filename = file.filename or "upload"
    return ImageResponse.from_record(
        upload_service.upload(
            brand_id, image_kind, product_id, filename, file.file
        )
    )


@router.get("/brands/{brand_id}/images", response_model=ImageListResponse)
def list_images(
    brand_id: str,
    library: ImageLibraryServiceDependency,
    kind: Literal["PRODUCT", "TRAY"] | None = None,
    status_filter: Annotated[
        Literal["UNLABELED", "COMPLETED"] | None, Query(alias="status")
    ] = None,
    product_id: str | None = None,
    filename: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ImageListResponse:
    page = library.list_images(
        brand_id,
        kind=ImageKind(kind) if kind else None,
        labeling_status=LabelingStatus(status_filter) if status_filter else None,
        product_id=product_id,
        filename=filename,
        cursor=cursor,
        limit=limit,
    )
    return ImageListResponse(
        items=[ImageResponse.from_record(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/images/{image_id}", response_model=ImageResponse)
def get_image(
    image_id: str,
    brand_id: str,
    library: ImageLibraryServiceDependency,
) -> ImageResponse:
    return ImageResponse.from_record(library.get(brand_id, image_id))


@router.patch("/images/{image_id}/product", response_model=ImageResponse)
def change_product(
    image_id: str,
    brand_id: str,
    request: ProductChange,
    library: ImageLibraryServiceDependency,
) -> ImageResponse:
    return ImageResponse.from_record(
        library.change_product(brand_id, image_id, request.product_id)
    )


@router.get("/images/{image_id}/original")
def get_original(
    image_id: str,
    brand_id: str,
    library: ImageLibraryServiceDependency,
) -> FileResponse:
    record, path = library.resolve_file(brand_id, image_id, "originals")
    return FileResponse(
        path,
        media_type=record.mime_type,
        filename=record.original_filename,
        content_disposition_type="attachment",
    )


@router.get("/images/{image_id}/thumbnail")
def get_thumbnail(
    image_id: str,
    brand_id: str,
    library: ImageLibraryServiceDependency,
) -> FileResponse:
    record, path = library.resolve_file(brand_id, image_id, "thumbnails")
    filename = f"{Path(record.original_filename).stem}.webp"
    return FileResponse(
        path,
        media_type="image/webp",
        filename=filename,
        content_disposition_type="inline",
    )


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: str,
    brand_id: str,
    library: ImageLibraryServiceDependency,
) -> Response:
    library.delete(brand_id, image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
