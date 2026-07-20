from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.config import Settings
from backend.app.infrastructure.database import create_engine_for, session_scope
from backend.app.infrastructure.models import Base, BrandModel, ProductModel


def database_test_settings(data_dir: Path) -> Settings:
    database_path = data_dir / "database" / "app.db"
    return Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return database_test_settings(tmp_path)


@pytest.fixture
def engine(settings: Settings):
    database_engine = create_engine_for(settings)
    Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def migrated_engine(tmp_path: Path, monkeypatch):
    migration_settings = database_test_settings(tmp_path)
    monkeypatch.setenv("BAKERY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BAKERY_DATABASE_URL", migration_settings.database_url)
    repository_root = Path(__file__).parents[3]

    command.upgrade(Config(repository_root / "alembic.ini"), "0001_catalog")

    database_engine = create_engine_for(migration_settings)
    yield database_engine
    database_engine.dispose()


def test_database_tests_ignore_ambient_database_url(tmp_path: Path, monkeypatch):
    external_database = tmp_path.parent / f"{tmp_path.name}-business.db"
    expected_database = tmp_path / "database" / "app.db"
    monkeypatch.setenv(
        "BAKERY_DATABASE_URL", f"sqlite:///{external_database.as_posix()}"
    )

    test_engine = create_engine_for(database_test_settings(tmp_path))
    try:
        Base.metadata.create_all(test_engine)
        assert expected_database.exists()
        assert not external_database.exists()
    finally:
        test_engine.dispose()
        external_database.unlink(missing_ok=True)


def test_new_connections_apply_sqlite_policies(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000


def test_brand_name_must_be_unique(engine):
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        session.add(BrandModel(name="BIXOLON Bakery"))
        session.commit()
        session.add(BrandModel(name="BIXOLON Bakery"))

        with pytest.raises(IntegrityError):
            session.commit()


def test_product_code_must_be_unique_within_brand(engine):
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        brand = BrandModel(name="BIXOLON Bakery")
        session.add(brand)
        session.flush()
        session.add(ProductModel(brand_id=brand.id, code="BREAD-001", name="소금빵"))
        session.commit()
        session.add(ProductModel(brand_id=brand.id, code="BREAD-001", name="단팥빵"))

        with pytest.raises(IntegrityError):
            session.commit()


def test_session_scope_commits_successful_work(engine):
    session_factory = sessionmaker(bind=engine)

    with session_scope(session_factory) as session:
        session.add(BrandModel(name="BIXOLON Bakery"))

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(BrandModel)) == 1


def test_session_scope_rolls_back_failed_work(engine):
    session_factory = sessionmaker(bind=engine)

    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as session:
            session.add(BrandModel(name="BIXOLON Bakery"))
            raise RuntimeError("stop transaction")

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(BrandModel)) == 0


def test_catalog_migration_creates_required_tables_and_columns(migrated_engine):
    schema = inspect(migrated_engine)
    assert set(schema.get_table_names()) == {
        "alembic_version",
        "brands",
        "products",
    }

    brand_columns = {column["name"]: column for column in schema.get_columns("brands")}
    product_columns = {
        column["name"]: column for column in schema.get_columns("products")
    }
    assert set(brand_columns) == {"id", "name", "status", "created_at", "updated_at"}
    assert set(product_columns) == {
        "id",
        "brand_id",
        "code",
        "name",
        "status",
        "created_at",
        "updated_at",
    }
    assert all(not column["nullable"] for column in brand_columns.values())
    assert all(not column["nullable"] for column in product_columns.values())
    for columns in (brand_columns, product_columns):
        assert columns["status"]["default"] is not None
        assert columns["created_at"]["default"] is not None
        assert columns["updated_at"]["default"] is not None


def test_catalog_migration_makes_brand_name_globally_unique(migrated_engine):
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspect(migrated_engine).get_unique_constraints("brands")
    }
    assert ("name",) in unique_columns

    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO brands (id, name) VALUES (?, ?)",
            ("brand-1", "BIXOLON Bakery"),
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO brands (id, name) VALUES (?, ?)",
            ("brand-2", "BIXOLON Bakery"),
        )


def test_catalog_migration_scopes_product_code_unique_to_brand(migrated_engine):
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspect(migrated_engine).get_unique_constraints("products")
    }
    assert ("brand_id", "code") in unique_columns

    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO brands (id, name) VALUES (?, ?)",
            ("brand-1", "First Bakery"),
        )
        connection.exec_driver_sql(
            "INSERT INTO brands (id, name) VALUES (?, ?)",
            ("brand-2", "Second Bakery"),
        )
        connection.exec_driver_sql(
            "INSERT INTO products (id, brand_id, code, name) VALUES (?, ?, ?, ?)",
            ("product-1", "brand-1", "BREAD-001", "소금빵"),
        )
        connection.exec_driver_sql(
            "INSERT INTO products (id, brand_id, code, name) VALUES (?, ?, ?, ?)",
            ("product-2", "brand-2", "BREAD-001", "소금빵"),
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO products (id, brand_id, code, name) VALUES (?, ?, ?, ?)",
            ("product-3", "brand-1", "BREAD-001", "단팥빵"),
        )


def test_catalog_migration_restricts_deleting_brand_with_product(migrated_engine):
    foreign_keys = inspect(migrated_engine).get_foreign_keys("products")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["constrained_columns"] == ["brand_id"]
    assert foreign_keys[0]["referred_table"] == "brands"
    assert foreign_keys[0]["referred_columns"] == ["id"]
    assert foreign_keys[0]["options"]["ondelete"] == "RESTRICT"

    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO brands (id, name) VALUES (?, ?)",
            ("brand-1", "BIXOLON Bakery"),
        )
        connection.exec_driver_sql(
            "INSERT INTO products (id, brand_id, code, name) VALUES (?, ?, ?, ?)",
            ("product-1", "brand-1", "BREAD-001", "소금빵"),
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM brands WHERE id = ?", ("brand-1",))
