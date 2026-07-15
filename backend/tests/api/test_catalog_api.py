from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_catalog_service
from backend.app.config import Settings
from backend.app.infrastructure.database import create_engine_for
from backend.app.infrastructure.models import Base
from backend.app.main import create_app


def assert_utc_iso8601(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def create_test_app(settings: Settings) -> FastAPI:
    engine = create_engine_for(settings)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return create_app(settings)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_test_app(Settings(data_dir=tmp_path))) as test_client:
        yield test_client


def test_brand_create_list_update_and_deactivate(client: TestClient) -> None:
    created_response = client.post(
        "/api/v1/brands", json={"name": "  BIXOLON Bakery  "}
    )

    assert created_response.status_code == 201
    created = created_response.json()
    assert created["name"] == "BIXOLON Bakery"
    assert created["status"] == "ACTIVE"
    assert_utc_iso8601(created["created_at"])
    assert_utc_iso8601(created["updated_at"])

    updated_response = client.patch(
        f"/api/v1/brands/{created['id']}", json={"name": "BIXOLON Bake Lab"}
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["name"] == "BIXOLON Bake Lab"

    deactivated_response = client.patch(
        f"/api/v1/brands/{created['id']}", json={"status": "INACTIVE"}
    )
    assert deactivated_response.status_code == 200
    assert deactivated_response.json()["status"] == "INACTIVE"

    assert client.get("/api/v1/brands", params={"status": "ACTIVE"}).json() == []
    assert client.get(
        "/api/v1/brands", params={"status": "INACTIVE", "query": "bake lab"}
    ).json() == [deactivated_response.json()]


def test_products_are_created_filtered_updated_and_scoped_to_brand(
    client: TestClient,
) -> None:
    first_brand = client.post(
        "/api/v1/brands", json={"name": "First Bakery"}
    ).json()
    second_brand = client.post(
        "/api/v1/brands", json={"name": "Second Bakery"}
    ).json()
    salt_bread_response = client.post(
        f"/api/v1/brands/{first_brand['id']}/products",
        json={"code": " BREAD-001 ", "name": " 소금빵 "},
    )
    inactive_product = client.post(
        f"/api/v1/brands/{first_brand['id']}/products",
        json={"code": "BREAD-002", "name": "단팥빵"},
    ).json()
    client.post(
        f"/api/v1/brands/{second_brand['id']}/products",
        json={"code": "BREAD-001", "name": "다른 소금빵"},
    )

    assert salt_bread_response.status_code == 201
    salt_bread = salt_bread_response.json()
    assert salt_bread["brand_id"] == first_brand["id"]
    assert salt_bread["code"] == "BREAD-001"
    assert salt_bread["name"] == "소금빵"
    assert_utc_iso8601(salt_bread["created_at"])

    updated_response = client.patch(
        f"/api/v1/brands/{first_brand['id']}/products/{salt_bread['id']}",
        json={"code": "BREAD-010", "name": "프리미엄 소금빵"},
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["code"] == "BREAD-010"
    assert updated_response.json()["name"] == "프리미엄 소금빵"

    deactivated_response = client.patch(
        f"/api/v1/brands/{first_brand['id']}/products/{inactive_product['id']}",
        json={"status": "INACTIVE"},
    )
    assert deactivated_response.status_code == 200
    assert deactivated_response.json()["status"] == "INACTIVE"

    active_products = client.get(
        f"/api/v1/brands/{first_brand['id']}/products",
        params={"status": "ACTIVE", "query": "프리미엄"},
    )
    assert active_products.status_code == 200
    assert active_products.json() == [updated_response.json()]

    inactive_products = client.get(
        f"/api/v1/brands/{first_brand['id']}/products",
        params={"status": "INACTIVE", "query": "bread-002"},
    )
    assert inactive_products.json() == [deactivated_response.json()]
    assert all(
        product["brand_id"] == first_brand["id"]
        for product in client.get(
            f"/api/v1/brands/{first_brand['id']}/products"
        ).json()
    )


def test_duplicate_product_code_returns_common_conflict_error(
    client: TestClient,
) -> None:
    brand = client.post("/api/v1/brands", json={"name": "BIXOLON Bakery"}).json()
    product_url = f"/api/v1/brands/{brand['id']}/products"
    client.post(product_url, json={"code": "BREAD-001", "name": "소금빵"})

    response = client.post(
        product_url, json={"code": " BREAD-001 ", "name": "단팥빵"}
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "PRODUCT_CODE_DUPLICATE",
        "message": "같은 브랜드에 이미 등록된 상품 코드예요.",
        "action": "다른 상품 코드를 입력해 주세요.",
        "field_errors": {"code": "이미 사용 중인 코드예요."},
    }


def test_duplicate_brand_name_returns_common_conflict_error(client: TestClient) -> None:
    client.post("/api/v1/brands", json={"name": "BIXOLON Bakery"})

    response = client.post(
        "/api/v1/brands", json={"name": " BIXOLON Bakery "}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "BRAND_NAME_DUPLICATE"
    assert response.json()["field_errors"] == {
        "name": "이미 사용 중인 이름이에요."
    }


def test_missing_and_cross_brand_resources_return_common_not_found_error(
    client: TestClient,
) -> None:
    first_brand = client.post(
        "/api/v1/brands", json={"name": "First Bakery"}
    ).json()
    second_brand = client.post(
        "/api/v1/brands", json={"name": "Second Bakery"}
    ).json()
    product = client.post(
        f"/api/v1/brands/{first_brand['id']}/products",
        json={"code": "BREAD-001", "name": "소금빵"},
    ).json()

    missing_brand = client.get("/api/v1/brands/missing/products")
    cross_brand_product = client.patch(
        f"/api/v1/brands/{second_brand['id']}/products/{product['id']}",
        json={"name": "단팥빵"},
    )

    assert missing_brand.status_code == 404
    assert missing_brand.json() == {
        "code": "BRAND_NOT_FOUND",
        "message": "브랜드를 찾을 수 없어요.",
        "action": "브랜드 목록을 새로고침해 주세요.",
    }
    assert cross_brand_product.status_code == 404
    assert cross_brand_product.json()["code"] == "PRODUCT_NOT_FOUND"


def test_request_and_catalog_validation_errors_use_common_shape(
    client: TestClient,
) -> None:
    too_long_name = client.post("/api/v1/brands", json={"name": "가" * 101})
    blank_name = client.post("/api/v1/brands", json={"name": "   "})
    invalid_status = client.get(
        "/api/v1/brands", params={"status": "ARCHIVED"}
    )

    assert too_long_name.status_code == 422
    assert too_long_name.json()["code"] == "REQUEST_VALIDATION_ERROR"
    assert too_long_name.json()["message"] == "입력값을 확인해 주세요."
    assert too_long_name.json()["field_errors"] == {
        "name": "문자열은 100자 이하여야 해요."
    }
    assert blank_name.status_code == 422
    assert blank_name.json()["code"] == "CATALOG_FIELD_REQUIRED"
    assert blank_name.json()["field_errors"] == {
        "name": "name 값은 비워 둘 수 없어요."
    }
    assert invalid_status.status_code == 422
    assert invalid_status.json()["code"] == "CATALOG_STATUS_INVALID"


def test_patch_requires_a_change_and_only_supports_deactivation(
    client: TestClient,
) -> None:
    brand = client.post("/api/v1/brands", json={"name": "BIXOLON Bakery"}).json()

    empty_patch = client.patch(f"/api/v1/brands/{brand['id']}", json={})
    reactivation = client.patch(
        f"/api/v1/brands/{brand['id']}", json={"status": "ACTIVE"}
    )

    assert empty_patch.status_code == 422
    assert empty_patch.json()["code"] == "REQUEST_VALIDATION_ERROR"
    assert reactivation.status_code == 422
    assert reactivation.json()["code"] == "REQUEST_VALIDATION_ERROR"


def test_unknown_api_route_uses_common_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "code": "HTTP_NOT_FOUND",
        "message": "요청한 API를 찾을 수 없어요.",
        "action": "요청 주소를 확인해 주세요.",
    }


def test_malformed_json_uses_body_field_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/brands",
        content='{"name":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["field_errors"] == {
        "body": "요청 본문 JSON 형식을 확인해 주세요."
    }


def test_method_not_allowed_preserves_allow_header(client: TestClient) -> None:
    response = client.delete("/api/v1/brands")

    assert response.status_code == 405
    assert response.json()["code"] == "HTTP_METHOD_NOT_ALLOWED"
    assert response.headers["allow"]


def test_unexpected_api_error_uses_common_error_shape(tmp_path: Path) -> None:
    app = create_test_app(Settings(data_dir=tmp_path))

    def failing_catalog_service() -> None:
        raise RuntimeError("database unavailable")

    app.dependency_overrides[get_catalog_service] = failing_catalog_service

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v1/brands")

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "서버에서 요청을 처리하지 못했어요.",
        "action": "잠시 후 다시 시도해 주세요.",
    }


def test_application_instances_do_not_share_test_databases(tmp_path: Path) -> None:
    first_settings = Settings(data_dir=tmp_path / "first")
    second_settings = Settings(data_dir=tmp_path / "second")

    with TestClient(create_test_app(first_settings)) as first_client:
        first_client.post("/api/v1/brands", json={"name": "First Bakery"})
        assert len(first_client.get("/api/v1/brands").json()) == 1

    with TestClient(create_test_app(second_settings)) as second_client:
        assert second_client.get("/api/v1/brands").json() == []
