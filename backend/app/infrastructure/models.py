from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CatalogFields:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    status: Mapped[str] = mapped_column(
        String(8), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )


class BrandModel(CatalogFields, Base):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class ProductModel(CatalogFields, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("brand_id", "code", name="uq_products_brand_id_code"),
    )

    brand_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ImageModel(Base):
    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('PRODUCT', 'TRAY')", name="ck_images_kind"
        ),
        CheckConstraint(
            "labeling_status IN ('UNLABELED', 'COMPLETED')",
            name="ck_images_labeling_status",
        ),
        CheckConstraint(
            "(kind = 'PRODUCT' AND product_id IS NOT NULL) "
            "OR (kind = 'TRAY' AND product_id IS NULL)",
            name="ck_images_kind_product_id",
        ),
        UniqueConstraint(
            "brand_id", "sha256", name="uq_images_brand_id_sha256"
        ),
        Index(
            "ix_images_library",
            "brand_id",
            "kind",
            "labeling_status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    brand_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(7), nullable=False)
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    labeling_status: Mapped[str] = mapped_column(String(9), nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.current_timestamp(),
    )
