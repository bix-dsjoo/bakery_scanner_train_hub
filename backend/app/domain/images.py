from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ImageKind(StrEnum):
    PRODUCT = "PRODUCT"
    TRAY = "TRAY"


class LabelingStatus(StrEnum):
    UNLABELED = "UNLABELED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ImageRecord:
    id: str
    brand_id: str
    kind: ImageKind
    product_id: str | None
    storage_key: str
    thumbnail_storage_key: str
    original_filename: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str
    labeling_status: LabelingStatus
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.kind == ImageKind.PRODUCT and self.product_id is None:
            raise ValueError("PRODUCT images require product_id")
        if self.kind == ImageKind.TRAY and self.product_id is not None:
            raise ValueError("TRAY images must not have product_id")
