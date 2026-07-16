from pathlib import Path
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.config import Settings
from backend.app.domain.images import ImageKind, ImageRecord, LabelingStatus
from backend.app.infrastructure.database import create_engine_for
from backend.app.infrastructure.models import Base, BrandModel, ImageModel, ProductModel


def database_test_settings(data_dir: Path) -> Settings:
    database_path = data_dir / "database" / "app.db"
    return Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )


@pytest.fixture
def migrated_engine(tmp_path: Path, monkeypatch):
    migration_settings = database_test_settings(tmp_path)
    monkeypatch.setenv("BAKERY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BAKERY_DATABASE_URL", migration_settings.database_url)
    repository_root = Path(__file__).parents[3]

    command.upgrade(Config(repository_root / "alembic.ini"), "head")

    database_engine = create_engine_for(migration_settings)
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def model_engine(tmp_path: Path):
    database_engine = create_engine_for(database_test_settings(tmp_path))
    Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


def insert_catalog(connection) -> None:
    connection.exec_driver_sql(
        "INSERT INTO brands (id, name) VALUES (?, ?)",
        ("brand-1", "BIXOLON Bakery"),
    )
    connection.exec_driver_sql(
        "INSERT INTO products (id, brand_id, code, name) VALUES (?, ?, ?, ?)",
        ("product-1", "brand-1", "BREAD-001", "소금빵"),
    )


def image_values(**overrides):
    values = {
        "id": "image-1",
        "brand_id": "brand-1",
        "kind": "PRODUCT",
        "product_id": "product-1",
        "storage_key": "brand-1/ab/cd/image-1.jpg",
        "thumbnail_storage_key": "brand-1/ab/cd/image-1.webp",
        "original_filename": "salt-bread.jpg",
        "mime_type": "image/jpeg",
        "width": 1920,
        "height": 1080,
        "byte_size": 123456,
        "sha256": "a" * 64,
        "labeling_status": "COMPLETED",
    }
    values.update(overrides)
    return values


def insert_image(connection, **overrides) -> None:
    values = image_values(**overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{column}" for column in values)
    connection.exec_driver_sql(
        f"INSERT INTO images ({columns}) VALUES ({placeholders})", values
    )


def test_image_migration_creates_all_metadata_columns(migrated_engine):
    columns = {
        column["name"]: column
        for column in inspect(migrated_engine).get_columns("images")
    }

    assert set(columns) == {
        "id",
        "brand_id",
        "kind",
        "product_id",
        "storage_key",
        "thumbnail_storage_key",
        "original_filename",
        "mime_type",
        "width",
        "height",
        "byte_size",
        "sha256",
        "labeling_status",
        "revision",
        "created_at",
        "updated_at",
    }
    assert columns["product_id"]["nullable"]
    for name, column in columns.items():
        if name != "product_id":
            assert not column["nullable"]
    assert columns["revision"]["default"] is not None
    assert columns["created_at"]["default"] is not None
    assert columns["updated_at"]["default"] is not None


def test_image_kind_requires_the_matching_product_link(migrated_engine):
    with migrated_engine.begin() as connection:
        insert_catalog(connection)
        insert_image(connection)
        insert_image(
            connection,
            id="image-2",
            kind="TRAY",
            product_id=None,
            sha256="b" * 64,
            labeling_status="UNLABELED",
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        insert_image(connection, id="image-3", product_id=None, sha256="c" * 64)

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        insert_image(
            connection,
            id="image-4",
            kind="TRAY",
            sha256="d" * 64,
            labeling_status="UNLABELED",
        )


def test_image_sha256_is_unique_within_brand(migrated_engine):
    with migrated_engine.begin() as connection:
        insert_catalog(connection)
        insert_image(connection)

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        insert_image(connection, id="image-2")


def test_image_library_has_composite_lookup_index(migrated_engine):
    indexes = inspect(migrated_engine).get_indexes("images")

    assert any(
        index["column_names"]
        == ["brand_id", "kind", "labeling_status", "created_at", "id"]
        for index in indexes
    )


def test_image_foreign_keys_restrict_catalog_deletion(migrated_engine):
    foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspect(migrated_engine).get_foreign_keys("images")
    }
    assert foreign_keys[("brand_id",)]["options"]["ondelete"] == "RESTRICT"
    assert foreign_keys[("product_id",)]["options"]["ondelete"] == "RESTRICT"

    with migrated_engine.begin() as connection:
        insert_catalog(connection)
        insert_image(connection)

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "DELETE FROM products WHERE id = ?", ("product-1",)
        )
    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM brands WHERE id = ?", ("brand-1",))


def test_image_model_defaults_revision_to_zero(model_engine):
    session_factory = sessionmaker(bind=model_engine)
    with session_factory() as session:
        brand = BrandModel(name="BIXOLON Bakery")
        session.add(brand)
        session.flush()
        product = ProductModel(
            brand_id=brand.id, code="BREAD-001", name="소금빵"
        )
        session.add(product)
        session.flush()
        image = ImageModel(
            brand_id=brand.id,
            kind=ImageKind.PRODUCT.value,
            product_id=product.id,
            storage_key="brand/ab/cd/image.jpg",
            thumbnail_storage_key="brand/ab/cd/image.webp",
            original_filename="salt-bread.jpg",
            mime_type="image/jpeg",
            width=1920,
            height=1080,
            byte_size=123456,
            sha256="a" * 64,
            labeling_status=LabelingStatus.COMPLETED.value,
        )
        session.add(image)
        session.commit()
        session.refresh(image)

        assert image.revision == 0
        assert session.scalar(select(ImageModel).where(ImageModel.id == image.id))


def make_record(**overrides) -> ImageRecord:
    now = datetime.now(timezone.utc)
    values = {
        "id": "image-1",
        "brand_id": "brand-1",
        "kind": ImageKind.PRODUCT,
        "product_id": "product-1",
        "storage_key": "brand-1/ab/cd/image-1.jpg",
        "thumbnail_storage_key": "brand-1/ab/cd/image-1.webp",
        "original_filename": "salt-bread.jpg",
        "mime_type": "image/jpeg",
        "width": 1920,
        "height": 1080,
        "byte_size": 123456,
        "sha256": "a" * 64,
        "labeling_status": LabelingStatus.COMPLETED,
        "revision": 0,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return ImageRecord(**values)


def test_image_record_is_immutable_and_validates_product_link():
    record = make_record()
    with pytest.raises(FrozenInstanceError):
        record.revision = 1  # type: ignore[misc]

    make_record(
        kind=ImageKind.TRAY,
        product_id=None,
        labeling_status=LabelingStatus.UNLABELED,
    )
    with pytest.raises(ValueError):
        make_record(product_id=None)
    with pytest.raises(ValueError):
        make_record(kind=ImageKind.TRAY)
