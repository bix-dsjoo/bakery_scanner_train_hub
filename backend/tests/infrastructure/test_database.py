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


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path)


@pytest.fixture
def engine(settings: Settings):
    database_engine = create_engine_for(settings)
    Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


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


def test_catalog_migration_creates_expected_tables(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAKERY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("BAKERY_DATABASE_URL", raising=False)
    repository_root = Path(__file__).parents[3]

    command.upgrade(Config(repository_root / "alembic.ini"), "head")

    migration_engine = create_engine_for(Settings(data_dir=tmp_path))
    try:
        assert set(inspect(migration_engine).get_table_names()) == {
            "alembic_version",
            "brands",
            "products",
        }
    finally:
        migration_engine.dispose()
