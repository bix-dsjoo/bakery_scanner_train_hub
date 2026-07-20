"""Create image metadata table.

Revision ID: 0002_images
Revises: 0001_catalog
Create Date: 2026-07-16

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_images"
down_revision: str | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("brand_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=7), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column(
            "thumbnail_storage_key", sa.String(length=500), nullable=False
        ),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("labeling_status", sa.String(length=9), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('PRODUCT', 'TRAY')", name="ck_images_kind"
        ),
        sa.CheckConstraint(
            "labeling_status IN ('UNLABELED', 'COMPLETED')",
            name="ck_images_labeling_status",
        ),
        sa.CheckConstraint(
            "(kind = 'PRODUCT' AND product_id IS NOT NULL) "
            "OR (kind = 'TRAY' AND product_id IS NULL)",
            name="ck_images_kind_product_id",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brand_id", "sha256", name="uq_images_brand_id_sha256"
        ),
    )
    op.create_index(
        "ix_images_library",
        "images",
        ["brand_id", "kind", "labeling_status", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_images_library", table_name="images")
    op.drop_table("images")
