from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.app.application.catalog import CatalogService
from backend.app.config import Settings
from backend.app.domain.catalog import (
    CatalogConflict,
    CatalogNotFound,
    CatalogValidationError,
)
from backend.app.infrastructure.catalog_repository import CatalogRepository
from backend.app.infrastructure.database import create_engine_for
from backend.app.infrastructure.models import Base, ProductModel


@pytest.fixture
def engine(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}",
    )
    database_engine = create_engine_for(settings)
    Base.metadata.create_all(database_engine)
    yield database_engine
    database_engine.dispose()


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine)
    with factory() as database_session:
        yield database_session


@pytest.fixture
def service(session):
    return CatalogService(CatalogRepository(session))


def test_duplicate_brand_name_is_rejected(service):
    service.create_brand("BIXOLON Bakery")

    with pytest.raises(CatalogConflict) as caught:
        service.create_brand(" BIXOLON Bakery ")

    assert caught.value.code == "BRAND_NAME_DUPLICATE"
    assert caught.value.message == "이미 등록된 브랜드 이름이에요."
    assert caught.value.action == "다른 브랜드 이름을 입력해 주세요."
    assert caught.value.field_errors == {"name": "이미 사용 중인 이름이에요."}


def test_product_code_is_unique_inside_brand(service):
    brand = service.create_brand("BIXOLON Bakery")
    service.create_product(brand.id, "BREAD-001", "소금빵")

    with pytest.raises(CatalogConflict) as caught:
        service.create_product(brand.id, " BREAD-001 ", "단팥빵")

    assert caught.value.code == "PRODUCT_CODE_DUPLICATE"
    assert caught.value.message == "같은 브랜드에 이미 등록된 상품 코드예요."
    assert caught.value.action == "다른 상품 코드를 입력해 주세요."
    assert caught.value.field_errors == {"code": "이미 사용 중인 코드예요."}


def test_same_product_code_is_allowed_in_another_brand(service):
    first_brand = service.create_brand("First Bakery")
    second_brand = service.create_brand("Second Bakery")

    first_product = service.create_product(first_brand.id, "BREAD-001", "소금빵")
    second_product = service.create_product(second_brand.id, "BREAD-001", "소금빵")

    assert first_product.brand_id == first_brand.id
    assert second_product.brand_id == second_brand.id
    assert first_product.code == second_product.code == "BREAD-001"


def test_deactivation_keeps_existing_product(service, session):
    brand = service.create_brand("BIXOLON Bakery")
    product = service.create_product(brand.id, "BREAD-001", "소금빵")

    deactivated = service.deactivate_brand(brand.id)

    assert deactivated.status == "INACTIVE"
    assert session.scalar(
        select(func.count()).select_from(ProductModel).where(ProductModel.id == product.id)
    ) == 1
    assert service.list_products(brand.id) == [product]


@pytest.mark.parametrize(
    ("operation", "field"),
    [
        (lambda catalog, brand_id: catalog.create_brand("   "), "name"),
        (
            lambda catalog, brand_id: catalog.create_product(
                brand_id, "   ", "소금빵"
            ),
            "code",
        ),
        (
            lambda catalog, brand_id: catalog.create_product(
                brand_id, "BREAD-001", "   "
            ),
            "name",
        ),
    ],
)
def test_blank_catalog_fields_are_rejected(service, operation, field):
    brand = service.create_brand("BIXOLON Bakery")

    with pytest.raises(CatalogValidationError) as caught:
        operation(service, brand.id)

    assert caught.value.field_errors == {field: f"{field} 값은 비워 둘 수 없어요."}


def test_catalog_values_are_trimmed_and_can_be_updated(service):
    brand = service.create_brand("  BIXOLON Bakery  ")
    product = service.create_product(brand.id, " BREAD-001 ", "  소금빵  ")

    updated_brand = service.update_brand(brand.id, "  BIXOLON Bake Lab  ")
    updated_product = service.update_product(
        brand.id, product.id, code=" BREAD-002 ", name="  단팥빵  "
    )

    assert updated_brand.name == "BIXOLON Bake Lab"
    assert updated_product.code == "BREAD-002"
    assert updated_product.name == "단팥빵"


def test_updates_reject_duplicates(service):
    first_brand = service.create_brand("First Bakery")
    second_brand = service.create_brand("Second Bakery")
    first_product = service.create_product(first_brand.id, "BREAD-001", "소금빵")
    second_product = service.create_product(first_brand.id, "BREAD-002", "단팥빵")

    with pytest.raises(CatalogConflict) as brand_conflict:
        service.update_brand(second_brand.id, " First Bakery ")
    with pytest.raises(CatalogConflict) as product_conflict:
        service.update_product(
            first_brand.id, second_product.id, code=first_product.code
        )

    assert brand_conflict.value.code == "BRAND_NAME_DUPLICATE"
    assert product_conflict.value.code == "PRODUCT_CODE_DUPLICATE"


def test_lists_filter_by_status_query_and_brand(service):
    first_brand = service.create_brand("BIXOLON Bakery")
    second_brand = service.create_brand("Other Bakery")
    salt_bread = service.create_product(first_brand.id, "BREAD-001", "소금빵")
    inactive_product = service.create_product(
        first_brand.id, "BREAD-002", "단팥빵"
    )
    service.create_product(second_brand.id, "BREAD-001", "다른 소금빵")
    inactive_product = service.deactivate_product(
        first_brand.id, inactive_product.id
    )
    second_brand = service.deactivate_brand(second_brand.id)

    assert service.list_brands(status="ACTIVE", query="bixolon") == [first_brand]
    assert service.list_brands(status="INACTIVE") == [second_brand]
    assert service.list_products(
        first_brand.id, status="ACTIVE", query="bread-001"
    ) == [salt_bread]
    assert service.list_products(first_brand.id, query="단팥") == [inactive_product]


def test_missing_or_cross_brand_resources_are_not_found(service):
    first_brand = service.create_brand("First Bakery")
    second_brand = service.create_brand("Second Bakery")
    product = service.create_product(first_brand.id, "BREAD-001", "소금빵")

    with pytest.raises(CatalogNotFound) as missing_brand:
        service.update_brand("missing-brand", "Missing")
    with pytest.raises(CatalogNotFound) as missing_product:
        service.update_product(second_brand.id, product.id, name="단팥빵")
    with pytest.raises(CatalogNotFound):
        service.list_products("missing-brand")

    assert missing_brand.value.code == "BRAND_NOT_FOUND"
    assert missing_product.value.code == "PRODUCT_NOT_FOUND"


def test_product_deactivation_updates_status_without_deleting(service, session):
    brand = service.create_brand("BIXOLON Bakery")
    product = service.create_product(brand.id, "BREAD-001", "소금빵")

    deactivated = service.deactivate_product(brand.id, product.id)

    assert deactivated.status == "INACTIVE"
    assert session.scalar(
        select(func.count()).select_from(ProductModel).where(ProductModel.id == product.id)
    ) == 1
